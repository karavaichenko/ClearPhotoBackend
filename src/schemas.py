from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Any


class User(BaseModel):
    login: str
    password: str


class CreateUser(BaseModel):
    login: str
    password: str
    email: str


class GoodResponse(BaseModel):

    resultCode: int = 0

    def __init__(self, code, **data):
        super().__init__(**data)
        self.resultCode = code


# 100 - verify email sends
# 101 - verify success
# 102 - refresh tokens, send request again
# 103 - operation success


class BadResponse(BaseModel):

    resultCode: int = 1

    def __init__(self, code, **data):
        super().__init__(**data)
        self.resultCode = code

# 1 - login is not in db or login already register
# 2 - uncorrected password or email already register
# 3 - bad email
# 4 - uncorrected verify code
# 5 - old refresh token
# 6 - old access token
# 66 - all bad
# 11 - need wait
# 10 - no money
# 12 - code does not exist


class VerifyRequest(BaseModel):
    code: int
    hashcode: str
    email: str


# === Photo Processor Schemas ===

class PhotoBase(BaseModel):
    id: int
    url: str
    processed: bool
    timestamp: Optional[datetime] = None


class PhotoInfo(PhotoBase):
    user_id: int


class PhotoUploadResponse(BaseModel):
    photo_id: int
    task_id: str
    status: str
    message: str
    original_filename: str
    saved_as: str


class TaskStatusBase(BaseModel):
    task_id: str
    state: str


class TaskStatusPending(TaskStatusBase):
    state: str = "PENDING"
    status: str


class TaskStatusProcessing(TaskStatusBase):
    state: str = "PROCESSING"
    progress: int = 0
    status: str
    faces: int = 0
    plates: int = 0


class TaskStatusSuccess(TaskStatusBase):
    state: str = "SUCCESS"
    result: dict


class TaskStatusFailure(TaskStatusBase):
    state: str = "FAILURE"
    error: str


class TaskStatusOther(TaskStatusBase):
    state: str
    info: Any


TaskStatus = TaskStatusPending | TaskStatusProcessing | TaskStatusSuccess | TaskStatusFailure | TaskStatusOther


class UserPhotosResponse(BaseModel):
    user_id: int
    total: int
    limit: int
    offset: int
    photos: List[PhotoBase]


class UnprocessedPhotosResponse(BaseModel):
    count: int
    photos: List[PhotoInfo]


class PhotoDeleteResponse(BaseModel):
    message: str
    photo_id: int


class PhotoStatusUpdateRequest(BaseModel):
    isProcessed: bool = True


class PhotoStatusUpdateResponse(BaseModel):
    message: str
    photo_id: int
    isProcessed: bool


class PhotoStatsResponse(BaseModel):
    user_id: int
    total: int
    processed: int
    unprocessed: int



