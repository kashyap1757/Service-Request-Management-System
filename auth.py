import os
from time import time
from typing import Dict

import jwt
from dotenv import load_dotenv
from passlib.context import CryptContext
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

load_dotenv()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
TOKEN_EXPIRY_SECONDS = int(os.getenv("TOKEN_EXPIRY_SECONDS", 3600))

# password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(user_password: str, db_hashed_password: str) -> bool:
    return pwd_context.verify(user_password, db_hashed_password)


def create_token(user_id: int, role: str) -> str:
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": time() + TOKEN_EXPIRY_SECONDS,
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def decode_jwt(token: str) -> Dict:
    try:
        decoded_token = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return decoded_token if decoded_token["exp"] >= time() else None
    except jwt.PyJWTError:
        return None


security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> Dict:
    """Decodes the bearer token and returns {user_id, role} for the caller."""
    token = credentials.credentials
    payload = decode_jwt(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"user_id": payload["user_id"], "role": payload["role"]}


def require_role(*allowed_roles: str):
    """Dependency factory: restricts an endpoint to one or more roles.

    Usage: Depends(require_role("staff", "admin"))
    """

    def role_checker(current_user: Dict = Depends(get_current_user)) -> Dict:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user

    return role_checker
