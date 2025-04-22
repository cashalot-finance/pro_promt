# backend/main.py

import logging
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any, Union, Tuple
import os
import time
import asyncio
from collections import defaultdict
from datetime import timedelta
import json

from fastapi import FastAPI, Depends, HTTPException, Request, status, Path, Query, BackgroundTasks, APIRouter
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

# Импорты из нашего проекта
from backend import database, data_logic, models_io, auth, utils
from backend.config import (
    settings, ApiKeyCreate, ApiKeyRead, ModelInfo, InteractionRequest,
    InteractionResponse, ComparisonRequest, ComparisonResponse, RatingCreate, RatingRead,
    LeaderboardEntry, CategoryInfo, SUPPORTED_PROVIDERS, SystemPromptCreate, SystemPromptRead,
    Token, User, PromptTemplateCreate, PromptTemplateRead, PromptTemplateUpdate
)

# Настройка логгера (уровень уже установлен в config.py)
logger = logging.getLogger(__name__)

# Добавляем функцию для проверки окружения перед запуском
def validate_environment() -> Tuple[bool, List[str]]:
    """
    Проверяет обязательные переменные окружения перед запуском приложения.
    
    Returns:
        Tuple[bool, List[str]]: (все_ли_проверки_пройдены, список_ошибок)
    """
    errors = []
    
    # Проверяем критически важные переменные для безопасности
    if settings.is_production:
        # Проверка настроек CORS в production
        if '*' in settings.cors_origins:
            errors.append("CORS_ORIGINS содержит '*', что небезопасно для production.")
        
        # Проверка настроек SSL для production
        if not settings.use_ssl:
            errors.append("В production режиме рекомендуется использовать SSL (USE_SSL=True).")
        
        if settings.use_ssl and (not settings.ssl_cert_path or not settings.ssl_key_path):
            errors.append("SSL включен, но не указаны пути к сертификату (SSL_CERT_PATH) и ключу (SSL_KEY_PATH).")
        
        # Проверка настроек авторизации
        if settings.disable_auth:
            errors.append("Авторизация отключена (DISABLE_AUTH=True), что небезопасно для production.")
            
        # Проверка дефолтных паролей
        if settings.auth_password == "131313":
            errors.append("Используется дефолтный пароль администратора. Измените AUTH_PASSWORD в .env.")
            
        if settings.guest_password == "13":
            errors.append("Используется дефолтный пароль гостя. Измените GUEST_PASSWORD в .env.")
    
    # Проверяем критически важные настройки для работы приложения
    if not settings.database_url:
        errors.append("Не указан URL базы данных (DATABASE_URL).")
    
    # Возвращаем результат проверки
    return len(errors) == 0, errors

# --- Lifecycle Events ---

# Определение пути к директории data и её создание при необходимости
import os
import logging

