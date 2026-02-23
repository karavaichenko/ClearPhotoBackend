from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Body
from fastapi.responses import FileResponse
import os
import uuid
from pathlib import Path
import aiofiles
from typing import Optional
from src.ml.tasks import process_image_with_yolo
from src.database.database import database
from src.routers.auth import get_current_user
from src.schemas import (
    PhotoBase, PhotoInfo,
    PhotoUploadResponse, TaskStatus,
    TaskStatusProcessing, TaskStatusSuccess,
    TaskStatusFailure, TaskStatusOther,
    TaskStatusPending, UserPhotosResponse,
    UnprocessedPhotosResponse, PhotoDeleteResponse,
    PhotoStatusUpdateRequest, PhotoStatusUpdateResponse,
    PhotoStatsResponse,
)

router = APIRouter(prefix="/photo", tags=["photo"])

BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "uploads" / "processed"

UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)


@router.post("/upload", response_model=PhotoUploadResponse)
async def upload_photo(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Загружает фото и запускает обработку YOLO моделью
    """
    user_id = current_user['id']
    try:
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="Файл должен быть изображением")
        file_extension = Path(file.filename).suffix.lower()
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Неподдерживаемый формат. Разрешены: {', '.join(allowed_extensions)}"
            )
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = UPLOAD_DIR / unique_filename
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)

        photo = database.create_photo(
            user_id=user_id,
            url=str(file_path)
        )
        if not photo:
            raise HTTPException(status_code=500, detail="Не удалось создать запись о фото")

        output_filename = f"blurred_{unique_filename}"
        output_path = PROCESSED_DIR / output_filename

        # Запускаем Celery задачу с photo_id
        task = process_image_with_yolo.delay(
            image_path=str(file_path),
            output_path=str(output_path),
            photo_id=photo.id,
            blur_faces=True,
            blur_plates=True
        )

        return PhotoUploadResponse(
            photo_id=photo.id,
            task_id=task.id,
            status='processing',
            message='Фото отправлено на обработку',
            original_filename=file.filename,
            saved_as=unique_filename
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки: {str(e)}")


@router.get("/task/{task_id}", response_model=TaskStatus)
async def get_task_status(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Получить статус обработки по ID задачи
    """
    task = process_image_with_yolo.AsyncResult(task_id)

    if task.state == 'PENDING':
        return TaskStatusPending(
            task_id=task_id,
            state=task.state,
            status='Задача ожидает выполнения'
        )
    elif task.state == 'PROCESSING':
        return TaskStatusProcessing(
            task_id=task_id,
            state=task.state,
            progress=task.info.get('progress', 0),
            status=task.info.get('status', 'Обработка...'),
            faces=task.info.get('faces', 0),
            plates=task.info.get('plates', 0)
        )
    elif task.state == 'SUCCESS':
        photo_id = task.result.get('photo_id')
        photo = database.get_photo(photo_id)
        if not photo or photo.user_id != current_user['id']:
            raise HTTPException(status_code=403, detail="Доступ запрещён")
        return TaskStatusSuccess(
            task_id=task_id,
            state=task.state,
            result=task.result
        )
    elif task.state == 'FAILURE':
        return TaskStatusFailure(
            task_id=task_id,
            state=task.state,
            error=str(task.info)
        )
    else:
        return TaskStatusOther(
            task_id=task_id,
            state=task.state,
            info=str(task.info)
        )


@router.get("/result/{photo_id}")
async def get_processed_photo(
    photo_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Получить обработанное фото по ID фото из БД
    """
    photo = database.get_photo(photo_id)

    if not photo:
        raise HTTPException(status_code=404, detail="Фото не найдено")

    if photo.user_id != current_user['id']:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    if not photo.isProcessed:
        raise HTTPException(status_code=404, detail="Фото еще не обработано")

    if not os.path.exists(photo.url):
        raise HTTPException(status_code=404, detail="Файл не найден на диске")

    return FileResponse(
        path=photo.url,
        media_type="image/jpeg",
        filename=os.path.basename(photo.url)
    )


@router.get("/user", response_model=UserPhotosResponse)
async def get_user_photos(
    current_user: dict = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
    processed: Optional[bool] = None
):
    """
    Получить все фото пользователя с пагинацией
    """
    user_id = current_user['id']
    photos = database.get_user_photos(user_id, limit, offset)

    if processed is not None:
        photos = [p for p in photos if p.isProcessed == processed]

    total = database.get_photos_count(user_id)

    return UserPhotosResponse(
        user_id=user_id,
        total=total,
        limit=limit,
        offset=offset,
        photos=[
            PhotoBase(
                id=p.id,
                url=p.url,
                processed=p.isProcessed,
                timestamp=p.timestamp if p.timestamp else None
            )
            for p in photos
        ]
    )


@router.get("/unprocessed", response_model=UnprocessedPhotosResponse)
async def get_unprocessed_photos(
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """
    Получить список необработанных фото (для админки/мониторинга)
    """
    photos = database.get_unprocessed_photos(limit)

    return UnprocessedPhotosResponse(
        count=len(photos),
        photos=[
            PhotoInfo(
                id=p.id,
                url=p.url,
                user_id=p.user_id,
                processed=p.isProcessed,
                timestamp=p.timestamp if p.timestamp else None
            )
            for p in photos
        ]
    )


@router.get("/{photo_id}", response_model=PhotoInfo)
async def get_photo_info(
    photo_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Получить информацию о фото по ID
    """
    photo = database.get_photo(photo_id)

    if not photo:
        raise HTTPException(status_code=404, detail="Фото не найдено")

    if photo.user_id != current_user['id']:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    return PhotoInfo(
        id=photo.id,
        url=photo.url,
        user_id=photo.user_id,
        processed=photo.isProcessed,
        timestamp=photo.timestamp if photo.timestamp else None
    )


@router.delete("/{photo_id}", response_model=PhotoDeleteResponse)
async def delete_photo(
    photo_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Удалить фото из БД
    """
    photo = database.get_photo(photo_id)

    if not photo:
        raise HTTPException(status_code=404, detail="Фото не найдено")

    if photo.user_id != current_user['id']:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    success = database.delete_photo(photo_id)

    if not success:
        raise HTTPException(status_code=500, detail="Не удалось удалить фото из БД")

    try:
        if os.path.exists(photo.url):
            os.remove(photo.url)
    except Exception as e:
        print(f"Ошибка при удалении файла {photo.url}: {e}")

    return PhotoDeleteResponse(
        message='Фото успешно удалено',
        photo_id=photo_id
    )


@router.put("/{photo_id}/status", response_model=PhotoStatusUpdateResponse)
async def update_photo_status(
    photo_id: int,
    status_update: PhotoStatusUpdateRequest = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Обновить статус обработки фото
    """
    photo = database.get_photo(photo_id)

    if not photo:
        raise HTTPException(status_code=404, detail="Фото не найдено")

    if photo.user_id != current_user['id']:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    success = database.update_photo_status(photo_id, status_update.isProcessed)

    if not success:
        raise HTTPException(status_code=404, detail="Фото не найдено или не удалось обновить")

    return PhotoStatusUpdateResponse(
        message='Статус фото обновлен',
        photo_id=photo_id,
        isProcessed=status_update.isProcessed
    )


@router.get("/stats/count", response_model=PhotoStatsResponse)
async def get_photos_stats(
    current_user: dict = Depends(get_current_user)
):
    """
    Получить статистику по фото
    """
    user_id = current_user['id']
    total = database.get_photos_count(user_id)

    photos = database.get_user_photos(user_id, limit=1000)
    processed = sum(1 for p in photos if p.isProcessed)
    unprocessed = total - processed

    return PhotoStatsResponse(
        user_id=user_id,
        total=total,
        processed=processed,
        unprocessed=unprocessed
    )
