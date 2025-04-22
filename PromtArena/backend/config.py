# backend/config.py

import os
import logging
import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, HttpUrl, SecretStr, validator, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import secrets
import base64

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка базового логгера
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger(__name__)

# Определяем список поддерживаемых провайдеров
SUPPORTED_PROVIDERS: Dict[str, str] = {
    "openai": "OpenAI",
    "google": "Google AI",
    "anthropic": "Anthropic (Claude)",
    "mistral": "Mistral AI",
    "groq": "Groq",
    "huggingface_hub": "Hugging Face Hub",
    "openrouter": "OpenRouter",
    "together": "Together AI"
}

class Settings(BaseSettings):
    """
    Основные настройки приложения, загружаемые из переменных окружения.
    """
    # Конфигурация Pydantic Settings
    model_config = SettingsConfigDict(
        env_file='.env',          # Указываем файл .env
        env_file_encoding='utf-8', # Кодировка файла
        extra='ignore'            # Игнорировать лишние переменные в .env
    )

    # Настройки базы данных
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/prompt_arena.db",
        description="URL для подключения к базе данных SQLAlchemy (асинхронный драйвер)."
    )

    # Настройки сервера
    host: str = Field(default="0.0.0.0", description="Хост для запуска API сервера")
    port: int = Field(default=8000, description="Порт для запуска API сервера")
    debug: bool = Field(default=False, description="Режим отладки")
    trusted_hosts: List[str] = Field(default=["*"], description="Список доверенных хостов")
    
    # Настройки логирования
    log_level: str = Field(default="INFO", description="Уровень логирования (DEBUG, INFO, WARNING, ERROR)")
    log_file: Optional[str] = Field(default=None, description="Путь к файлу логов (если нужен)")

    # Настройки безопасности
    # Ключ для шифрования API ключей в базе данных
    encryption_key: str = Field(
        default=None, # Установим None, чтобы ключ генерировался, если не указан
        description="Ключ Fernet для шифрования API ключей в БД. Если не указан, будет сгенерирован случайно."
    )

    # Ключ для JWT токенов
    jwt_secret_key: SecretStr = Field(
        default=None, # Установим None, чтобы ключ генерировался, если не указан
        description="Секретный ключ для JWT-токенов. Если не указан, будет сгенерирован случайно."
    )

    # Секреты (необязательные, т.к. будут вводиться пользователем, но могут быть дефолтные)
    hugging_face_hub_token: Optional[SecretStr] = Field(default=None, description="Токен Hugging Face Hub API (опционально, можно задать и через UI)")
    openrouter_api_key: Optional[SecretStr] = Field(default=None, description="API ключ OpenRouter (опционально)")
    together_api_key: Optional[SecretStr] = Field(default=None, description="API ключ Together AI (опционально)")

    # Настройки CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:8000", "http://127.0.0.1:8000", "https://promt-arena.ru"],
        description="Список разрешенных источников CORS. Используйте конкретные домены вместо ['*']."
    )
    
    # Режим работы (dev/prod)
    is_production: bool = Field(
        default=False, 
        description="Режим продакшена (влияет на настройки безопасности)"
    )
    
    # Настройки авторизации
    auth_username: str = Field(default="admin", description="Имя пользователя для API авторизации")
    auth_password: str = Field(default="131313", description="Пароль для API авторизации")
    guest_username: str = Field(default="guest", description="Имя пользователя для гостевого доступа")
    guest_password: str = Field(default="13", description="Пароль для гостевого доступа")
    disable_auth: bool = Field(default=False, description="Отключить авторизацию API (для разработки)")
    token_expire_minutes: int = Field(default=1440, description="Время жизни токена в минутах (24 часа)")
    
    # Настройки SSL (для продакшена)
    use_ssl: bool = Field(default=False, description="Использовать SSL")
    ssl_cert_path: Optional[str] = Field(default=None, description="Путь к SSL сертификату")
    ssl_key_path: Optional[str] = Field(default=None, description="Путь к ключу SSL сертификата")
    
    # Настройки для инференса моделей
    default_max_tokens: int = Field(default=1024, description="Максимальное количество токенов по умолчанию")
    default_temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Температура генерации по умолчанию")
    default_system_prompt: str = Field(
        default="Ты — полезный ассистент.",
        description="Системный промт по умолчанию"
    )
    max_prompt_length: int = Field(default=16000, description="Максимальная длина промта в символах")
    
    # Настройки кеширования
    models_cache_ttl: int = Field(default=3600, description="Время жизни кеша моделей в секундах (1 час)")
    response_cache_ttl: int = Field(default=86400, description="Время жизни кеша ответов в секундах (24 часа)")
    
    # Настройки безопасности
    max_requests_per_minute: int = Field(default=60, description="Максимальное количество запросов в минуту")
    session_expiry: int = Field(default=86400, description="Время жизни сессии в секундах (24 часа)")

    # Версия приложения
    app_version: str = Field(default="0.1.0", description="Версия приложения")
    
    # Интеграция с другими сервисами
    enable_discord_webhooks: bool = Field(default=False, description="Включить отправку уведомлений в Discord")
    discord_webhook_url: Optional[SecretStr] = Field(default=None, description="URL вебхука Discord")
    
    # Настройки визуального редактора
    enable_visual_editor: bool = Field(default=True, description="Включить визуальный редактор кода")
    default_editor_theme: str = Field(default="vs", description="Тема для редактора кода по умолчанию")
    
    # Настройки продуктивности
    enable_prompt_templates: bool = Field(default=True, description="Включить шаблоны промтов")
    max_templates_per_user: int = Field(default=50, description="Максимальное количество шаблонов на пользователя")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Валидирует уровень логирования."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        level = str(v).upper()
        if level in valid_levels:
            # Обновляем уровень логгера сразу после валидации
            logging.getLogger().setLevel(level)
            for handler in logging.getLogger().handlers:
                handler.setLevel(level)
            logger.info(f"Уровень логирования установлен на: {level}")
            return level
        raise ValueError(f"Неверный уровень логирования: {v}. Допустимые значения: {valid_levels}")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v):
        """Простая проверка URL базы данных."""
        if not isinstance(v, str) or '://' not in v:
            raise ValueError(f"Неверный формат DATABASE_URL: {v}")
        # Проверяем наличие папки data для SQLite по умолчанию
        if v.startswith("sqlite") and "///./data/" in v:
            # Определяем относительный путь к data директории
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_file_dir)  # Поднимаемся на уровень выше
            data_dir = os.path.join(project_root, 'data')
            
            if not os.path.exists(data_dir):
                try:
                    os.makedirs(data_dir)
                    logger.info(f"Создана директория для базы данных SQLite: {data_dir}")
                except OSError as e:
                    logger.error(f"Не удалось создать директорию {data_dir}: {e}")
                    raise ValueError(f"Не удалось создать директорию {data_dir} для SQLite.")
            elif not os.path.isdir(data_dir):
                raise ValueError(f"Путь {data_dir} существует, но не является директорией.")
        return v

    # Валидатор для CORS_ORIGINS чтобы избежать использования '*' в production
    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, v, info):
        """Проверяет настройки CORS на безопасность."""
        # Получаем значение is_production из других полей
        is_production = info.data.get("is_production", False)
        
        # Если это production и в списке есть '*', выдаем предупреждение и заменяем на безопасные значения
        if is_production and '*' in v:
            logger.warning("⚠️ В режиме production обнаружен небезопасный CORS: '*'. Заменяем на безопасные значения.")
            return ["http://localhost:8000", "http://127.0.0.1:8000", "https://promt-arena.ru"]
        return v

