from datetime import timedelta, datetime

import jwt

from fastapi import Cookie

private_key = 'certs/private_key.pem'
with open(private_key) as f:
    key = f.read()
    private_key = key
public_key = 'certs/public_key.pem'
with open(public_key) as f:
    key = f.read()
    public_key = key


def create_jwt(user_id: int, login: str, ttl: int = 15):
    now = datetime.utcnow()
    delta = timedelta(minutes=ttl)
    exp = now + delta
    payload = {
        'login': login,
        'id': user_id,
        'exp': exp,

    }
    token = jwt.encode(payload=payload, algorithm="RS256", key=private_key)
    return token


def check_access_jwt(access_token: str = Cookie(None)):
    try:
        if type(access_token) is str:
            decoded = jwt.decode(jwt=access_token.encode(), key=public_key, algorithms=['RS256'])
            if access_token != jwt.encode(payload=decoded, algorithm="RS256", key=private_key):
                return None
            else:
                return decoded
    except:
        return None


def check_refresh_jwt(refresh_token: str = Cookie(None)):
    try:
        if type(refresh_token) is str:
            decoded = jwt.decode(jwt=refresh_token.encode(), key=public_key, algorithms=['RS256'])
            if refresh_token != jwt.encode(payload=decoded, algorithm="RS256", key=private_key):
                return None
            else:
                return decoded
    except:
        return None