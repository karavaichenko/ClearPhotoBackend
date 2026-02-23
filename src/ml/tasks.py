# ml/tasks.py
import os
import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO
from celery.utils.log import get_task_logger
import traceback

# Импортируем экземпляр celery из соседнего файла
from src.ml.celery_app import celery_app

logger = get_task_logger(__name__)

# Глобальная переменная для модели (синглтон)
_model = None


def get_model():
    """Ленивая загрузка модели YOLO"""
    global _model
    if _model is None:
        # Путь к модели относительно текущего файла
        current_dir = Path(__file__).parent
        model_path = current_dir / 'pretrainedYOLO.pt'

        logger.info(f"Загружаю YOLOv8 из {model_path}...")
        _model = YOLO(str(model_path))
        logger.info("Модель YOLO успешно загружена")
    return _model


def blur_area(image, x1, y1, x2, y2, kernel_size=(99, 99), sigma=30, feather_ratio=0.1, expansion_factor=2):
    """
    Размывает указанную область на изображении с плавным градиентным переходом по краям

    Args:
        image: исходное изображение
        x1, y1, x2, y2: координаты области
        kernel_size: размер ядра размытия
        sigma: sigma для GaussianBlur
        feather_ratio: доля области для плавного перехода (0.0 - 0.5)
        expansion_factor: коэффициент расширения области размытия (больше 1 = больше область)
    """
    # Вычисляем центр и размеры оригинальной области
    center_x = (x1 + x2) // 2
    center_y = (y1 + y2) // 2
    width = x2 - x1
    height = y2 - y1

    # Расширяем область для размытия
    new_width = int(width * expansion_factor)
    new_height = int(height * expansion_factor)

    # Новые координаты с центром в том же месте
    new_x1 = center_x - new_width // 2
    new_x2 = new_x1 + new_width
    new_y1 = center_y - new_height // 2
    new_y2 = new_y1 + new_height

    # Ограничиваем координаты границами изображения
    new_x1 = max(0, new_x1)
    new_y1 = max(0, new_y1)
    new_x2 = min(image.shape[1], new_x2)
    new_y2 = min(image.shape[0], new_y2)

    # Если после ограничения область слишком мала, возвращаем оригинал
    if new_x2 <= new_x1 or new_y2 <= new_y1:
        return image

    new_height = new_y2 - new_y1
    new_width = new_x2 - new_x1

    # Вырезаем расширенную область
    area = image[new_y1:new_y2, new_x1:new_x2].copy()

    # Применяем очень сильное размытие ко всей расширенной области
    # Увеличиваем kernel_size пропорционально расширению
    expanded_kernel = (int(kernel_size[0] * expansion_factor), int(kernel_size[1] * expansion_factor))
    # Делаем ядро нечетным
    expanded_kernel = (expanded_kernel[0] | 1, expanded_kernel[1] | 1)
    # Ограничиваем максимальный размер (чтобы не зависнуть)
    expanded_kernel = (min(expanded_kernel[0], 199), min(expanded_kernel[1], 199))

    blurred_area = cv2.GaussianBlur(area, expanded_kernel, sigma * expansion_factor)

    # Вычисляем смещение оригинальной области внутри расширенной
    orig_x1 = x1 - new_x1
    orig_x2 = x2 - new_x1
    orig_y1 = y1 - new_y1
    orig_y2 = y2 - new_y1

    # Создаем маску только для оригинальной области (с градиентом)
    mask = np.zeros((new_height, new_width), dtype=np.float32)

    # Размер перехода (в пикселях) - теперь считаем от размеров оригинальной области
    feather_size_h = int(height * feather_ratio)
    feather_size_w = int(width * feather_ratio)

    # Заполняем маску только в области оригинального прямоугольника
    for i in range(orig_y1, orig_y2):
        for j in range(orig_x1, orig_x2):
            # Расстояние до краев оригинальной области
            dist_to_top = i - orig_y1
            dist_to_bottom = orig_y2 - 1 - i
            dist_to_left = j - orig_x1
            dist_to_right = orig_x2 - 1 - j

            # Минимальное расстояние до любого края
            min_dist = min(dist_to_top, dist_to_bottom, dist_to_left, dist_to_right)

            # Если внутри (дальше чем feather_size от краев)
            if min_dist >= feather_size_h and min_dist >= feather_size_w:
                mask[i, j] = 1.0  # Полностью размыто
            else:
                # Градиент от края
                weight = min_dist / min(feather_size_h, feather_size_w)
                weight = max(0, min(1, weight))
                mask[i, j] = weight

    # Дополнительно размываем маску для более плавного перехода
    mask = cv2.GaussianBlur(mask, (min(feather_size_h * 2 + 1, 51) | 1, min(feather_size_w * 2 + 1, 51) | 1), 0)

    # Расширяем маску до 3 каналов
    mask_3channel = np.stack([mask, mask, mask], axis=2)

    # Плавно смешиваем оригинал и размытую область
    result_area = (area * (1 - mask_3channel) + blurred_area * mask_3channel).astype(np.uint8)

    # Вставляем обратно
    image[new_y1:new_y2, new_x1:new_x2] = result_area

    return image