# Инициализация настроек
settings = Settings()

# Генерируем случайные ключи если они не указаны
if not settings.encryption_key:
    logger.warning("ENCRYPTION_KEY не указан в .env. Генерируется случайный ключ.")
    # Генерируем случайный ключ для Fernet (должен быть URL-safe base64 строкой длиной 32 байта)
    random_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    # Обновляем значение в настройках
    settings.encryption_key = random_key
    logger.info("Сгенерирован случайный ключ шифрования. Рекомендуется сохранить его в .env файле.")

# Генерируем JWT секрет, если он не указан
if not settings.jwt_secret_key or settings.jwt_secret_key.get_secret_value() == "":
    logger.warning("JWT_SECRET_KEY не указан в .env. Генерируется случайный ключ.")
    # Генерируем случайный ключ для JWT (64 символа в hex)
    random_jwt_key = secrets.token_hex(32)
    # Обновляем значение в настройках
    settings.jwt_secret_key = SecretStr(random_jwt_key)
    logger.info("Сгенерирован случайный JWT ключ. Рекомендуется сохранить его в .env файле.")

# Инициализация Fernet для шифрования/дешифрования API ключей
try:
    fernet = Fernet(settings.encryption_key.encode())
    logger.info("Fernet шифрование успешно инициализировано")
except Exception as e:
    logger.error(f"Ошибка инициализации Fernet шифрования: {e}")
    logger.error("Возможно, ключ шифрования в переменной ENCRYPTION_KEY некорректен. "
                "Формат должен быть в URL-safe base64 кодировке, длиной 32 байта.")
    raise SystemExit("Критическая ошибка инициализации шифрования. Проверьте ENCRYPTION_KEY.")

# --- Модели данных для API (Data Transfer Objects - DTOs) ---

class ApiKeyBase(BaseModel):
    provider: str
    api_key: SecretStr

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v):
        """Проверяет, поддерживается ли провайдер."""
        if v not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Провайдер '{v}' не поддерживается. Доступные: {list(SUPPORTED_PROVIDERS.keys())}")
        return v

class ApiKeyCreate(ApiKeyBase):
    pass

