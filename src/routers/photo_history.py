from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from src.utils import auth
from fastapi.params import Depends
from src.ml.tasks import process_image_with_yolo
from src.schemas import PhotoProcessResult, PhotosHistory, DeletePhotoResponse, ResultEnum
from src.database.database import database
import uuid

router = APIRouter(prefix="/history", tags=["history"])

BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "uploads" / "processed"

UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)

@router.get("/")
def get_photo_history(page: int, limit: int = 10, user_by_access: dict = Depends(auth.check_access_jwt)):
    if not user_by_access:
        raise HTTPException(status_code=401)

    user_photos = database.get_user_photos(user_by_access["id"], limit, page)
    if not user_photos:
        return PhotosHistory(photos=[])
    user_photos_schema = PhotosHistory(photos=list(map(lambda x: x.to_schema(), user_photos)))

    return user_photos_schema

@router.get("/photo/{photo_id}")
def get_photo(photo_id: int, user_by_access: dict = Depends(auth.check_access_jwt)):
    if not user_by_access:
        raise HTTPException(status_code=401)

    photo = database.get_photo(photo_id, user_by_access['id'])

    if not photo:
        raise HTTPException(500, detail="Ошибка получения фото из БД")

    return photo.to_schema()

@router.delete("/delete/{photo_id}")
def delete_photo(photo_id: int, user_by_access: dict = Depends(auth.check_access_jwt)):
    if not user_by_access:
        raise HTTPException(401)

    delete_result = database.delete_photo(photo_id, user_by_access["id"])

    if not delete_result:
        raise DeletePhotoResponse(result=ResultEnum.failed)

    return DeletePhotoResponse()





