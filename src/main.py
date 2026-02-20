from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import os
import uvicorn
from dotenv import load_dotenv

from starlette.responses import JSONResponse

from src.database.database import Database
from src.schemas import User, CreateUser, BadResponse, GoodResponse, VerifyRequest
from src.utils.auth import check_access_jwt, check_refresh_jwt, create_jwt
from src.utils.utils import generate_verify_code, send_register_email, get_hash, validate_password

app = FastAPI()
print('start')

load_dotenv()

path = 'localhost'
if 'MY_PATH' in os.environ:
    path = os.environ["MY_PATH"]

URL = os.getenv('DB_URL')
print(URL)
database = Database(URL)


@app.post("/auth/login")
def login(user: User):
    user_db = database.get_user(user.login)
    if user_db is not None:
        if validate_password(user.password, user_db.password):
            access = create_jwt(user_db.id, user_db.login)
            refresh = create_jwt(user_db.id, user_db.login, 14*24*60)
            content = {
                'login': user_db.login,
                'email': user_db.email,
                'verify': True,
                'resultCode': 1000
            }
            response = add_cookie(content, refresh, access)
            return response
        return BadResponse(2)
    return BadResponse(1)


@app.post("/auth/registration")
def register(user: CreateUser):
    if database.get_user(user.login) is not None:
        return BadResponse(1)
    elif not database.check_email(user.email):
        return BadResponse(2)
    else:
        verifyCode = generate_verify_code()
        result = send_register_email(message=verifyCode, receiver=user.email)
        if result == 0:
            database.create_user(login=user.login, email=user.email, password=user.password)
            hashcode = get_hash(str(verifyCode) + user.email)
            return {
                'hash': hashcode,
                'resultCode': 100
            }
        else:
            return BadResponse(3)


@app.post("/auth/registration/verify")
def verify_registration(request: VerifyRequest):
    hashcode = get_hash(str(request.code) + request.email)
    a1 = get_hash(str(request.code) + request.email)
    if hashcode == request.hashcode:
        database.verify_email(request.email)
        return GoodResponse(101)
    else:
        return BadResponse(4)


@app.get('/auth')
def auth(user_by_access: dict = Depends(check_access_jwt),
         user_by_refresh: dict = Depends(check_refresh_jwt)):
    if user_by_access:
        user = database.get_user(user_by_access['login'])
        if not user:
            return BadResponse(5)
        content = {
            "login": user.login,
            "email": user.email,
            "verify": user.verify,
        }
        return content
    elif user_by_refresh:
        user = database.get_user(user_by_refresh['login'])
        content = {
            "login": user.login,
            "email": user.email,
            "verify": user.verify,
        }
        response = add_cookie(content, create_jwt(user.id, user.login, 14*24*60), create_jwt(user.id, user.login))
        return response
    else:
        return BadResponse(5)


@app.delete('/auth/logout')
def logout():
    response = add_cookie({"resultCode": 0}, "", "")
    return response


def add_cookie(content, refresh, access):
    response = JSONResponse(content=content)
    response.set_cookie(key="access_token", value=access)
    response.set_cookie(key="refresh_token", value=refresh)
    return response


origins = [
    "http://localhost",
    "http://localhost:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    uvicorn.run("main:app")