@celery_app.task(bind=True, name='process_image_with_yolo')
def process_image_with_yolo(self, image_path: str, output_path: str = None,
                            blur_faces: bool = True, blur_plates: bool = True):
    """
    Celery задача для обработки одного изображения YOLO моделью
    """
    task_id = self.request.id
    logger.info(f"[{task_id}] Запуск обработки изображения: {image_path}")

    try:
        # Обновляем статус
        self.update_state(
            state='PROCESSING',
            meta={'progress': 10, 'status': 'Проверка файла...'}
        )

        # Проверяем существование файла
        if not os.path.exists(image_path):
            error_msg = f"Изображение не найдено: {image_path}"
            logger.error(f"[{task_id}] {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'task_id': task_id
            }

        # Обновляем статус
        self.update_state(
            state='PROCESSING',
            meta={'progress': 20, 'status': 'Загрузка модели...'}
        )

        # Получаем модель
        try:
            model = get_model()
        except Exception as e:
            error_msg = f"Ошибка загрузки модели: {str(e)}"
            logger.error(f"[{task_id}] {error_msg}")
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': error_msg,
                'task_id': task_id
            }

        # Обновляем статус
        self.update_state(
            state='PROCESSING',
            meta={'progress': 30, 'status': 'Чтение изображения...'}
        )

        # Читаем изображение
        try:
            image = cv2.imread(image_path)
            if image is None:
                error_msg = f"Не удалось прочитать изображение: {image_path}"
                logger.error(f"[{task_id}] {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'task_id': task_id
                }
        except Exception as e:
            error_msg = f"Ошибка чтения изображения: {str(e)}"
            logger.error(f"[{task_id}] {error_msg}")
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': error_msg,
                'task_id': task_id
            }

        h, w = image.shape[:2]

        # Обновляем статус
        self.update_state(
            state='PROCESSING',
            meta={'progress': 50, 'status': 'Детекция объектов...'}
        )

        # Прогоняем через YOLO
        try:
            results = model(image, verbose=False)[0]  # Берем первый результат
        except Exception as e:
            error_msg = f"Ошибка детекции объектов: {str(e)}"
            logger.error(f"[{task_id}] {error_msg}")
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': error_msg,
                'task_id': task_id
            }

        # Собираем статистику
        faces_detected = 0
        plates_detected = 0
        detections = []

        # Обрабатываем найденные объекты
        if results.boxes is not None:
            boxes = results.boxes
            for box in boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])

                # Получаем координаты
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                # Сохраняем информацию о детекции
                detection = {
                    'class': 'face' if class_id == 0 else 'license_plate',
                    'confidence': round(confidence, 3),
                    'bbox': [x1, y1, x2, y2]
                }
                detections.append(detection)

                # Размываем в зависимости от класса
                if class_id == 0 and blur_faces:
                    image = blur_area(image, x1, y1, x2, y2)
                    faces_detected += 1
                    logger.debug(f"[{task_id}] Размыто лицо: [{x1}, {y1}, {x2}, {y2}], уверенность: {confidence:.2f}")

                elif class_id == 1 and blur_plates:
                    image = blur_area(image, x1, y1, x2, y2)
                    plates_detected += 1
                    logger.debug(f"[{task_id}] Размыт номер: [{x1}, {y1}, {x2}, {y2}], уверенность: {confidence:.2f}")

        # Обновляем статус
        self.update_state(
            state='PROCESSING',
            meta={
                'progress': 80,
                'status': 'Сохранение результата...',
                'faces': faces_detected,
                'plates': plates_detected
            }
        )

        # Определяем путь для сохранения результата
        if output_path is None:
            input_path = Path(image_path)
            output_dir = input_path.parent / 'processed'
            output_dir.mkdir(exist_ok=True)
            output_path = str(output_dir / f"blurred_{input_path.name}")

        # Сохраняем результат
        try:
            cv2.imwrite(output_path, image)
            logger.info(f"[{task_id}] Результат сохранен: {output_path}")
        except Exception as e:
            error_msg = f"Ошибка сохранения результата: {str(e)}"
            logger.error(f"[{task_id}] {error_msg}")
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': error_msg,
                'task_id': task_id
            }

        # Успешный результат
        result = {
            'success': True,
            'task_id': task_id,
            'input_path': image_path,
            'output_path': output_path,
            'faces_detected': faces_detected,
            'plates_detected': plates_detected,
            'total_detections': len(detections),
            'detections': detections,
            'image_size': {'width': w, 'height': h}
        }

        logger.info(f"[{task_id}] Обработка завершена. Найдено лиц: {faces_detected}, номеров: {plates_detected}")
        return result

    except Exception as e:
        # Ловим все необработанные исключения
        error_msg = f"Необработанная ошибка: {str(e)}"
        logger.error(f"[{task_id}] {error_msg}")
        logger.error(traceback.format_exc())

        return {
            'success': False,
            'error': error_msg,
            'task_id': task_id,
            'traceback': traceback.format_exc()
        }