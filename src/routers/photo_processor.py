from fastapi import APIRouter
from pathlib import Path


router = APIRouter(prefix="/photo", tags=["photo"])

BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "uploads" / "processed"

UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)


@router.post("/photo/process")
def process_photo():
    pass

@router.get("/photo/process")
def get_result_photo():
    pass
