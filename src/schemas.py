from pydantic import BaseModel
from enum import Enum
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

class ResultEnum(str, Enum):
    success = "success"
    failed = "failed"


class VerifyRequest(BaseModel):
    code: int
    hashcode: str
    email: str

class ChangePasswordRequest(BaseModel):
    oldPassword: str
    newPassword: str

class ChangePasswordResponse(BaseModel):
    result: ResultEnum = ResultEnum.success



# ========== Модели для обработки фото ===========


class PhotoProcessResult(BaseModel):
    id: str | None
    success: bool
    input_path: str | None
    output_path: str | None
    faces: int
    plates: int

class PhotoSchema(BaseModel):
    id: int | None
    input_path: str | None
    output_path: str | None
    faces: int
    plates: int
    timestamp: datetime

class PhotosHistory(BaseModel):
    photos: list[PhotoSchema]
    count: int

class DeletePhotoResponse(BaseModel):
    result: ResultEnum = ResultEnum.success

# ========== Модели аккаунта ===========

class AccountDataResponse(BaseModel):
    login: str
    email: str
    photoCount: int

    