data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
if not os.path.exists(data_dir):
    os.makedirs(data_dir, exist_ok=True)
    logging.getLogger(__name__).info(f"Создана директория для данных: {data_dir}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Асинхронный контекстный менеджер для управления жизненным циклом FastAPI.
    Выполняется при старте и остановке приложения.
    """
    logger.info("Запуск приложения Промт Арена...")
    
    # Проверяем корректность переменных окружения
    logger.info("Проверка переменных окружения...")
    env_valid, env_errors = validate_environment()
    if not env_valid:
        for error in env_errors:
            logger.warning(f"⚠️ {error}")
        
        if settings.is_production:
            logger.critical("Критические ошибки конфигурации в production режиме!")
            raise SystemExit("Невозможно запустить приложение из-за ошибок конфигурации. Проверьте .env файл.")
        else:
            logger.warning("⚠️ Обнаружены проблемы с конфигурацией! В dev-режиме приложение будет запущено, но могут быть проблемы.")
    
    # Проверяем зависимости
    logger.info("Проверка необходимых зависимостей...")
    missing_critical, missing_packages = utils.check_dependencies()
    if missing_critical:
        logger.warning("⚠️ Запуск с отсутствующими критическими зависимостями! Некоторая функциональность будет недоступна.")
    
    try:
        await database.init_db()
        logger.info("База данных успешно инициализирована.")
        
        # Выводим информацию о доступе
        access_links = utils.generate_access_links(port=settings.port, secure=False)
        logger.info("=" * 50)
        logger.info("🚀 Промт Арена успешно запущена!")
        logger.info("=" * 50)
        logger.info("🔗 Локальный доступ:")
        for link in access_links["local"]:
            logger.info(f"  - {link}")
        logger.info("")
        if access_links["public"]:
            logger.info("🌐 Внешний доступ (если ваш роутер настроен):")
            for link in access_links["public"]:
                logger.info(f"  - {link}")
        logger.info("=" * 50)
        logger.info(f"📝 Учетные данные для входа:")
        
        # Полностью маскируем имена пользователей для повышения безопасности
        def mask_username(username):
            if not username:
                return "******"
            return '*' * len(username)
            
        masked_admin = mask_username(settings.auth_username)
        masked_guest = mask_username(settings.guest_username)
        
        logger.info(f"  Админ:  {masked_admin} / {'*' * len(settings.auth_password)}")
        logger.info(f"  Гость:  {masked_guest} / {'*' * len(settings.guest_password)}")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.critical("КРИТИЧЕСКАЯ ОШИБКА: Не удалось инициализировать базу данных!", exc_info=e)
        raise SystemExit("Не удалось инициализировать БД.")

    yield # Приложение работает

    logger.info("Остановка приложения Промт Арена...")

# --- Middleware для ограничения частоты запросов ---

class RateLimitMiddleware:
    def __init__(self, app, max_requests: int = 60, window_size: int = 60):
        self.app = app
        self.max_requests = max_requests
        self.window_size = window_size  # в секундах
        self.requests = defaultdict(list)
        # Добавляем отдельные ограничения для разных путей и методов
        self.path_limits = {
            "/api/v1/token": {"max": 10, "window": 60},  # Строгие ограничения для авторизации (10 запросов в минуту)
            "/api/v1/interact": {"max": 30, "window": 60},  # Ограничения для запросов к моделям
            "/api/v1/compare": {"max": 20, "window": 60},  # Ограничения для сравнения моделей
        }
        # Лимиты по методам запросов
        self.method_limits = {
            "POST": {"max": 40, "window": 60},  # POST запросы обычно более "тяжелые"
            "PUT": {"max": 40, "window": 60},
            "DELETE": {"max": 30, "window": 60},
        }
        logger.info(f"Инициализирован RateLimitMiddleware: {max_requests} запросов за {window_size} секунд")
        
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        # Получаем информацию о запросе
        path = scope.get("path", "")
        method = scope.get("method", "").upper()
        
        # Получаем IP клиента
        headers = dict(scope.get("headers", []))
        client_ip = None
        
        # Проверяем X-Forwarded-For заголовок (для запросов через прокси)
        if b"x-forwarded-for" in headers:
            forwarded_for = headers[b"x-forwarded-for"].decode().split(",")[0].strip()
            if forwarded_for:
                client_ip = forwarded_for
        
        # Если X-Forwarded-For не найден, используем IP из scope
        if not client_ip:
            client_addr = scope.get("client")
            if client_addr:
                client_ip = client_addr[0]
            else:
                client_ip = "0.0.0.0"  # Неизвестный IP
        
        # Определяем применимые лимиты
        # Сначала проверяем конкретный путь
        limits = self.path_limits.get(path, None)
        if limits:
            max_requests = limits["max"]
            window_size = limits["window"]
        # Затем проверяем метод запроса
        elif method in self.method_limits:
            limits = self.method_limits[method]
            max_requests = limits["max"]
            window_size = limits["window"]
        # Иначе используем значения по умолчанию
        else:
            max_requests = self.max_requests
            window_size = self.window_size
        
        # Определяем уникальный ключ для запроса (IP + путь)
        request_key = f"{client_ip}:{path}"
        
        # Очищаем старые запросы
        current_time = time.time()
        self.requests[request_key] = [t for t in self.requests[request_key] 
                                   if current_time - t < window_size]
        
        # Проверяем количество запросов
        if len(self.requests[request_key]) >= max_requests:
            # Вычисляем время до сброса ограничения
            oldest_request = min(self.requests[request_key]) if self.requests[request_key] else current_time
            reset_after = int(window_size - (current_time - oldest_request))
            
            # Логируем информацию о превышении лимита
            logger.warning(
                f"Rate limit превышен для {client_ip} на пути {path}: "
                f"{len(self.requests[request_key])}/{max_requests} запросов за {window_size} секунд"
            )
            
            # Формируем ответ с ошибкой 429 Too Many Requests и дополнительными заголовками
            response = {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"retry-after", str(reset_after).encode()],
                    [b"x-ratelimit-limit", str(max_requests).encode()],
                    [b"x-ratelimit-remaining", b"0"],
                    [b"x-ratelimit-reset", str(reset_after).encode()],
                ],
            }
            await send(response)
            
            # Формируем тело ответа с подробной информацией
            body = {
                "detail": "Слишком много запросов. Пожалуйста, попробуйте позже.",
                "limit": max_requests,
                "window": window_size,
                "retry_after": reset_after
            }
            
            await send({
                "type": "http.response.body",
                "body": json.dumps(body).encode(),
            })
            return
        
        # Добавляем текущий запрос
        self.requests[request_key].append(current_time)
        
        # Добавляем заголовки с информацией о лимитах
        if scope.get("extensions", {}).get("http.response.headers"):
            scope["extensions"]["http.response.headers"].extend([
                (b"x-ratelimit-limit", str(max_requests).encode()),
                (b"x-ratelimit-remaining", str(max_requests - len(self.requests[request_key])).encode()),
            ])
        
        # Продолжаем обработку запроса
        await self.app(scope, receive, send)

# --- Middleware для ограничения размера запроса ---
class MaxBodySizeMiddleware:
    def __init__(self, app, max_size_mb: int = 10):
        """
        Middleware для ограничения размера запроса (payload).
        
        Args:
            app: FastAPI приложение
            max_size_mb: Максимальный размер payload в мегабайтах
        """
        self.app = app
        self.max_size = max_size_mb * 1024 * 1024  # Конвертируем в байты
        logger.info(f"Инициализирован MaxBodySizeMiddleware: ограничение {max_size_mb} МБ")
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        client_addr = scope.get("client", ("unknown", 0))
        client_ip = client_addr[0]
        path = scope.get("path", "")
        
        async def receive_with_size_limit():
            message = await receive()
            
            if message["type"] == "http.request":
                body_size = len(message.get("body", b""))
                
                # Если размер превышает лимит - возвращаем ошибку 413
                if body_size > self.max_size:
                    logger.warning(
                        f"Превышен лимит размера запроса от {client_ip} на {path}: "
                        f"{body_size/1024/1024:.2f} МБ > {self.max_size/1024/1024:.2f} МБ"
                    )
                    
                    # Отправляем ответ с ошибкой
                    await send({
                        "type": "http.response.start",
                        "status": 413,
                        "headers": [
                            (b"content-type", b"application/json"),
                        ],
                    })
                    
                    error_message = json.dumps({
                        "detail": f"Превышен максимальный размер запроса ({self.max_size/1024/1024:.2f} МБ)",
                        "current_size_mb": f"{body_size/1024/1024:.2f}",
                        "max_size_mb": f"{self.max_size/1024/1024:.2f}"
                    }).encode()
                    
                    await send({
                        "type": "http.response.body",
                        "body": error_message,
                    })
                    
                    return {"type": "http.disconnect"}
                
            return message
        
        await self.app(scope, receive_with_size_limit, send)

# --- Настройка безопасности и middleware ---
# Инициализируем список trusted hosts, если они указаны
trusted_hosts = settings.trusted_hosts if hasattr(settings, 'trusted_hosts') else []

# --- Инициализация FastAPI приложения ---
app = FastAPI(
    title="Промт Арена API",
    description="""
API для веб-приложения "Промт Арена". Предоставляет эндпоинты для:
- Управления API ключами различных LLM провайдеров.
- Получения списка доступных моделей и категорий.
- Взаимодействия с одной или двумя моделями (отправка промтов).
- Сохранения пользовательских оценок ответов моделей.
- Получения лидерборда моделей на основе оценок.

**Ключевые особенности:**
- Асинхронная обработка запросов.
- Поддержка нескольких LLM провайдеров.
- Шифрование API ключей в базе данных.
- Система рейтинга и лидерборд.
""",
    lifespan=lifespan,
    # В production режиме отключаем docs и redoc
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
    version=settings.app_version,
    swagger_ui_parameters={"syntaxHighlight.theme": "obsidian"}
)

# Добавляем middleware
app.add_middleware(RateLimitMiddleware, max_requests=settings.max_requests_per_minute, window_size=60)
app.add_middleware(MaxBodySizeMiddleware, max_size_mb=settings.max_prompt_length // 1000 or 10)  # Ограничение размера payload

# Настраиваем CORS для нашего API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Маршруты для статических файлов и фронтенда ---

# Определение путей к статике и индексному файлу с обработкой ошибок
def get_frontend_paths():
    """
    Определяет пути к frontend директориям и файлам с обработкой ошибок.
    
    Returns:
        Dict: Словарь с путями к frontend ресурсам
    """
    try:
        # Определяем путь к директории проекта
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Проверяем существование frontend директории
        frontend_dir = os.path.join(project_root, 'frontend')
        if not os.path.exists(frontend_dir):
            logger.warning(f"Директория frontend не найдена по пути: {frontend_dir}")
            os.makedirs(frontend_dir, exist_ok=True)
            logger.info(f"Создана директория frontend: {frontend_dir}")
        
        # Проверяем существование index.html
        index_path = os.path.join(project_root, 'frontend', 'index.html')
        if not os.path.exists(index_path):
            logger.warning(f"Файл index.html не найден по пути: {index_path}")
            
            # Создаём временный index.html с информацией о проблеме
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write("""
                <!DOCTYPE html>
                <html lang="ru">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Промт Арена - Ошибка</title>
                    <style>
                        body {
                            font-family: Arial, sans-serif;
                            line-height: 1.6;
                            max-width: 800px;
                            margin: 0 auto;
                            padding: 20px;
                            color: #333;
                        }
                        h1 { color: #e74c3c; }
                        .box {
                            background-color: #f8f9fa;
                            border-left: 4px solid #e74c3c;
                            padding: 15px;
                            margin: 20px 0;
                        }
                        code {
                            background-color: #eee;
                            padding: 2px 4px;
                            border-radius: 3px;
                        }
                    </style>
                </head>
                <body>
                    <h1>Ошибка: Файлы фронтенда не найдены</h1>
                    <div class="box">
                        <p>Приложение не смогло найти необходимые файлы фронтенда. Возможные причины:</p>
                        <ul>
                            <li>Вы не скопировали файлы фронтенда в директорию <code>frontend/</code></li>
                            <li>Произошла ошибка при установке приложения</li>
                        </ul>
                    </div>
                    <h2>Как исправить?</h2>
                    <ol>
                        <li>Убедитесь, что директория <code>frontend/</code> содержит все необходимые файлы</li>
                        <li>Перезапустите приложение</li>
                        <li>Если проблема сохраняется, обратитесь к документации</li>
                    </ol>
                </body>
                </html>
                """)
            logger.info(f"Создан временный index.html с инструкциями: {index_path}")
        
        # Проверка существования директории static
        static_dir = os.path.join(project_root, 'frontend', 'static')
        if not os.path.exists(static_dir):
            logger.warning(f"Директория static не найдена по пути: {static_dir}")
            os.makedirs(static_dir, exist_ok=True)
            logger.info(f"Создана директория static: {static_dir}")
            
            # Создаем директории для js и css
            os.makedirs(os.path.join(static_dir, 'js'), exist_ok=True)
            os.makedirs(os.path.join(static_dir, 'css'), exist_ok=True)
            logger.info(f"Созданы поддиректории в static/")
        
        return {
            "root": project_root,
            "frontend": frontend_dir,
            "index": index_path,
            "static": static_dir
        }
    except Exception as e:
        logger.error(f"Критическая ошибка при проверке путей к frontend: {e}")
        # Возвращаем пути по умолчанию
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return {
            "root": project_root,
            "frontend": os.path.join(project_root, 'frontend'),
            "index": os.path.join(project_root, 'frontend', 'index.html'),
            "static": os.path.join(project_root, 'frontend', 'static')
        }

# Получаем пути для frontend ресурсов
frontend_paths = get_frontend_paths()

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory=frontend_paths["static"]), name="static")

@app.get("/", include_in_schema=False)
async def read_index():
    """
    Обработчик корневого пути - возвращает главную страницу приложения.
    """
    try:
        return FileResponse(frontend_paths["index"])
    except Exception as e:
        logger.error(f"Ошибка при попытке вернуть index.html: {e}")
        # Возвращаем ошибку в виде HTML страницы
        error_html = """
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <title>Ошибка</title>
            <style>body{font-family:sans-serif;margin:40px;text-align:center;}h1{color:#e74c3c;}</style>
        </head>
        <body>
            <h1>Ошибка при загрузке приложения</h1>
            <p>Не удалось загрузить главную страницу приложения. Пожалуйста, убедитесь, что все файлы установлены корректно.</p>
        </body>
        </html>
        """
        return JSONResponse(
            content={"error": f"Ошибка при загрузке index.html: {str(e)}"},
            status_code=500
        )

# --- Обработчики исключений ---
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTP ошибка {exc.status_code}: {exc.detail} для {request.method} {request.url}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Получаем трассировку исключения без раскрытия в ответе
    import traceback
    error_trace = traceback.format_exc()
    error_type = type(exc).__name__
    
    # Проверяем, содержится ли в исключении или трассировке чувствительная информация
    sensitive_patterns = ["password", "token", "secret", "key", "auth", "credential"]
    
    # Фильтруем трассировку для логов
    safe_trace_for_logs = error_trace
    for pattern in sensitive_patterns:
        if pattern in safe_trace_for_logs.lower():
            # Заменяем чувствительные данные в логах
            safe_trace_for_logs = safe_trace_for_logs.replace(pattern, f"***{pattern}***")

    # Определяем, является ли ошибка связанной с базой данных
    is_db_error = "database" in str(exc).lower() or "sql" in str(exc).lower()
    is_network_error = "network" in str(exc).lower() or "connection" in str(exc).lower()
    
    # Создаем идентификатор ошибки для отслеживания
    import uuid
    error_id = str(uuid.uuid4())
    
    # Получаем дополнительную информацию о контексте запроса
    request_info = {
        "method": request.method,
        "url": str(request.url),
        "client_ip": request.client.host if hasattr(request, "client") and request.client else "unknown",
        "headers": dict(request.headers.items()),
        "path_params": request.path_params,
        "query_params": dict(request.query_params.items())
    }
    
    # Убираем чувствительные данные из заголовков
    if "authorization" in request_info["headers"]:
        request_info["headers"]["authorization"] = "***REDACTED***"
    
    try:
        # Пытаемся получить body запроса для большей информативности
        if request.method in ["POST", "PUT", "PATCH"]:
            body_position = request.body_iterator._cursor
            request_body = await request.body()
            
            # Попытка декодировать тело запроса, если оно есть
            if request_body:
                try:
                    decoded_body = request_body.decode("utf-8")
                    # Проверяем, похоже ли тело на JSON
                    if decoded_body.strip().startswith("{") or decoded_body.strip().startswith("["):
                        import json
                        body_json = json.loads(decoded_body)
                        # Редактируем чувствительные данные в JSON
                        if isinstance(body_json, dict):
                            for key in list(body_json.keys()):
                                if any(pattern in key.lower() for pattern in sensitive_patterns):
                                    body_json[key] = "***REDACTED***"
                        request_info["body"] = body_json
                    else:
                        # Для не-JSON ограничиваем размер и редактируем чувствительные данные
                        request_info["body"] = "***BINARY DATA***" if len(decoded_body) > 1000 else decoded_body
                except (UnicodeDecodeError, json.JSONDecodeError):
                    request_info["body"] = "***BINARY OR INVALID DATA***"
            
            # Восстанавливаем позицию итератора тела
            request.body_iterator._cursor = body_position
    except Exception as body_err:
        # Если что-то пошло не так при получении body
        request_info["body_error"] = str(body_err)
    
    # Логируем полную информацию об ошибке для отладки
    logger.error(
        f"[Error ID: {error_id}] Внутренняя ошибка сервера при обработке {request.method} {request.url}\n"
        f"Тип ошибки: {error_type}\n"
        f"Сообщение: {str(exc)}\n"
        f"Контекст запроса: {request_info}\n"
        f"Трассировка:\n{safe_trace_for_logs}"
    )
    
    # Формируем более информативное и безопасное сообщение для пользователя
    if is_db_error:
        user_message = "Произошла ошибка при работе с базой данных. Попробуйте позже."
    elif is_network_error:
        user_message = "Произошла ошибка сети. Проверьте подключение и попробуйте позже."
    elif "timeout" in str(exc).lower():
        user_message = "Превышено время ожидания ответа. Возможно, сервер перегружен. Попробуйте позже или уменьшите размер запроса."
    elif "memory" in str(exc).lower() or "oom" in str(exc).lower() or "out of memory" in str(exc).lower():
        user_message = "Недостаточно памяти на сервере для обработки запроса. Попробуйте запрос меньшего размера."
    elif "permission" in str(exc).lower() or "access" in str(exc).lower() or "forbidden" in str(exc).lower():
        user_message = "У вас недостаточно прав для выполнения этой операции."
    elif "not found" in str(exc).lower() or "не найден" in str(exc).lower():
        user_message = "Запрашиваемый ресурс не найден."
    elif "invalid" in str(exc).lower() or "validation" in str(exc).lower() or "неверный" in str(exc).lower():
        user_message = "Неверный формат данных в запросе. Проверьте правильность заполнения полей."
    else:
        user_message = "Внутренняя ошибка сервера. Пожалуйста, попробуйте позже."
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": user_message,
            "error_id": error_id,  # Включаем идентификатор для возможности отслеживания пользователем
            "error_type": error_type if settings.debug else None,  # Включаем тип ошибки только в режиме отладки
        },
    )

# --- API Router (для префикса /api/v1) ---
# Используем APIRouter для удобства добавления префикса
api_router = APIRouter(prefix="/api/v1")


# --- Аутентификация и авторизация ---
@api_router.post("/token", response_model=Token, tags=["Auth"])
async def login_for_access_token(credentials: HTTPBasicCredentials = Depends(HTTPBasic()), request: Request = None):
    """Получение JWT-токена по учетным данным."""
    ip_address = request.client.host if request else None
    user = auth.authenticate_user(credentials.username, credentials.password, ip_address)
    if not user:
        # Проверяем различные условия блокировки
        if auth.is_account_locked(credentials.username):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Слишком много неудачных попыток входа. Пожалуйста, попробуйте позже.",
                headers={"WWW-Authenticate": "Basic", "Retry-After": str(auth.LOCKOUT_TIME)},
            )
        
        if ip_address and auth.is_ip_blocked(ip_address):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Слишком много неудачных попыток входа с вашего IP. Пожалуйста, попробуйте позже.",
                headers={"WWW-Authenticate": "Basic", "Retry-After": str(auth.LOCKOUT_TIME)},
            )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    # Создаем данные для токена
    token_data = {
        "sub": user["username"],
        "is_admin": user["is_admin"]
    }
    
    # Создаем токен
    access_token_expires = timedelta(minutes=settings.token_expire_minutes)
    access_token = auth.create_access_token(
        data=token_data, expires_delta=access_token_expires
    )
    
    # Логируем успешную авторизацию (без вывода чувствительных данных)
    logger.info(f"Пользователь {user['username']} (admin: {user['is_admin']}) успешно авторизовался и получил токен")
    
    return {"access_token": access_token, "token_type": "bearer"}

@api_router.get("/users/me", response_model=User, tags=["Auth"])
async def read_users_me(current_user: User = Depends(auth.get_current_active_user)):
    """Получение информации о текущем пользователе."""
    return current_user

# --- Эндпоинты Статуса и Конфигурации ---

@api_router.get("/status", tags=["Статус"], summary="Проверка работоспособности API")
async def get_status():
    """
    Возвращает простой JSON объект, подтверждающий, что API работает.
    Используется для мониторинга и health check.
    """
    logger.debug("API: Запрос статуса")
    return {"status": "ok", "message": "Промт Арена API v1 работает!"}

@api_router.get("/config/providers", tags=["Конфигурация"], summary="Получение списка поддерживаемых провайдеров")
async def get_supported_providers() -> Dict[str, str]:
    """
    Возвращает словарь поддерживаемых провайдеров LLM.
    Ключ - идентификатор провайдера (используется в API), Значение - отображаемое имя.
    """
    logger.debug("API: Запрос списка поддерживаемых провайдеров")
    return SUPPORTED_PROVIDERS

@api_router.get("/config/access-links", tags=["Конфигурация"], summary="Получение ссылок для доступа к приложению")
async def get_access_links(current_user: User = Depends(auth.get_admin_user)):
    """
    Возвращает ссылки для доступа к приложению.
    Требует авторизации административного пользователя.
    """
    return utils.generate_access_links(port=settings.port, secure=False)

# --- Эндпоинты для API Ключей ---

@api_router.post(
    "/keys",
    response_model=ApiKeyRead,
    status_code=status.HTTP_201_CREATED,
    tags=["API Ключи"],
    summary="Добавить или обновить API ключ",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Неверные данные запроса (например, неподдерживаемый провайдер)"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Ошибка сохранения ключа на сервере"},
    }
)
async def add_api_key(
    api_key_data: ApiKeyCreate,
    current_user: User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(database.get_db)
):
    """
    Добавляет или обновляет API ключ для указанного LLM провайдера.

    - **provider**: Идентификатор провайдера (e.g., 'openai', 'google'). Должен быть из списка `/config/providers`.
    - **api_key**: Сам API ключ. Ключ будет зашифрован перед сохранением в БД.

    При успехе возвращает информацию о ключе (без самого ключа) и статус 201.
    Если ключ для провайдера уже существует, он будет обновлен.
    """
    logger.info(f"API: Запрос на добавление/обновление ключа для {api_key_data.provider}")
    try:
        created_key_info = await data_logic.add_or_update_api_key(db, api_key_data, current_user.username)
        
        # Очищаем кеш моделей для этого провайдера
        await models_io.clear_models_cache(api_key_data.provider)
        
        return created_key_info
    except ValueError as e:
        logger.warning(f"Ошибка добавления ключа: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    # Ошибка 500 будет поймана generic_exception_handler

@api_router.get(
    "/keys",
    response_model=List[ApiKeyRead],
    tags=["API Ключи"],
    summary="Получить список добавленных API ключей"
)
async def get_api_keys(
    current_user: User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(database.get_db)
):
    """
    Возвращает список всех API ключей, сохраненных пользователем.
    **Внимание:** Сами ключи не возвращаются, только информация о них (ID, провайдер).
    """
    logger.debug("API: Запрос списка добавленных ключей")
    keys = await data_logic.list_api_keys(db)
    return keys

@api_router.delete(
    "/keys/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["API Ключи"],
    summary="Удалить API ключ",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Ключ для указанного провайдера не найден"},
    }
)
async def delete_api_key(
    provider: str = Path(..., description="Идентификатор провайдера, ключ которого нужно удалить.", examples=["openai", "google"]),
    current_user: User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(database.get_db)
):
    """
    Удаляет API ключ для указанного провайдера.
    При успехе возвращает статус 204 No Content (пустое тело ответа).
    """
    logger.info(f"API: Запрос на удаление ключа для провайдера {provider}")
    deleted = await data_logic.remove_api_key(db, provider)
    if not deleted:
        logger.warning(f"API: Ключ для провайдера {provider} не найден для удаления.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Ключ для провайдера '{provider}' не найден.")
    
    # Очищаем кеш моделей для этого провайдера
    await models_io.clear_models_cache(provider)
    
    return None # FastAPI автоматически вернет 204

@api_router.post(
    "/keys/{provider}/clear-cache",
    status_code=status.HTTP_200_OK,
    tags=["API Ключи"],
    summary="Очистить кеш моделей для провайдера после обновления ключа",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Провайдер не найден"},
    }
)
async def clear_provider_cache(
    provider: str = Path(..., description="Идентификатор провайдера, для которого нужно обновить кеш моделей.", examples=["openai", "google"]),
    current_user: User = Depends(auth.get_current_active_user),
):
    """
    Очищает кеш моделей для указанного провайдера.
    Полезно вызывать после обновления API ключа, чтобы при следующем
    запросе моделей получить актуальный список.
    """
    logger.info(f"API: Запрос на очистку кеша моделей для провайдера {provider}")
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Провайдер '{provider}' не поддерживается.")
    
    try:
        await models_io.clear_models_cache(provider)
        return {"status": "success", "message": f"Кеш моделей для провайдера {provider} очищен."}
    except Exception as e:
        logger.error(f"Ошибка при очистке кеша для {provider}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при очистке кеша: {str(e)}"
        )

# --- Эндпоинты для системных промтов ---

@api_router.post(
    "/system-prompts",
    response_model=SystemPromptRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Системные промты"],
    summary="Добавить или обновить системный промт для модели"
)
async def add_system_prompt(
    prompt_data: SystemPromptCreate,
    current_user: User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(database.get_db)
):
    """
    Добавляет или обновляет системный промт для указанной модели.
    """
    logger.info(f"API: Запрос на добавление/обновление системного промта для модели {prompt_data.model_id}")
    try:
        saved_prompt = await data_logic.add_or_update_system_prompt(db, prompt_data, current_user.username)
        return saved_prompt
    except ValueError as e:
        logger.warning(f"Ошибка добавления системного промта: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@api_router.get(
    "/system-prompts",
    response_model=List[SystemPromptRead],
    tags=["Системные промты"],
    summary="Получить список всех системных промтов"
)
async def get_system_prompts(
    current_user: User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(database.get_db)
):
    """
    Возвращает список всех сохраненных системных промтов.
    """
    logger.debug("API: Запрос списка системных промтов")
    prompts = await data_logic.get_system_prompts(db)
    return prompts

@api_router.get(
    "/system-prompts/{model_id}",
    tags=["Системные промты"],
    summary="Получить системный промт для модели"
)
async def get_system_prompt(
    model_id: str = Path(..., description="ID модели, для которой нужно получить системный промт"),
    current_user: User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(database.get_db)
):
    """
    Возвращает текст системного промта для указанной модели.
    """
    logger.debug(f"API: Запрос системного промта для модели {model_id}")
    prompt = await database.get_system_prompt(db, model_id)
    return {"model_id": model_id, "prompt_text": prompt}

@api_router.delete(
    "/system-prompts/{model_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Системные промты"],
    summary="Удалить системный промт для модели"
)
async def delete_system_prompt(
    model_id: str = Path(..., description="ID модели, для которой нужно удалить системный промт"),
    current_user: User = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(database.get_db)
):
    """
    Удаляет системный промт для указанной модели.
    """
    logger.info(f"API: Запрос на удаление системного промта для модели {model_id}")
    deleted = await data_logic.remove_system_prompt(db, model_id)
    if not deleted:
        logger.warning(f"Системный промт для модели {model_id} не найден для удаления.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Системный промт для модели '{model_id}' не найден.")
    return None

# --- Эндпоинты для управления доступом ---
@api_router.get(
    "/access-links",
    tags=["Администрирование"],
    summary="Получить ссылки доступа к приложению"
)
async def get_access_links(
    current_user: User = Depends(auth.get_admin_user)
):
    """
    Возвращает ссылки для доступа к приложению.
    Доступно только для администраторов.
    """
    logger.info(f"Запрос ссылок доступа от пользователя {current_user.username}")
    
    # Получаем конфигурацию сервера
    port = settings.port
    host = settings.host
    is_secure = False  # Можно настроить через конфиг
    
    # Используем utils.generate_access_links для получения ссылок
    links = utils.generate_access_links(port=port, secure=is_secure)
    
    return links

# Монтируем API роутер
app.include_router(api_router)

# Добавляем маршрут для корневого URL и перенаправляем на frontend/index.html
@app.get("/", include_in_schema=False)
async def read_root():
    """Перенаправляет корневой URL на frontend/index.html"""
    return FileResponse(os.path.join(static_dir, "index.html"))

# Перехватываем все другие GET запросы и пытаемся отдать соответствующий статический файл
@app.get("/{path:path}", include_in_schema=False)
async def catch_all(path: str):
    """Обрабатывает все другие GET запросы, пытаясь отдать статические файлы"""
    # Проверяем, существует ли такой файл в директории static
    full_path = os.path.join(static_dir, path)
    if os.path.exists(full_path) and os.path.isfile(full_path):
        return FileResponse(full_path)
    
    # Если файл не найден, возвращаем 404
    raise HTTPException(status_code=404, detail="Файл не найден")

# Добавляем TrustedHostMiddleware, если указано
if trusted_hosts and trusted_hosts != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

# Добавляем RateLimitMiddleware для ограничения частоты запросов
app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.max_requests_per_minute,
    window_size=60
)

# Запуск приложения (если файл запущен напрямую)
if __name__ == "__main__":
    # Настраиваем логгер
    utils.setup_logger(log_level=settings.log_level, log_file=settings.log_file)
    
    # Выводим информацию о запуске
    logger.info(f"Запуск Промт Арены на {settings.host}:{settings.port}")
    
    # Запускаем uvicorn
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )