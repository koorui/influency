import base64
import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import User


def hash_password(value):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac('sha256', value.encode(), salt, 600000)
    return base64.b64encode(salt + digest).decode()


def check_password(value, encoded):
    raw = base64.b64decode(encoded)
    return hmac.compare_digest(raw[16:], hashlib.pbkdf2_hmac('sha256', value.encode(), raw[:16], 600000))


def set_session(response: Response, subject, kind='user'):
    value = jwt.encode({'sub': subject, 'kind': kind, 'exp': datetime.now(timezone.utc) + timedelta(hours=12)}, settings().secret_key, algorithm='HS256')
    response.set_cookie('impact_session', value, httponly=True, secure=settings().cookie_secure, samesite='lax', max_age=43200)


def identity(request: Request):
    try:
        return jwt.decode(request.cookies.get('impact_session', ''), settings().secret_key, algorithms=['HS256'])
    except jwt.InvalidTokenError:
        return None


def owner(request: Request, response: Response):
    ident = identity(request)
    if not ident:
        ident = {'sub': str(uuid.uuid4()), 'kind': 'guest'}
        set_session(response, ident['sub'], 'guest')
    return f"{ident['kind']}:{ident['sub']}"


def current_user(request: Request, db: Session = Depends(get_db)):
    ident = identity(request)
    user = db.get(User, ident['sub']) if ident and ident['kind'] == 'user' else None
    if not user:
        raise HTTPException(401, '请先登录')
    return user


def admin(user: User = Depends(current_user)):
    if user.role != 'admin':
        raise HTTPException(403, '需要管理员权限')
    return user