class ApiKeyRead(BaseModel): # Убрали наследование от ApiKeyBase, чтобы не требовать api_key
    id: int
    provider: str
    # Не включаем api_key для чтения списка

    model_config = {
        "from_attributes": True  # Заменяет orm_mode в Pydantic v2
    }

class SystemPromptBase(BaseModel):
    """Базовая модель для системного промта модели."""
    model_id: str
    prompt_text: str
    
    model_config = {
        "protected_namespaces": ()  # Отключаем защищенное пространство имен для model_id
    }

class SystemPromptCreate(SystemPromptBase):
    pass

class SystemPromptRead(SystemPromptBase):
    id: int
    updated_at: datetime.datetime
    created_by: Optional[str] = None
    
    model_config = {
        "from_attributes": True
    }

class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    # Добавим поле категории для фильтрации
    category: Optional[str] = None # Например, 'Программирование', 'Текст', 'Чат'
    # Добавим поля для контекстной информации
    max_input_tokens: Optional[int] = None
    supports_system_prompt: bool = False
    supports_vision: bool = False
    supports_tools: bool = False

class InteractionRequest(BaseModel):
    model_id: str
    prompt: str
    # Опциональные параметры для модели
    max_tokens: Optional[int] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    # Новые параметры
    system_prompt: Optional[str] = None
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    presence_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    stop_sequences: Optional[List[str]] = None
    
    model_config = {
        "protected_namespaces": ()  # Отключаем защищенное пространство имен для model_id
    }

class InteractionResponse(BaseModel):
    model_id: str
    response: str
    error: Optional[str] = None
    # Добавим полезную информацию
    elapsed_time: Optional[float] = None
    token_count: Optional[dict] = None
    
    model_config = {
        "protected_namespaces": ()  # Отключаем защищенное пространство имен для model_id
    }

class ComparisonRequest(BaseModel):
    model_id_1: str
    model_id_2: str
    prompt: str
    max_tokens: Optional[int] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    # Новые параметры
    system_prompt_1: Optional[str] = None
    system_prompt_2: Optional[str] = None
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    presence_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    stop_sequences: Optional[List[str]] = None
    
    model_config = {
        "protected_namespaces": ()  # Отключаем защищенное пространство имен для model_id_1 и model_id_2
    }

class ComparisonResponse(BaseModel):
    response_1: InteractionResponse
    response_2: InteractionResponse

class RatingBase(BaseModel):
    model_id: str
    prompt_text: str # Полный текст промта для хеширования
    rating: int = Field(ge=1, le=10)
    
    model_config = {
        "protected_namespaces": ()  # Отключаем защищенное пространство имен для model_id
    }

class RatingCreate(RatingBase):
    comparison_winner: Optional[str] = None # 'model_1', 'model_2', 'tie'
    user_identifier: Optional[str] = None # Session ID or User ID
    # Добавим новые поля для детального анализа
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

class RatingRead(RatingBase):
    id: int
    prompt_hash: str # Хеш промта, который хранится в БД
    timestamp: datetime.datetime # Используем datetime для ясности
    comparison_winner: Optional[str] = None
    user_identifier: Optional[str] = None
    # Новые поля
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    model_config = {
        "from_attributes": True  # Заменяет orm_mode в Pydantic v2
    }

class LeaderboardEntry(BaseModel):
    rank: int # Добавим ранг
    model_id: str
    name: str
    provider: str
    category: Optional[str] = None # Категория модели
    average_rating: float
    rating_count: int
    
    model_config = {
        "protected_namespaces": ()  # Отключаем защищенное пространство имен для model_id
    }

class CategoryInfo(BaseModel):
    """Структура для описания категории и подкатегорий."""
    id: str # Уникальный ID категории (e.g., "programming")
    name: str # Отображаемое имя (e.g., "Программирование")
    subcategories: Optional[List['CategoryInfo']] = None # Рекурсивно для подкатегорий

class PromptTemplateBase(BaseModel):
    """Базовая модель для шаблона промта."""
    name: str = Field(..., description="Название шаблона")
    prompt_text: str = Field(..., description="Текст шаблона промта")
    description: Optional[str] = Field(None, description="Описание шаблона")
    tags: Optional[str] = Field(None, description="Теги шаблона через запятую")
    is_public: bool = Field(True, description="Доступен ли шаблон всем пользователям")

class PromptTemplateCreate(PromptTemplateBase):
    """Модель для создания шаблона промта."""
    pass

class PromptTemplateRead(PromptTemplateBase):
    """Модель для чтения шаблона промта."""
    id: int
    created_by: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    
    model_config = {
        "from_attributes": True
    }

class PromptTemplateUpdate(BaseModel):
    """Модель для обновления шаблона промта."""
    name: Optional[str] = None
    prompt_text: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    is_public: Optional[bool] = None

# Модели для JWT-токенов аутентификации
class Token(BaseModel):
    access_token: str
    token_type: str
    
class TokenData(BaseModel):
    username: str
    is_admin: bool = False
    exp: Optional[datetime.datetime] = None

class User(BaseModel):
    username: str
    is_admin: bool = False