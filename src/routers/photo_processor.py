import datetime

from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from src.utils import auth
from fastapi.params import Depends
from src.ml.tasks import process_image_with_yolo
from src.schemas import PhotoProcessResult, PhotoSchema
from src.database.database import database
import uuid

router = APIRouter(prefix="/photo", tags=["photo"])

BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "uploads" / "processed"

UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)


@router.post("/process")
def process_photo(photo: UploadFile = File(...), user_by_access: dict = Depends(auth.check_access_jwt)):

    if not user_by_access:
        raise HTTPException(status_code=401)

    unique_filename = f"{uuid.uuid4()}_{photo.filename}"
    file_path = UPLOAD_DIR / unique_filename

    with open(file_path, "wb") as buffer:
        buffer.write(photo.file.read())

    task = process_image_with_yolo.delay(str(file_path))
    result = task.get()

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Ошибка обработки изображения"))

    photo_id = database.create_photo(
        result.get("input_path"), result.get("output_path"),
        datetime.datetime.now(), user_by_access['id'],
        result.get("faces_detected"),
        result.get("plates_detected")
    )

    if photo_id is None:
        raise HTTPException(status_code=500, detail="Ошибка создания записи в БД")

    return PhotoSchema(
        id=photo_id,
        input_path=result.get("input_path"),
        output_path=result.get("output_path"),
        faces=result.get("faces_detected"),
        plates=result.get("plates_detected"),
        timestamp=datetime.datetime.now()
    )

@router.get("/result/{photo_id}")
def get_result_photo(photo_id: int, user_by_access: dict = Depends(auth.check_access_jwt)):
    if not user_by_access:
        raise HTTPException(status_code=401)

    photo = database.get_photo(photo_id, user_by_access["id"])
    
    if not photo:
        raise HTTPException(status_code=404, detail="Фото не найдено")
    
    output_path = Path(photo.output_path)
    
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    return FileResponse(path=output_path, media_type="image/jpeg", filename=output_path.name)

@router.get("/input/{photo_id}")
def get_entered_photo(photo_id: int, user_by_access: dict = Depends(auth.check_access_jwt)):
    if not user_by_access:
        raise HTTPException(status_code=401)

    photo = database.get_photo(photo_id, user_by_access["id"])

    if not photo:
        raise HTTPException(status_code=404, detail="Фото не найдено")

    input_path = Path(photo.input_path)

    if not input_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")

    return FileResponse(path=input_path, media_type="image/jpeg", filename=input_path.name)





