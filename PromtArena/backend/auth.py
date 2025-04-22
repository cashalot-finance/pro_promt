# backend/auth.py

from datetime import datetime, timedelta
from typing import Optional, Union, Dict, Any
import jwt
from fastapi import HTTPException, Depends, status, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer, HTTPAuthorizationCredentials
import secrets
import os
import logging
import time
from collections import defaultdict
from backend.config import settings, User, TokenData

# Настройка логгера
logger = logging.getLogger(__name__)

# Секрет для JWT-токенов
# В продакшене лучше хранить в переменных окружения
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "efd99c5e7b5baa0a5ec11bf26b2908732f933d60dc27a492b5c15b45539073a9")
ALGORITHM = "HS256"

security_basic = HTTPBasic()
security_bearer = HTTPBearer()

# Защита от brute-force
MAX_FAILED_ATTEMPTS = 5  # Максимальное количество неудачных попыток
LOCKOUT_TIME = 300  # Время блокировки в секундах (5 минут)
failed_login_attempts = defaultdict(list)  # username -> [timestamp1, timestamp2, ...]
ip_login_attempts = defaultdict(list)  # ip -> [timestamp1, timestamp2, ...]

# Пользователи для базовой аутентификации
USERS = {
    "admin": {
        "password": settings.auth_password,
        "is_admin": True
    },
    "13": {  # Основной администраторский аккаунт
        "password": "131313",
        "is_admin": True
    },
    "guest": {
        "password": settings.guest_password,
        "is_admin": False
    },
    "13guest": {  # Гостевой аккаунт
        "password": "13",
        "is_admin": False
    }
}

def is_account_locked(username: str) -> bool:
    """Проверяет, заблокирован ли аккаунт из-за большого количества неудачных попыток."""
    now = time.time()
    # Очищаем старые попытки
    failed_login_attempts[username] = [t for t in failed_login_attempts[username] 
                                     if now - t < LOCKOUT_TIME]
    
    # Проверяем количество неудачных попыток
    if len(failed_login_attempts[username]) >= MAX_FAILED_ATTEMPTS:
        # Вычисляем, сколько времени осталось до разблокировки
        time_passed = now - failed_login_attempts[username][0]
        time_left = LOCKOUT_TIME - time_passed
        logger.warning(f"Аккаунт {username} заблокирован на {time_left:.1f} секунд после {MAX_FAILED_ATTEMPTS} неудачных попыток")
        return True
    
    return False

def is_ip_blocked(ip_address: str) -> bool:
    """Проверяет, заблокирован ли IP-адрес из-за большого количества неудачных попыток."""
    now = time.time()
    # Очищаем старые попытки
    ip_login_attempts[ip_address] = [t for t in ip_login_attempts[ip_address] 
                                   if now - t < LOCKOUT_TIME]
    
    # Проверяем количество неудачных попыток
    if len(ip_login_attempts[ip_address]) >= MAX_FAILED_ATTEMPTS * 2:  # Умножаем на 2 для IP (более мягкая политика)
        time_passed = now - ip_login_attempts[ip_address][0]
        time_left = LOCKOUT_TIME - time_passed
        logger.warning(f"IP {ip_address} заблокирован на {time_left:.1f} секунд после множества неудачных попыток")
        return True
    
    return False

def record_failed_attempt(username: str, ip_address: Optional[str] = None):
    """Записывает неудачную попытку входа."""
    now = time.time()
    failed_login_attempts[username].append(now)
    if ip_address:
        ip_login_attempts[ip_address].append(now)
    
    # Логируем попытки
    attempt_count = len(failed_login_attempts[username])
    logger.warning(f"Неудачная попытка входа для пользователя {username} (попытка {attempt_count}/{MAX_FAILED_ATTEMPTS})")
    
    if attempt_count >= MAX_FAILED_ATTEMPTS:
        logger.warning(f"Достигнут лимит неудачных попыток для {username}, аккаунт временно заблокирован")

def verify_password(plain_password: str, username: str) -> bool:
    """Проверяет пароль пользователя."""
    if username not in USERS:
        return False
    return secrets.compare_digest(plain_password, USERS[username]["password"])

def get_user(username: str) -> Optional[Dict[str, Any]]:
    """Получает информацию о пользователе по имени."""
    if username in USERS:
        user_dict = USERS[username].copy()
        user_dict["username"] = username
        return user_dict
    return None

def authenticate_user(username: str, password: str, ip_address: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Аутентифицирует пользователя и возвращает его данные."""
    # Проверяем блокировку аккаунта
    if is_account_locked(username):
        return None
    
    # Проверяем блокировку IP
    if ip_address and is_ip_blocked(ip_address):
        return None
    
    user = get_user(username)
    if not user:
        # Записываем неудачную попытку для несуществующего пользователя
        record_failed_attempt(username, ip_address)
        return None
        
    if not verify_password(password, username):
        # Записываем неудачную попытку
        record_failed_attempt(username, ip_address)
        return None
        
    return user

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Создает JWT-токен для пользователя."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.token_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> Optional[TokenData]:
    """Декодирует JWT-токен и возвращает данные пользователя."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        is_admin: bool = payload.get("is_admin", False)
        exp: datetime = datetime.fromtimestamp(payload.get("exp"))
        
        if username is None:
            return None
            
        return TokenData(username=username, is_admin=is_admin, exp=exp)
    except jwt.PyJWTError:
        return None

async def get_current_user_basic(credentials: HTTPBasicCredentials = Depends(security_basic), request: Request = None) -> User:
    """Аутентификация через Basic Auth."""
    # Получаем IP-адрес клиента, если request доступен
    ip_address = None
    if request:
        ip_address = request.client.host
    
    user = authenticate_user(credentials.username, credentials.password, ip_address)
    if not user:
        # Проверяем, заблокирован ли аккаунт
        if is_account_locked(credentials.username):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Слишком много неудачных попыток входа. Пожалуйста, попробуйте позже.",
                headers={"WWW-Authenticate": "Basic", "Retry-After": str(LOCKOUT_TIME)},
            )
        
        # Проверяем, заблокирован ли IP
        if ip_address and is_ip_blocked(ip_address):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Слишком много неудачных попыток входа с вашего IP. Пожалуйста, попробуйте позже.",
                headers={"WWW-Authenticate": "Basic", "Retry-After": str(LOCKOUT_TIME)},
            )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    logger.info(f"Пользователь {credentials.username} аутентифицирован через Basic Auth")
    
    return User(username=user["username"], is_admin=user["is_admin"])

async def get_current_user_token(credentials: HTTPAuthorizationCredentials = Depends(security_bearer)) -> User:
    """Аутентификация через Bearer token (JWT)."""
    token_data = decode_token(credentials.credentials)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный или истекший токен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.debug(f"Пользователь {token_data.username} аутентифицирован через JWT")
    
    return User(username=token_data.username, is_admin=token_data.is_admin)

async def get_current_active_user(
    user: User = Depends(get_current_user_basic)
) -> User:
    """Проверяет, что пользователь активен."""
    # Здесь можно добавить дополнительные проверки
    return user

async def get_admin_user(
    user: User = Depends(get_current_active_user)
) -> User:
    """Проверяет, что пользователь - администратор."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="У вас недостаточно прав для этой операции"
        )
    return user

# Функция для создания основных пользователей
def create_default_users():
    """Создает пользователей по умолчанию при первом запуске."""
    # Уже определены статически в словаре USERS
    logger.info(f"Зарегистрированы пользователи: admin, guest, 13, 13guest")
    
    # Можно расширить для добавления пользователей в БД
    return True