# backend/models_io.py

import asyncio
import logging
import time
import functools
import hashlib
from typing import List, Optional, Dict, Tuple, Any, Set, Callable, Union
import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
import os
import socket
import json
import importlib
import sys
import pkg_resources

# Настройка логгера
logger = logging.getLogger(__name__)

# Вспомогательная функция для безопасного импорта с подробной информацией об ошибке
def safe_import(module_name, as_object=False):
    try:
        module = importlib.import_module(module_name)
        logger.debug(f"Успешно импортирован модуль '{module_name}'")
        return module if as_object else True
    except ImportError as e:
        logger.error(f"Ошибка импорта '{module_name}': {e}")
        return None if as_object else False
    except Exception as e:
        logger.error(f"Неожиданная ошибка при импорте '{module_name}': {e}")
        return None if as_object else False

# Проверка версии huggingface_hub
def check_huggingface_version():
    try:
        # Проверяем установленную версию
        installed_packages = pkg_resources.working_set
        for pkg in installed_packages:
            if pkg.key == 'huggingface-hub':
                logger.info(f"Hugging Face Hub версия: {pkg.version}")
                if pkg.version != "0.23.0":
                    logger.warning(f"Установлена версия {pkg.version}, но требуется 0.23.0")
                    return False
                return True
        logger.error("Hugging Face Hub не найден в установленных пакетах")
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке версии huggingface_hub: {e}")
        return False

# Явная первичная попытка импорта huggingface_hub с диагностикой
huggingface_hub_module = safe_import('huggingface_hub', as_object=True)
if huggingface_hub_module:
    # Проверяем версию
    version = getattr(huggingface_hub_module, '__version__', 'неизвестно')
    logger.info(f"Модуль huggingface_hub успешно импортирован, версия: {version}")
    logger.info(f"Путь к huggingface_hub: {getattr(huggingface_hub_module, '__file__', 'не определен')}")
    
    # Если версия не та, которая нам нужна
    if version != "0.23.0":
        logger.warning(f"Неправильная версия huggingface_hub: {version}, требуется 0.23.0")
        # Попытка переустановки правильной версии
        try:
            logger.info("Попытка переустановки huggingface_hub с правильной версией...")
            import subprocess
            result = subprocess.run([sys.executable, "-m", "pip", "install", "--force-reinstall", "--no-deps", "huggingface_hub==0.23.0"], 
                                   check=True, capture_output=True, text=True)
            logger.info(f"Результат переустановки: {result.stdout}")
            # Перезагрузка модуля
            if 'huggingface_hub' in sys.modules:
                del sys.modules['huggingface_hub']
            huggingface_hub_module = importlib.import_module('huggingface_hub')
            version = getattr(huggingface_hub_module, '__version__', 'неизвестно')
            logger.info(f"Модуль huggingface_hub перезагружен, версия: {version}")
        except Exception as e:
            logger.error(f"Ошибка при переустановке huggingface_hub: {e}")
else:
    logger.error("КРИТИЧЕСКИ ВАЖНЫЙ ИМПОРТ 'huggingface_hub' НЕУДАЧЕН.")
    logger.error("Проверяем список установленных пакетов...")
    try:
        import pkg_resources
        installed_packages = [pkg.key for pkg in pkg_resources.working_set]
        logger.info(f"Установлены следующие пакеты: {', '.join(installed_packages)}")
        
        if 'huggingface-hub' in installed_packages:
            logger.info("Пакет huggingface-hub найден в установленных, но импорт не работает. Возможно, проблема с путями импорта.")
        else:
            logger.error("Пакет huggingface-hub НЕ найден в установленных пакетах.")
    except ImportError:
        logger.error("Не удалось проверить список установленных пакетов.")

# Импорты библиотек провайдеров
try:
    from openai import AsyncOpenAI, OpenAIError, AuthenticationError as OpenAIAuthenticationError, NotFoundError as OpenAINotFoundError, RateLimitError as OpenAIRateLimitError
except ImportError:
    AsyncOpenAI = None # type: ignore
    OpenAIError = Exception # type: ignore
    OpenAIAuthenticationError = Exception # type: ignore
    OpenAINotFoundError = Exception # type: ignore
    OpenAIRateLimitError = Exception # type: ignore
    logging.warning("Библиотека 'openai' не установлена. Функциональность OpenAI будет недоступна.")

try:
    import google.generativeai as genai
    from google.api_core.exceptions import ClientError as GoogleClientError, Unauthenticated as GoogleUnauthenticated, PermissionDenied as GooglePermissionDenied, NotFound as GoogleNotFound
except ImportError:
    genai = None # type: ignore
    GoogleClientError = Exception # type: ignore
    GoogleUnauthenticated = Exception # type: ignore
    GooglePermissionDenied = Exception # type: ignore
    GoogleNotFound = Exception # type: ignore
    logging.warning("Библиотека 'google-generativeai' не установлена. Функциональность Google AI будет недоступна.")

try:
    from anthropic import AsyncAnthropic, AnthropicError, AuthenticationError as AnthropicAuthenticationError, NotFoundError as AnthropicNotFoundError, RateLimitError as AnthropicRateLimitError
except ImportError:
    AsyncAnthropic = None # type: ignore
    AnthropicError = Exception # type: ignore
    AnthropicAuthenticationError = Exception # type: ignore
    AnthropicNotFoundError = Exception # type: ignore
    AnthropicRateLimitError = Exception # type: ignore
    logging.warning("Библиотека 'anthropic' не установлена. Функциональность Anthropic (Claude) будет недоступна.")

try:
    from mistralai.client import MistralClient # У Mistral пока нет официального async клиента, используем sync в executor или aiohttp
    from mistralai.async_client import MistralAsyncClient
    from mistralai.exceptions import MistralException, MistralAPIException, MistralConnectionException, MistralAPIStatusException
except ImportError:
    MistralAsyncClient = None # type: ignore
    MistralException = Exception # type: ignore
    MistralAPIException = Exception # type: ignore
    MistralConnectionException = Exception # type: ignore
    MistralAPIStatusException = Exception # type: ignore
    logging.warning("Библиотека 'mistralai' не установлена. Функциональность Mistral AI будет недоступна.")

try:
    from groq import AsyncGroq, GroqError, AuthenticationError as GroqAuthenticationError, NotFoundError as GroqNotFoundError, RateLimitError as GroqRateLimitError
except ImportError:
    AsyncGroq = None # type: ignore
    GroqError = Exception # type: ignore
    GroqAuthenticationError = Exception # type: ignore
    GroqNotFoundError = Exception # type: ignore
    GroqRateLimitError = Exception # type: ignore
    logging.warning("Библиотека 'groq' не установлена. Функциональность Groq будет недоступна.")

# Повторная попытка импорта huggingface_hub после нашей диагностики
try:
    # Если модуль уже успешно импортирован, используем его
    if huggingface_hub_module:
        AsyncInferenceClient = huggingface_hub_module.AsyncInferenceClient
        HfApi = huggingface_hub_module.HfApi
        RepositoryNotFoundError = huggingface_hub_module.utils.RepositoryNotFoundError
        GatedRepoError = huggingface_hub_module.utils.GatedRepoError
        HFValidationError = huggingface_hub_module.utils.HFValidationError
        
        # Проверяем, существует ли InferenceTimeoutError в версии 0.23.0
        # В этой версии он может находиться в другом месте или отсутствовать
        try:
            # Попытка импорта из модуля inference
            if hasattr(huggingface_hub_module.inference, "InferenceTimeoutError"):
                InferenceTimeoutError = huggingface_hub_module.inference.InferenceTimeoutError
            # Попытка импорта из _common если существует
            elif hasattr(huggingface_hub_module.inference, "_common") and hasattr(huggingface_hub_module.inference._common, "InferenceTimeoutError"):
                InferenceTimeoutError = huggingface_hub_module.inference._common.InferenceTimeoutError
            # Создаем заглушку если не найден
            else:
                logger.warning("InferenceTimeoutError не найден в huggingface_hub v0.23.0, создаем заглушку")
                class InferenceTimeoutError(Exception):
                    """Заглушка для InferenceTimeoutError."""
                    pass
        except AttributeError:
            logger.warning("Структура huggingface_hub отличается, создаем заглушку для InferenceTimeoutError")
            class InferenceTimeoutError(Exception):
                """Заглушка для InferenceTimeoutError."""
                pass
        
        logger.info("Успешно импортированы классы из имеющегося модуля huggingface_hub")
    else:
        # Иначе пытаемся импортировать явно
        from huggingface_hub import AsyncInferenceClient, HfApi
        from huggingface_hub.utils import RepositoryNotFoundError, GatedRepoError, HFValidationError
        
        # Создаем заглушку для InferenceTimeoutError
        class InferenceTimeoutError(Exception):
            """Заглушка для InferenceTimeoutError."""
            pass
        
        logger.info("Успешно импортированы классы из huggingface_hub напрямую")
except ImportError as e:
    logger.error(f"Ошибка импорта классов из huggingface_hub: {e}")
    # Пытаемся установить пакет внутри скрипта (это экстренное решение)
    try:
        logger.warning("Попытка автоматической установки huggingface_hub...")
        import subprocess
        # Принудительная установка с --no-deps для предотвращения конфликтов зависимостей
        result = subprocess.run([sys.executable, "-m", "pip", "install", "--force-reinstall", "--no-deps", "huggingface_hub==0.23.0"], 
                               check=True, capture_output=True, text=True)
        logger.info(f"Результат установки: {result.stdout}")
        
        # Очистка кеша импорта если модуль уже был загружен
        if 'huggingface_hub' in sys.modules:
            del sys.modules['huggingface_hub']
        
        # Пробуем импортировать после установки
        from huggingface_hub import AsyncInferenceClient, HfApi
        from huggingface_hub.utils import RepositoryNotFoundError, GatedRepoError, HFValidationError
        
        # Создаем заглушку для InferenceTimeoutError вместо импорта
        class InferenceTimeoutError(Exception):
            """Заглушка для InferenceTimeoutError."""
            pass
            
        logger.info("huggingface_hub успешно установлен и импортирован автоматически!")
    except Exception as install_error:
        AsyncInferenceClient = None # type: ignore
        HfApi = None # type: ignore
        RepositoryNotFoundError = Exception # type: ignore
        GatedRepoError = Exception # type: ignore
        HFValidationError = Exception # type: ignore
        InferenceTimeoutError = Exception # type: ignore
        logger.error(f"Автоматическая установка huggingface_hub не удалась: {install_error}")
        logger.error("Библиотека 'huggingface_hub' не установлена. Функциональность Hugging Face будет недоступна.")
except Exception as e:
    AsyncInferenceClient = None # type: ignore
    HfApi = None # type: ignore
    RepositoryNotFoundError = Exception # type: ignore
    GatedRepoError = Exception # type: ignore
    HFValidationError = Exception # type: ignore
    InferenceTimeoutError = Exception # type: ignore
    logger.error(f"Неожиданная ошибка при импорте huggingface_hub: {e}")


# Импорты из нашего проекта
from backend import database
from backend.config import (
    settings, ModelInfo, InteractionRequest, InteractionResponse,
    ComparisonRequest, ComparisonResponse, SUPPORTED_PROVIDERS
)

logger = logging.getLogger(__name__)

# --- Кеширование ответов ---
class ResponseCache:
    """Простая реализация кеша в памяти."""
    def __init__(self, ttl: int = 3600):
        self.cache = {}
        self.ttl = ttl  # время жизни кеша в секундах
    
    def get(self, key: str) -> Optional[Any]:
        """Получает элемент из кеша по ключу."""
        if key in self.cache:
            entry, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return entry
            # Если время истекло, удаляем запись
            del self.cache[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Устанавливает элемент в кеш с текущим временем."""
        self.cache[key] = (value, time.time())
    
    def clear(self, prefix: Optional[str] = None) -> None:
        """Очищает кеш или его часть по префиксу."""
        if prefix is None:
            self.cache = {}
        else:
            self.cache = {k: v for k, v in self.cache.items() if not k.startswith(prefix)}

# Создаем экземпляр кеша ответов
response_cache = ResponseCache(ttl=settings.response_cache_ttl)

# --- Вспомогательные функции ---

def _parse_model_id(full_model_id: str) -> Tuple[str, str]:
    """Разбирает полный ID модели (e.g., 'openai/gpt-4o') на провайдера и имя."""
    if '/' not in full_model_id:
        # По умолчанию считаем Hugging Face, если нет префикса
        # Или можно выбросить ошибку, если формат неверный
        logger.warning(f"Неверный формат model_id '{full_model_id}'. Предполагается Hugging Face.")
        return "huggingface_hub", full_model_id
    provider, model_name = full_model_id.split('/', 1)
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Неподдерживаемый провайдер '{provider}' в ID модели '{full_model_id}'")
    return provider, model_name

async def _get_provider_client(db: AsyncSession, provider: str) -> Optional[Any]:
    """Получает API ключ и инициализирует асинхронный клиент для провайдера."""
    api_key = await database.get_api_key(db, provider)
    if not api_key:
        # Отдельно проверяем токен HF из настроек, если он есть
        if provider == "huggingface_hub" and settings.hugging_face_hub_token:
             api_key = settings.hugging_face_hub_token.get_secret_value()
             logger.debug("Используется токен Hugging Face из настроек.")
        else:
            logger.warning(f"API ключ для провайдера '{provider}' не найден в БД.")
            return None

    try:
        if provider == "openai" and AsyncOpenAI:
            return AsyncOpenAI(api_key=api_key)
        elif provider == "google" and genai:
            # У Google нет явного async клиента для list_models, но есть для generate_content_async
            # Настроим ключ для использования в genai.configure и вернем сам ключ для list_models
            genai.configure(api_key=api_key)
            return api_key # Возвращаем ключ для list_models, а generate_content_async будет использовать настроенный
        elif provider == "anthropic" and AsyncAnthropic:
            return AsyncAnthropic(api_key=api_key)
        elif provider == "mistral" and MistralAsyncClient:
            return MistralAsyncClient(api_key=api_key)
        elif provider == "groq" and AsyncGroq:
            return AsyncGroq(api_key=api_key)
        elif provider == "huggingface_hub" and AsyncInferenceClient:
            # Для листинга моделей может понадобиться HfApi, для инференса - AsyncInferenceClient
            # Вернем кортеж или словарь
            return {"inference": AsyncInferenceClient(token=api_key), "api": HfApi(token=api_key)}
        else:
            logger.error(f"Клиент для провайдера '{provider}' не может быть инициализирован (библиотека не установлена?).")
            return None
    except Exception as e:
        logger.exception(f"Ошибка инициализации клиента для провайдера {provider}: {e}", exc_info=e)
        return None

def _guess_category(provider: str, model_name: str) -> Optional[str]:
    """Простая эвристика для определения категории модели."""
    model_name_lower = model_name.lower()
    
    # Категории на основе провайдера
    if provider in ["openai", "anthropic", "google", "mistral", "groq"]:
        # Определение категории по имени модели
        if "vision" in model_name_lower or "claude-3" in model_name_lower:
            return "multimodal"
        if "code" in model_name_lower or "codex" in model_name_lower:
            return "programming"
        if "embedding" in model_name_lower:
            return "embeddings"
        return "text_generation"  # Категория по умолчанию для этих провайдеров
    
    # Более детальное определение для Hugging Face
    if provider == "huggingface_hub":
        if "code" in model_name_lower or "coder" in model_name_lower:
            return "programming"
        if "translate" in model_name_lower or "translation" in model_name_lower:
            return "text_translation"
        if "summarization" in model_name_lower or "summary" in model_name_lower:
            return "text_summary"
        if "ocr" in model_name_lower or "text-detection" in model_name_lower:
            return "ocr"
        if "diffusion" in model_name_lower or "stable-diffusion" in model_name_lower:
            return "image_generation"
        if "chat" in model_name_lower or "instruct" in model_name_lower:
            return "text_generation"
    
    # Для неизвестных случаев возвращаем общую категорию
    return "text_generation"

def _get_model_metadata(provider: str, model_name: str) -> Dict[str, Any]:
    """Возвращает метаданные для модели (для внутреннего использования)."""
    # Определяем базовые метаданные
    metadata = {
        "max_input_tokens": None,
        "supports_system_prompt": False,
        "supports_vision": False,
        "supports_tools": False
    }
    
    # Обогащаем метаданные на основе провайдера и имени модели
    if provider == "openai":
        metadata["supports_system_prompt"] = True
        if "gpt-4" in model_name:
            metadata["max_input_tokens"] = 128000 if "128k" in model_name else 8192
            metadata["supports_tools"] = True
            metadata["supports_vision"] = "vision" in model_name or "-o" in model_name
        elif "gpt-3.5" in model_name:
            metadata["max_input_tokens"] = 16384 if "16k" in model_name else 4096
            metadata["supports_tools"] = "turbo" in model_name
    
    elif provider == "anthropic":
        metadata["supports_system_prompt"] = True
        if "claude-3" in model_name:
            metadata["max_input_tokens"] = 200000 if "opus" in model_name else 100000
            metadata["supports_vision"] = True
        elif "claude-2" in model_name:
            metadata["max_input_tokens"] = 100000
    
    elif provider == "google":
        metadata["supports_system_prompt"] = True
        if "gemini" in model_name:
            metadata["max_input_tokens"] = 30720 if "pro" in model_name else 8192
            metadata["supports_vision"] = "vision" in model_name or "pro" in model_name
    
    elif provider == "mistral":
        metadata["supports_system_prompt"] = True
        metadata["max_input_tokens"] = 32768 if "large" in model_name else 8192
        
    elif provider == "groq":
        metadata["supports_system_prompt"] = "llama" not in model_name.lower()
        metadata["max_input_tokens"] = 8192
    
    # Для Hugging Face метаданные сложно определить без запроса к API
    return metadata

# --- Кеширование и оптимизация ---

# Кеш для имен моделей, чтобы не опрашивать API постоянно
# формат: {provider: {model_name: ModelInfo, ...}, ...}
_models_cache: Dict[str, Dict[str, ModelInfo]] = {}
_last_cache_refresh: Dict[str, float] = {}
_CACHE_TTL = 3600  # Время жизни кеша в секундах (1 час)
_cache_lock = asyncio.Lock()  # Для синхронизации доступа к кешу

def model_cache(provider: str, ttl: int = _CACHE_TTL) -> Callable:
    """Декоратор для кеширования результатов fetch_*_models функций."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> List[ModelInfo]:
            global _models_cache, _last_cache_refresh
            
            current_time = time.time()
            
            # Используем блокировку для предотвращения race condition
            async with _cache_lock:
                if (provider not in _models_cache or 
                    provider not in _last_cache_refresh or 
                    current_time - _last_cache_refresh[provider] > ttl):
                    
                    # Вызываем оригинальную функцию для обновления кеша
                    logger.debug(f"Обновляем кеш моделей для провайдера {provider}")
                    try:
                        models = await func(*args, **kwargs)
                        
                        # Обновляем кеш
                        _models_cache[provider] = {model.id.split('/', 1)[1]: model for model in models}
                        _last_cache_refresh[provider] = current_time
                        return models
                    except Exception as e:
                        logger.error(f"Ошибка при обновлении кеша моделей для {provider}: {e}")
                        # Если в кеше уже есть данные, вернем их даже если обновление не удалось
                        if provider in _models_cache:
                            logger.info(f"Возвращаем устаревшие данные из кеша для {provider}")
                            return list(_models_cache[provider].values())
                        # Иначе пробросим исключение дальше
                        raise
                
                # Возвращаем закешированные данные
                logger.debug(f"Используем кеш моделей для провайдера {provider}")
                return list(_models_cache[provider].values())
        
        return wrapper
    return decorator

# Применяем декоратор к функциям _fetch_*_models
@model_cache("openai")
async def _fetch_openai_models(client: AsyncOpenAI) -> List[ModelInfo]:
    """Получает список моделей от OpenAI."""
    models_info = []
    if not client: return models_info
    
    try:
        models = await client.models.list()
        for model in models.data:
            # Фильтруем, оставляем в основном gpt модели
            if model.id.startswith("gpt-") or model.id.startswith("text-davinci"):
                # Получаем метаданные
                metadata = _get_model_metadata("openai", model.id)
                
                models_info.append(ModelInfo(
                    id=f"openai/{model.id}",
                    name=model.id, # OpenAI не дает красивых имен в API
                    provider="openai",
                    category=_guess_category("openai", model.id),
                    # Добавляем метаданные
                    max_input_tokens=metadata["max_input_tokens"],
                    supports_system_prompt=metadata["supports_system_prompt"],
                    supports_vision=metadata["supports_vision"],
                    supports_tools=metadata["supports_tools"]
                ))
        logger.info(f"Загружено {len(models_info)} моделей от OpenAI.")
    except OpenAIAuthenticationError:
        logger.error("Ошибка аутентификации OpenAI. Проверьте API ключ.")
        raise
    except OpenAIError as e:
        logger.error(f"Ошибка API OpenAI при получении списка моделей: {e}")
        raise
    except Exception as e:
        logger.exception(f"Неизвестная ошибка при получении моделей OpenAI: {e}", exc_info=True)
        raise
    return models_info

@model_cache("google")
async def _fetch_google_models(api_key: str) -> List[ModelInfo]:
    """Получает список моделей от Google AI."""
    models_info = []
    if not genai or not api_key: return models_info
    try:
        # genai.configure(api_key=api_key) # Уже сделано в _get_provider_client
        google_models = genai.list_models() # Используем синхронный вызов, т.к. нет async версии
        for model in google_models:
            # Фильтруем модели, поддерживающие генерацию контента ('generateContent')
            # и извлекаем только имя модели после 'models/'
            if 'generateContent' in model.supported_generation_methods and model.name.startswith("models/"):
                model_name = model.name.split("models/", 1)[1]
                # Исключаем 'embedding' модели
                if 'embedding' not in model_name.lower():
                    # Получаем метаданные
                    metadata = _get_model_metadata("google", model_name)
                    
                    models_info.append(ModelInfo(
                        id=f"google/{model_name}",
                        name=model.display_name or model_name,
                        provider="google",
                        category=_guess_category("google", model_name),
                        # Добавляем метаданные
                        max_input_tokens=metadata["max_input_tokens"],
                        supports_system_prompt=metadata["supports_system_prompt"],
                        supports_vision=metadata["supports_vision"],
                        supports_tools=metadata["supports_tools"]
                    ))
        logger.info(f"Загружено {len(models_info)} моделей от Google AI.")
    except (GoogleUnauthenticated, GooglePermissionDenied):
         logger.error("Ошибка аутентификации/авторизации Google AI. Проверьте API ключ.")
         raise
    except GoogleClientError as e:
        logger.error(f"Общая ошибка API Google AI при получении списка моделей: {e}")
        raise
    except Exception as e:
        logger.exception(f"Неизвестная ошибка при получении моделей Google AI: {e}", exc_info=True)
        raise
    return models_info

@model_cache("anthropic")
async def _fetch_anthropic_models(client: AsyncAnthropic) -> List[ModelInfo]:
    """Получает список моделей от Anthropic (Claude). У них нет API для этого, используем статический список."""
    models_info = []
    if not client: return models_info
    # API Anthropic не предоставляет эндпоинт для списка моделей. Используем известный список.
    known_models = [
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229", 
        "claude-3-haiku-20240307",
        "claude-3.5-sonnet-20240425",
        "claude-3.5-haiku-20240307",
        "claude-2.1",
        "claude-2.0",
        "claude-instant-1.2"
    ]
    
    for model_name in known_models:
        # Получаем метаданные
        metadata = _get_model_metadata("anthropic", model_name)
        
        models_info.append(ModelInfo(
            id=f"anthropic/{model_name}",
            name=model_name.replace("-", " ").title(), # Простое форматирование имени
            provider="anthropic",
            category=_guess_category("anthropic", model_name),
            # Добавляем метаданные
            max_input_tokens=metadata["max_input_tokens"],
            supports_system_prompt=metadata["supports_system_prompt"],
            supports_vision=metadata["supports_vision"],
            supports_tools=metadata["supports_tools"]
        ))
    
    logger.info(f"Загружен статический список из {len(models_info)} моделей Anthropic.")
    
    # Можно добавить проверку доступности одной из моделей, чтобы убедиться, что ключ рабочий
    try:
        # Попробуем сделать дешевый запрос для проверки ключа
        await client.messages.create(
            model=known_models[-1], # Берем самую быструю/дешевую
            messages=[{"role": "user", "content": "Ping"}],
            max_tokens=1
        )
        logger.info("API ключ Anthropic валиден.")
    except AnthropicAuthenticationError:
        logger.error("Ошибка аутентификации Anthropic. Проверьте API ключ.")
        raise
    except AnthropicRateLimitError:
         logger.warning("Превышен лимит запросов Anthropic при проверке ключа.")
         # Продолжаем, ключ скорее всего валиден
    except AnthropicError as e:
        logger.error(f"Ошибка API Anthropic при проверке ключа: {e}")
        # Ключ может быть валиден, но другая проблема. Оставляем модели.
    except Exception as e:
        logger.exception(f"Неизвестная ошибка при проверке ключа Anthropic: {e}", exc_info=True)

    return models_info

@model_cache("mistral")
async def _fetch_mistral_models(client: MistralAsyncClient) -> List[ModelInfo]:
    """Получает список моделей от Mistral AI."""
    models_info = []
    if not client: return models_info
    try:
        models_response = await client.list_models()
        for model in models_response.data:
            # Получаем метаданные
            metadata = _get_model_metadata("mistral", model.id)
            
            models_info.append(ModelInfo(
                id=f"mistral/{model.id}",
                name=model.id,
                provider="mistral",
                category=_guess_category("mistral", model.id),
                # Добавляем метаданные
                max_input_tokens=metadata["max_input_tokens"],
                supports_system_prompt=metadata["supports_system_prompt"],
                supports_vision=metadata["supports_vision"],
                supports_tools=metadata["supports_tools"]
            ))
        logger.info(f"Загружено {len(models_info)} моделей от Mistral AI.")
    except MistralAPIException as e:
        if e.status_code == 401:
             logger.error("Ошибка аутентификации Mistral AI. Проверьте API ключ.")
        else:
             logger.error(f"Ошибка API Mistral AI ({e.status_code}) при получении списка моделей: {e.message}")
        raise
    except MistralConnectionException as e:
         logger.error(f"Ошибка соединения с Mistral AI: {e}")
         raise
    except MistralException as e:
        logger.error(f"Ошибка Mistral AI при получении списка моделей: {e}")
        raise
    except Exception as e:
        logger.exception(f"Неизвестная ошибка при получении моделей Mistral AI: {e}", exc_info=True)
        raise
    return models_info

@model_cache("groq")
async def _fetch_groq_models(client: AsyncGroq) -> List[ModelInfo]:
    """Получает список моделей от Groq."""
    models_info = []
    if not client: return models_info
    # Groq использует формат OpenAI, получаем список моделей так же
    try:
        models = await client.models.list()
        for model in models.data:
            # Получаем метаданные
            metadata = _get_model_metadata("groq", model.id)
            
            models_info.append(ModelInfo(
                id=f"groq/{model.id}",
                name=model.id,
                provider="groq",
                category=_guess_category("groq", model.id),
                # Добавляем метаданные
                max_input_tokens=metadata["max_input_tokens"],
                supports_system_prompt=metadata["supports_system_prompt"],
                supports_vision=metadata["supports_vision"],
                supports_tools=metadata["supports_tools"]
            ))
        logger.info(f"Загружено {len(models_info)} моделей от Groq.")
    except GroqAuthenticationError:
        logger.error("Ошибка аутентификации Groq. Проверьте API ключ.")
        raise
    except GroqError as e:
        logger.error(f"Ошибка API Groq при получении списка моделей: {e}")
        raise
    except Exception as e:
        logger.exception(f"Неизвестная ошибка при получении моделей Groq: {e}", exc_info=True)
        raise
    return models_info

@model_cache("huggingface_hub")
async def _fetch_huggingface_models(clients: Dict[str, Any]) -> List[ModelInfo]:
    """Получает список моделей от Hugging Face Hub (текстовые модели)."""
    models_info = []
    if not HfApi or not clients or "api" not in clients: return models_info
    hf_api: HfApi = clients["api"]
    try:
        # Ищем популярные модели для text-generation и conversational
        # Ограничиваем количество для производительности
        models = list(hf_api.list_models(
            filter="text-generation", sort="downloads", direction=-1, limit=50, cardData=True
        ))
        models.extend(list(hf_api.list_models(
            filter="conversational", sort="downloads", direction=-1, limit=50, cardData=True
        )))
        # Добавим модели для кода
        models.extend(list(hf_api.list_models(
             filter="text2text-generation", tags="code", sort="downloads", direction=-1, limit=20, cardData=True
        )))

        seen_ids = set()
        for model in models:
            if model.modelId not in seen_ids:
                models_info.append(ModelInfo(
                    id=f"huggingface_hub/{model.modelId}",
                    name=model.modelId,
                    provider="huggingface_hub",
                    category=_guess_category("huggingface_hub", model.modelId),
                    # Метаданные для HF сложно определить без дополнительных запросов
                    max_input_tokens=None,
                    supports_system_prompt=False,
                    supports_vision=False,
                    supports_tools=False
                ))
                seen_ids.add(model.modelId)

        logger.info(f"Загружено {len(models_info)} моделей от Hugging Face Hub.")
    except HFValidationError:
         logger.error("Ошибка аутентификации Hugging Face Hub. Проверьте API токен.")
         raise
    except Exception as e:
        logger.exception(f"Ошибка при получении моделей Hugging Face Hub: {e}", exc_info=True)
        raise
    return models_info

# Также добавим функцию принудительного обновления кеша
async def clear_models_cache(provider: Optional[str] = None) -> None:
    """
    Очищает кеш моделей для указанного провайдера или для всех провайдеров.
    Полезно вызывать после обновления API ключа.
    """
    global _models_cache, _last_cache_refresh
    
    async with _cache_lock:
        if provider:
            if provider in _models_cache:
                del _models_cache[provider]
            if provider in _last_cache_refresh:
                del _last_cache_refresh[provider]
            logger.info(f"Кеш моделей для провайдера {provider} очищен.")
        else:
            _models_cache.clear()
            _last_cache_refresh.clear()
            logger.info("Кеш моделей для всех провайдеров очищен.")

# --- Оптимизируем функцию get_available_models_details ---

async def get_available_models_details(db: AsyncSession) -> List[ModelInfo]:
    """
    Получает информацию о доступных моделях от всех провайдеров,
    для которых есть API ключи. Результаты кешируются для оптимизации.
    """
    logger.info("Получение списка доступных моделей...")
    all_models: List[ModelInfo] = []

    # Получаем список провайдеров, для которых есть ключи
    from sqlalchemy import select
    stmt = select(database.ApiKey.provider)
    result = await db.execute(stmt)
    providers_with_keys = [row[0] for row in result.all()]
    
    # Добавляем HuggingFace, если есть токен в настройках
    if "huggingface_hub" not in providers_with_keys and settings.hugging_face_hub_token:
        providers_with_keys.append("huggingface_hub")
    
    if not providers_with_keys:
        logger.warning("Нет доступных API ключей для получения моделей.")
        return []
    
    # Создаем и запускаем задачи для каждого провайдера
    tasks = []
    logger.debug(f"Запрашиваем модели для провайдеров: {providers_with_keys}")
    
    for provider in providers_with_keys:
        # Получаем клиент для провайдера
        client = await _get_provider_client(db, provider)
        if not client:
            logger.warning(f"Не удалось создать клиент для {provider}. Пропускаем.")
            continue
        
        # Создаем задачу для получения моделей провайдера
        if provider == "openai":
            tasks.append(_fetch_openai_models(client))
        elif provider == "google":
            tasks.append(_fetch_google_models(client))
        elif provider == "anthropic":
            tasks.append(_fetch_anthropic_models(client))
        elif provider == "mistral":
            tasks.append(_fetch_mistral_models(client))
        elif provider == "groq":
            tasks.append(_fetch_groq_models(client))
        elif provider == "huggingface_hub":
            tasks.append(_fetch_huggingface_models(client))
        # Добавлять новых провайдеров здесь
    
    # Ожидаем завершения всех задач
    if tasks:
        # Используем gather с return_exceptions=True, чтобы одна ошибка не ломала всё
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обрабатываем результаты
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Ошибка при получении моделей: {result}")
            elif isinstance(result, list):
                all_models.extend(result)
    
    logger.info(f"Всего получено {len(all_models)} моделей от {len(tasks)} провайдеров.")
    return all_models


# --- Логика Выполнения Запросов к Моделям (Inference) ---

async def _infer_openai(client: AsyncOpenAI, model_name: str, prompt: str, params: Dict) -> Tuple[str, Dict]:
    """Выполняет запрос к OpenAI Chat Completion API."""
    if not client: 
        raise ValueError("Клиент OpenAI не инициализирован.")
        
    start_time = time.time()
    token_count = {"prompt": 0, "completion": 0, "total": 0}
    
    try:
        # Формируем сообщения
        messages = []
        
        # Добавляем системный промт, если есть
        if params.get("system_prompt"):
            messages.append({"role": "system", "content": params["system_prompt"]})
        
        # Добавляем основной промт
        messages.append({"role": "user", "content": prompt})
        
        # Собираем параметры запроса
        request_params = {
            "model": model_name,
            "messages": messages,
            "temperature": params.get("temperature"),
            "max_tokens": params.get("max_tokens"),
        }
        
        # Добавляем опциональные параметры, если они указаны
        if params.get("top_p") is not None:
            request_params["top_p"] = params["top_p"]
        if params.get("frequency_penalty") is not None:
            request_params["frequency_penalty"] = params["frequency_penalty"]
        if params.get("presence_penalty") is not None:
            request_params["presence_penalty"] = params["presence_penalty"]
        if params.get("stop_sequences"):
            request_params["stop"] = params["stop_sequences"]
        
        response = await client.chat.completions.create(**request_params)
        
        # Получаем токены
        if hasattr(response, 'usage'):
            token_count["prompt"] = response.usage.prompt_tokens
            token_count["completion"] = response.usage.completion_tokens
            token_count["total"] = response.usage.total_tokens
        
        content = response.choices[0].message.content
        elapsed_time = time.time() - start_time
        
        return content if content else "", {"elapsed_time": elapsed_time, "token_count": token_count}
        
    except (OpenAIAuthenticationError, OpenAINotFoundError, OpenAIRateLimitError) as e:
        elapsed_time = time.time() - start_time
        logger.error(f"Ошибка API OpenAI ({type(e).__name__}) для модели {model_name}: {e}")
        raise  # Передаем ошибку выше для обработки
    except OpenAIError as e:
        elapsed_time = time.time() - start_time
        logger.error(f"Общая ошибка API OpenAI для модели {model_name}: {e}")
        raise
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.exception(f"Неизвестная ошибка при запросе к OpenAI {model_name}: {e}", exc_info=True)
        raise ConnectionError(f"Неизвестная ошибка при запросе к OpenAI: {e}")


async def _infer_google(model_name: str, prompt: str, params: Dict) -> Tuple[str, Dict]:
    """Выполняет запрос к Google AI API."""
    if not genai: 
        raise ValueError("Библиотека Google AI не установлена.")
        
    start_time = time.time()
    token_count = {"prompt": None, "completion": None, "total": None}  # Google не всегда возвращает счетчики
    
    try:
        # Ключ уже должен быть настроен через genai.configure в _get_provider_client
        model = genai.GenerativeModel(model_name)
        
        # Определяем параметры генерации
        generation_config = genai.types.GenerationConfig(
             max_output_tokens=params.get("max_tokens"),
             temperature=params.get("temperature"),
             top_p=params.get("top_p"),
        )
        
        # Формируем содержимое запроса (с системным промтом или без)
        if params.get("system_prompt"):
            response = await model.generate_content_async(
                [
                    genai.types.Content(
                        parts=[genai.types.Part(text=params["system_prompt"])],
                        role="system"
                    ),
                    genai.types.Content(
                        parts=[genai.types.Part(text=prompt)],
                        role="user"
                    )
                ],
                generation_config=generation_config
            )
        else:
            # Стандартный запрос без системного промта
            response = await model.generate_content_async(
                 prompt,
                 generation_config=generation_config
            )
        
        # Обработка safety_ratings (если нужно)
        if not response.parts:
             # Проверяем, был ли контент заблокирован
             if response.prompt_feedback and response.prompt_feedback.block_reason:
                  raise ValueError(f"Запрос к Google AI заблокирован: {response.prompt_feedback.block_reason.name}")
             else:
                  return "", {"elapsed_time": time.time() - start_time, "token_count": token_count}
                  
        # Пытаемся получить информацию о токенах, если она есть
        if hasattr(response, 'usage_metadata'):
            try:
                token_count["total"] = response.usage_metadata.total_token_count
                # Для Google AI не всегда доступны отдельные счетчики prompt/completion
            except:
                pass
                
        elapsed_time = time.time() - start_time
        return response.text, {"elapsed_time": elapsed_time, "token_count": token_count}
        
    except (GoogleUnauthenticated, GooglePermissionDenied, GoogleNotFound) as e:
         elapsed_time = time.time() - start_time
         logger.error(f"Ошибка API Google AI ({type(e).__name__}) для модели {model_name}: {e}")
         raise ValueError(f"Ошибка Google AI: {e}")
    except GoogleClientError as e:
        elapsed_time = time.time() - start_time
        logger.error(f"Общая ошибка API Google AI для модели {model_name}: {e}")
        raise ValueError(f"Ошибка Google AI: {e}")
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.exception(f"Неизвестная ошибка при запросе к Google AI {model_name}: {e}", exc_info=True)
        raise ConnectionError(f"Неизвестная ошибка при запросе к Google AI: {e}")

async def _infer_anthropic(client: AsyncAnthropic, model_name: str, prompt: str, params: Dict) -> Tuple[str, Dict]:
    """Выполняет запрос к Anthropic API."""
    if not client: 
        raise ValueError("Клиент Anthropic не инициализирован.")
        
    start_time = time.time()
    token_count = {"prompt": None, "completion": None, "total": None}
    
    try:
        # Формируем запрос
        request_params = {
            "model": model_name,
            "max_tokens": params.get("max_tokens", 1024),  # У Anthropic max_tokens обязательный
            "temperature": params.get("temperature"),
        }
        
        # Добавляем опциональные параметры
        if params.get("top_p") is not None:
            request_params["top_p"] = params["top_p"]
            
        # Формируем сообщения
        messages = []
        
        # Добавляем системный промт, если есть
        if params.get("system_prompt"):
            request_params["system"] = params["system_prompt"]
        
        # Добавляем основной промт
        messages = [{"role": "user", "content": prompt}]
        request_params["messages"] = messages
        
        response = await client.messages.create(**request_params)
        
        # Ответ в response.content, который является списком блоков (обычно один TextBlock)
        text_content = "".join(block.text for block in response.content if hasattr(block, 'text'))
        
        # Получаем информацию о токенах, если она есть
        if hasattr(response, 'usage'):
            token_count["prompt"] = response.usage.input_tokens
            token_count["completion"] = response.usage.output_tokens
            token_count["total"] = token_count["prompt"] + token_count["completion"] if token_count["prompt"] and token_count["completion"] else None
        
        elapsed_time = time.time() - start_time
        return text_content, {"elapsed_time": elapsed_time, "token_count": token_count}
        
    except (AnthropicAuthenticationError, AnthropicNotFoundError, AnthropicRateLimitError) as e:
        elapsed_time = time.time() - start_time
        logger.error(f"Ошибка API Anthropic ({type(e).__name__}) для модели {model_name}: {e}")
        raise ValueError(f"Ошибка Anthropic: {e}")
    except AnthropicError as e:
        elapsed_time = time.time() - start_time
        logger.error(f"Общая ошибка API Anthropic для модели {model_name}: {e}")
        raise ValueError(f"Ошибка Anthropic: {e}")
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.exception(f"Неизвестная ошибка при запросе к Anthropic {model_name}: {e}", exc_info=True)
        raise ConnectionError(f"Неизвестная ошибка при запросе к Anthropic: {e}")

async def _infer_mistral(client: MistralAsyncClient, model_name: str, prompt: str, params: Dict) -> Tuple[str, Dict]:
    """Выполняет запрос к Mistral AI API."""
    if not client: 
        raise ValueError("Клиент Mistral AI не инициализирован.")
        
    start_time = time.time()
    token_count = {"prompt": None, "completion": None, "total": None}
    
    try:
        # Формируем сообщения
        messages = []
        
        # Добавляем системный промт, если есть
        if params.get("system_prompt"):
            messages.append({"role": "system", "content": params["system_prompt"]})
        
        # Добавляем основной промт
        messages.append({"role": "user", "content": prompt})
        
        # Формируем параметры запроса
        request_params = {
            "model": model_name,
            "messages": messages,
            "max_tokens": params.get("max_tokens"),
            "temperature": params.get("temperature"),
        }
        
        # Добавляем опциональные параметры
        if params.get("top_p") is not None:
            request_params["top_p"] = params["top_p"]
        if params.get("stop_sequences"):
            request_params["stop"] = params["stop_sequences"]
        
        response = await client.chat(**request_params)
        
        # Получаем информацию о токенах, если она есть
        if hasattr(response, 'usage'):
            token_count["prompt"] = response.usage.prompt_tokens
            token_count["completion"] = response.usage.completion_tokens
            token_count["total"] = response.usage.total_tokens
            
        elapsed_time = time.time() - start_time
        return response.choices[0].message.content, {"elapsed_time": elapsed_time, "token_count": token_count}
        
    except MistralAPIStatusException as e:
         if e.status_code == 401:
              logger.error(f"Ошибка аутентификации Mistral AI для модели {model_name}: {e.message}")
              raise ValueError(f"Ошибка Mistral AI: {e.message}")
         elif e.status_code == 429:
              logger.error(f"Превышен лимит запросов Mistral AI для модели {model_name}: {e.message}")
              raise ValueError(f"Ошибка Mistral AI: {e.message}")
         else:
              logger.error(f"Ошибка API Mistral AI ({e.status_code}) для модели {model_name}: {e.message}")
              raise ValueError(f"Ошибка Mistral AI ({e.status_code}): {e.message}")
    except MistralConnectionException as e:
         elapsed_time = time.time() - start_time
         logger.error(f"Ошибка соединения с Mistral AI для модели {model_name}: {e}")
         raise ConnectionError(f"Ошибка соединения с Mistral AI: {e}")
    except MistralException as e:
        elapsed_time = time.time() - start_time
        logger.error(f"Общая ошибка Mistral AI для модели {model_name}: {e}")
        raise ValueError(f"Ошибка Mistral AI: {e}")
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.exception(f"Неизвестная ошибка при запросе к Mistral AI {model_name}: {e}", exc_info=True)
        raise ConnectionError(f"Неизвестная ошибка при запросе к Mistral AI: {e}")

async def _infer_groq(client: AsyncGroq, model_name: str, prompt: str, params: Dict) -> Tuple[str, Dict]:
    """Выполняет запрос к Groq API (формат OpenAI)."""
    if not client: 
        raise ValueError("Клиент Groq не инициализирован.")
        
    start_time = time.time()
    token_count = {"prompt": None, "completion": None, "total": None}
    
    try:
        # Формируем сообщения
        messages = []
        
        # Добавляем системный промт, если он поддерживается и указан
        metadata = _get_model_metadata("groq", model_name)
        if metadata["supports_system_prompt"] and params.get("system_prompt"):
            messages.append({"role": "system", "content": params["system_prompt"]})
        
        # Добавляем основной промт
        messages.append({"role": "user", "content": prompt})
        
        # Формируем параметры запроса
        request_params = {
            "model": model_name,
            "messages": messages,
            "temperature": params.get("temperature"),
            "max_tokens": params.get("max_tokens"),
        }
        
        # Добавляем опциональные параметры
        if params.get("top_p") is not None:
            request_params["top_p"] = params["top_p"]
        if params.get("frequency_penalty") is not None:
            request_params["frequency_penalty"] = params["frequency_penalty"]
        if params.get("presence_penalty") is not None:
            request_params["presence_penalty"] = params["presence_penalty"]
        if params.get("stop_sequences"):
            request_params["stop"] = params["stop_sequences"]
        
        response = await client.chat.completions.create(**request_params)
        
        # Получаем токены, если они есть
        if hasattr(response, 'usage'):
            token_count["prompt"] = response.usage.prompt_tokens
            token_count["completion"] = response.usage.completion_tokens
            token_count["total"] = response.usage.total_tokens
        
        content = response.choices[0].message.content
        elapsed_time = time.time() - start_time
        
        return content if content else "", {"elapsed_time": elapsed_time, "token_count": token_count}
        
    except (GroqAuthenticationError, GroqNotFoundError, GroqRateLimitError) as e:
        elapsed_time = time.time() - start_time
        logger.error(f"Ошибка API Groq ({type(e).__name__}) для модели {model_name}: {e}")
        raise ValueError(f"Ошибка Groq: {e}")
    except GroqError as e:
        elapsed_time = time.time() - start_time
        logger.error(f"Общая ошибка API Groq для модели {model_name}: {e}")
        raise ValueError(f"Ошибка Groq: {e}")
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.exception(f"Неизвестная ошибка при запросе к Groq {model_name}: {e}", exc_info=True)
        raise ConnectionError(f"Неизвестная ошибка при запросе к Groq: {e}")

# --- Утилиты для обработки ошибок и повторных попыток ---

def async_retry(max_retries: int = 3, 
                retry_delay: float = 1.0, 
                backoff_factor: float = 2.0,
                retry_exceptions: tuple = (ConnectionError, TimeoutError, ConnectionAbortedError)):
    """
    Декоратор для асинхронных функций, который делает повторные попытки при возникновении 
    определенных исключений с экспоненциальной задержкой между попытками.
    
    Args:
        max_retries: Максимальное количество повторных попыток
        retry_delay: Начальная задержка перед повторной попыткой (в секундах)
        backoff_factor: Множитель для увеличения задержки с каждой попыткой
        retry_exceptions: Кортеж типов исключений, при которых нужно делать повторные попытки
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            delay = retry_delay
            
            # Извлекаем имя функции для логов (обычно это _infer_*)
            func_name = func.__name__
            # Пытаемся определить, какую модель вызываем (обычно третий аргумент)
            model_name = kwargs.get('model_name', '') if 'model_name' in kwargs else (
                args[2] if len(args) > 2 else 'unknown')
            
            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        logger.info(f"Попытка {attempt}/{max_retries} вызова {func_name} для {model_name} (задержка: {delay:.1f}с)")
                    
                    return await func(*args, **kwargs)
                    
                except retry_exceptions as e:
                    last_exception = e
                    
                    # Проверяем, является ли ошибка временной
                    error_str = str(e).lower()
                    is_temporary = any(
                        phrase in error_str for phrase in 
                        ["timeout", "currently loading", "temporarily unavailable", 
                         "too many requests", "rate limit", "retry"]
                    )
                    
                    if not is_temporary or attempt >= max_retries:
                        # Если ошибка не временная или исчерпаны попытки, передаем исключение дальше
                        logger.warning(f"Не удалось выполнить {func_name} для {model_name} после {attempt+1} попыток: {e}")
                        raise
                    
                    # Логируем информацию о повторной попытке
                    logger.info(f"Временная ошибка при вызове {func_name} для {model_name}: {e}, повторная попытка через {delay:.1f}с")
                    
                    # Ждем перед повторной попыткой с экспоненциальной задержкой
                    await asyncio.sleep(delay)
                    delay *= backoff_factor
                
                except Exception as e:
                    # Для других исключений не делаем повторных попыток
                    raise
            
            # Этот код не должен выполниться, но на всякий случай
            if last_exception:
                raise last_exception
            raise RuntimeError(f"Не удалось выполнить {func_name} после {max_retries} попыток")
            
        return wrapper
    return decorator

@async_retry(max_retries=2, retry_delay=1.5, 
            retry_exceptions=(ConnectionError, TimeoutError, ConnectionAbortedError, 
                             Exception))  # для Hugging Face мы расширяем типы ошибок для повторных попыток
async def _infer_huggingface(clients: Dict[str, Any], model_name: str, prompt: str, params: Dict) -> Tuple[str, Dict]:
    """Выполняет запрос к Hugging Face Inference API."""
    if not clients or "inference" not in clients: 
        raise ValueError("Клиент Hugging Face Inference не инициализирован.")
        
    inference_client: AsyncInferenceClient = clients["inference"]
    start_time = time.time()
    token_count = {"prompt": None, "completion": None, "total": None}  # HF не всегда возвращает токены
    
    try:
        # Определяем параметры запроса
        request_params = {
            "model": model_name,
            "prompt": prompt,
            "max_new_tokens": params.get("max_tokens"),
            "temperature": params.get("temperature", 1.0)  # HF требует > 0
        }
        
        # Добавляем опциональные параметры
        if params.get("top_p") is not None:
            request_params["top_p"] = params["top_p"]
        if params.get("stop_sequences"):
            request_params["stop"] = params["stop_sequences"]
        
        # Определяем тип задачи (text-generation или conversational)
        task = "text-generation"
        try:
            response = await inference_client.text_generation(**request_params)
            
            # Убираем сам промт из ответа, если он включен
            if isinstance(response, str) and response.startswith(prompt):
                 processed_response = response[len(prompt):].strip()
            else:
                 processed_response = response
                 
            elapsed_time = time.time() - start_time
            return processed_response, {"elapsed_time": elapsed_time, "token_count": token_count}

        except HFValidationError as e_gen:
            # Может быть ошибка, если модель поддерживает только conversational API
            if "is not supported for text-generation" in str(e_gen).lower():
                 logger.debug(f"Модель {model_name} не поддерживает text-generation, пробуем conversational.")
                 task = "conversational"
                 
                 # Пробуем использовать chat API
                 try:
                     response = await inference_client.chat(
                         model=model_name,
                         messages=[
                             {"role": "system", "content": params.get("system_prompt", "")} if params.get("system_prompt") else None,
                             {"role": "user", "content": prompt}
                         ],
                         temperature=params.get("temperature", 1.0),
                         max_tokens=params.get("max_tokens")
                     )
                     
                     elapsed_time = time.time() - start_time
                     return response.generated_text, {"elapsed_time": elapsed_time, "token_count": token_count}
                 except Exception:
                     # Если и chat не поддерживается, возвращаем сообщение об ошибке
                     raise NotImplementedError(f"Модель {model_name} не поддерживает совместимый API.")
            else:
                 raise e_gen  # Другая ошибка валидации

    except (RepositoryNotFoundError, GatedRepoError) as e:
        elapsed_time = time.time() - start_time
        logger.error(f"Ошибка доступа к модели Hugging Face {model_name}: {e}")
        raise ValueError(f"Ошибка Hugging Face: {e}")
    except HFValidationError as e:
         elapsed_time = time.time() - start_time
         logger.error(f"Ошибка аутентификации/валидации Hugging Face для модели {model_name}: {e}")
         raise ValueError(f"Ошибка Hugging Face: {e}")
    except InferenceTimeoutError:
         elapsed_time = time.time() - start_time
         logger.error(f"Таймаут запроса к Hugging Face Inference API для модели {model_name}.")
         raise TimeoutError(f"Таймаут запроса к Hugging Face {model_name}.")
    except Exception as e:
        elapsed_time = time.time() - start_time
        # Обработка ошибок вида 'Model ... is currently loading'
        if "is currently loading" in str(e) or "currently unavailable" in str(e):
             logger.warning(f"Модель Hugging Face {model_name} временно недоступна: {e}")
             raise ConnectionAbortedError(f"Модель Hugging Face {model_name} временно недоступна.")
        logger.exception(f"Неизвестная ошибка при запросе к Hugging Face {model_name}: {e}", exc_info=True)
        raise ConnectionError(f"Неизвестная ошибка при запросе к Hugging Face: {e}")


async def run_single_inference(db: AsyncSession, request: InteractionRequest) -> InteractionResponse:
    """Выполняет запрос к одной модели, обрабатывая ошибки."""
    full_model_id = request.model_id
    prompt = request.prompt
    
    # Соберем все параметры запроса
    params = {
        "max_tokens": request.max_tokens or settings.default_max_tokens,
        "temperature": request.temperature or settings.default_temperature,
        "top_p": request.top_p,
        "frequency_penalty": request.frequency_penalty,
        "presence_penalty": request.presence_penalty,
        "stop_sequences": request.stop_sequences
    }
    
    # Получаем системный промт, если он не указан в запросе
    if request.system_prompt is None:
        params["system_prompt"] = await database.get_system_prompt(db, full_model_id)
    else:
        params["system_prompt"] = request.system_prompt
    
    response_text = ""
    error_message = None
    token_info = {"prompt": None, "completion": None, "total": None}
    elapsed_time = 0
    
    # Проверяем кеш, если температура низкая
    use_cache = params.get("temperature", 0.7) <= 0.1
    cache_key = None
    
    if use_cache:
        cache_key = f"{full_model_id}:{hashlib.md5(prompt.encode()).hexdigest()}:{params.get('max_tokens')}:{params.get('system_prompt', '')}"
        cached_response = response_cache.get(cache_key)
        if cached_response:
            logger.info(f"Возвращаем кешированный ответ для {full_model_id}")
            return cached_response

    start_time = time.time()
    logger.info(f"Запрос к модели {full_model_id} (prompt: '{prompt[:30]}...')")

    try:
        provider, model_name = _parse_model_id(full_model_id)
        client_or_key = await _get_provider_client(db, provider)

        if client_or_key is None:
            raise ValueError(f"API ключ для провайдера '{provider}' не найден или клиент не инициализирован.")

        # Вызов соответствующей функции для провайдера
        if provider == "openai":
            response_text, meta = await _infer_openai(client_or_key, model_name, prompt, params)
            elapsed_time = meta.get("elapsed_time", 0)
            token_info = meta.get("token_count", token_info)
        elif provider == "google":
            response_text, meta = await _infer_google(model_name, prompt, params)
            elapsed_time = meta.get("elapsed_time", 0)
            token_info = meta.get("token_count", token_info)
        elif provider == "anthropic":
            response_text, meta = await _infer_anthropic(client_or_key, model_name, prompt, params)
            elapsed_time = meta.get("elapsed_time", 0)
            token_info = meta.get("token_count", token_info)
        elif provider == "mistral":
            response_text, meta = await _infer_mistral(client_or_key, model_name, prompt, params)
            elapsed_time = meta.get("elapsed_time", 0)
            token_info = meta.get("token_count", token_info)
        elif provider == "groq":
            response_text, meta = await _infer_groq(client_or_key, model_name, prompt, params)
            elapsed_time = meta.get("elapsed_time", 0)
            token_info = meta.get("token_count", token_info)
        elif provider == "huggingface_hub":
            response_text, meta = await _infer_huggingface(client_or_key, model_name, prompt, params)
            elapsed_time = meta.get("elapsed_time", 0)
            token_info = meta.get("token_count", token_info)
        else:
            # Это не должно произойти из-за _parse_model_id
            raise ValueError(f"Обработчик для провайдера '{provider}' не реализован.")
        
        # Если успешный запрос с низкой температурой, кешируем результат
        if use_cache and cache_key and not error_message:
            response = InteractionResponse(
                model_id=full_model_id,
                response=response_text,
                error=error_message,
                elapsed_time=elapsed_time,
                token_count=token_info
            )
            response_cache.set(cache_key, response)
            return response

    # Обработка ошибок аутентификации
    except (OpenAIAuthenticationError, AnthropicAuthenticationError, 
            GroqAuthenticationError, GoogleUnauthenticated, GooglePermissionDenied) as e:
        error_type = type(e).__name__
        logger.error(f"Ошибка аутентификации API {provider} для модели {full_model_id}: {error_type}: {e}")
        error_message = f"Ошибка аутентификации API {provider}. Пожалуйста, проверьте ваш API ключ."

    # Обработка ошибок, связанных с отсутствием модели
    except (OpenAINotFoundError, AnthropicNotFoundError, GroqNotFoundError, GoogleNotFound) as e:
        error_type = type(e).__name__
        logger.error(f"Модель {full_model_id} не найдена у провайдера {provider}: {error_type}: {e}")
        error_message = f"Модель '{model_name}' не найдена у провайдера {provider}."

    # Обработка ошибок, связанных с превышением лимитов запросов
    except (OpenAIRateLimitError, AnthropicRateLimitError, GroqRateLimitError) as e:
        error_type = type(e).__name__
        logger.error(f"Превышен лимит запросов к API {provider} для модели {full_model_id}: {error_type}: {e}")
        error_message = f"Превышен лимит запросов к API {provider}. Пожалуйста, попробуйте позже."
        
    # Обработка ошибок, связанных с валидацией запросов
    except (ValueError, NotImplementedError) as e:
        logger.warning(f"Ошибка конфигурации или реализации для {full_model_id}: {e}")
        if "API ключ" in str(e):
            error_message = f"API ключ для провайдера '{provider}' не настроен. Добавьте ключ в настройках."
        else:
            error_message = f"Ошибка конфигурации: {e}"
            
    # Обработка сетевых ошибок
    except (ConnectionAbortedError, TimeoutError, ConnectionError, 
            InferenceTimeoutError, MistralConnectionException) as e:
        error_type = type(e).__name__
        error_details = str(e)
        logger.error(f"Ошибка сети при запросе к {full_model_id}: {error_type}: {error_details}")
        
        # Определяем тип ошибки для понятного сообщения пользователю
        if "timeout" in error_details.lower() or isinstance(e, TimeoutError) or isinstance(e, InferenceTimeoutError):
            error_message = f"Превышено время ожидания ответа от модели {provider}/{model_name}. Попробуйте позже или уменьшите размер промта."
        elif "currently loading" in error_details.lower() or "unavailable" in error_details.lower():
            error_message = f"Модель {provider}/{model_name} в данный момент загружается или временно недоступна. Пожалуйста, попробуйте позже."
        else:
            error_message = f"Ошибка сети при запросе к {provider}. Проверьте подключение к интернету и попробуйте позже."
    
    # Обработка общих ошибок API
    except (OpenAIError, AnthropicError, GroqError, MistralAPIException, 
            MistralAPIStatusException, GoogleClientError) as e:
        error_type = type(e).__name__
        logger.error(f"Ошибка API {provider} для модели {full_model_id}: {error_type}: {e}")
        
        # Проверяем, содержит ли ошибка информацию о превышении размера контекста
        error_details = str(e).lower()
        if "context" in error_details and ("length" in error_details or "size" in error_details or "too long" in error_details):
            error_message = f"Превышен максимальный размер контекста для модели {provider}/{model_name}. Уменьшите размер промта."
        elif "content policy" in error_details or "moderation" in error_details or "harmful" in error_details:
            error_message = f"Запрос был отклонен политикой безопасности {provider}. Измените содержание промта."
        else:
            error_message = f"Ошибка сервиса {provider}: {str(e)[:100]}..."
    
    # Обработка любых других исключений
    except Exception as e:
        logger.exception(f"Непредвиденная ошибка при запросе к {full_model_id}: {type(e).__name__}: {e}", exc_info=True)
        
        # Создаем идентификатор ошибки для отслеживания
        import uuid
        error_id = str(uuid.uuid4())[:8]
        
        # Записываем детальный лог с ID для облегчения отладки
        logger.error(f"[Error ID: {error_id}] Подробная информация об ошибке: {str(e)}")
        
        # Отправляем пользователю сообщение с ID ошибки для обращения в поддержку
        error_message = f"Внутренняя ошибка сервера при обработке запроса. Идентификатор ошибки: {error_id}"

    if not elapsed_time:
        elapsed_time = time.time() - start_time
        
    logger.info(f"Ответ от {full_model_id} получен за {elapsed_time:.2f} сек. Ошибка: {error_message is not None}")

    return InteractionResponse(
        model_id=full_model_id,
        response=response_text,
        error=error_message,
        elapsed_time=elapsed_time,
        token_count=token_info
    )


async def run_comparison_inference(db: AsyncSession, request: ComparisonRequest) -> ComparisonResponse:
    """Выполняет запросы к двум моделям параллельно."""
    logger.info(f"Запрос на сравнение моделей {request.model_id_1} и {request.model_id_2}")

    # Создаем запросы для каждой модели с их системными промтами
    request1 = InteractionRequest(
        model_id=request.model_id_1,
        prompt=request.prompt,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        top_p=request.top_p,
        frequency_penalty=request.frequency_penalty,
        presence_penalty=request.presence_penalty,
        stop_sequences=request.stop_sequences,
        system_prompt=request.system_prompt_1
    )
    
    request2 = InteractionRequest(
        model_id=request.model_id_2,
        prompt=request.prompt,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        top_p=request.top_p,
        frequency_penalty=request.frequency_penalty,
        presence_penalty=request.presence_penalty,
        stop_sequences=request.stop_sequences,
        system_prompt=request.system_prompt_2
    )

    # Запускаем запросы параллельно
    task1 = asyncio.create_task(run_single_inference(db, request1), name=f"infer_{request.model_id_1}")
    task2 = asyncio.create_task(run_single_inference(db, request2), name=f"infer_{request.model_id_2}")

    # Ожидаем результаты
    # Мы не используем return_exceptions=True здесь, т.к. run_single_inference
    # уже обрабатывает ошибки и возвращает их в поле 'error' объекта InteractionResponse.
    response1, response2 = await asyncio.gather(task1, task2)

    return ComparisonResponse(
        response_1=response1,
        response_2=response2
    )

# --- Вспомогательные функции для диагностики сети ---

def get_ip_addresses() -> Dict[str, Any]:
    """Получает информацию о сетевых интерфейсах и IP-адресах."""
    ip_info = {
        "local": [],
        "public": None,
        "hostname": socket.gethostname()
    }
    
    # Пытаемся получить локальные IP
    try:
        # В Linux / macOS
        import netifaces
        for interface in netifaces.interfaces():
            try:
                addresses = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addresses:
                    for addr in addresses[netifaces.AF_INET]:
                        ip = addr['addr']
                        if not ip.startswith('127.'):
                            ip_info["local"].append({
                                "interface": interface,
                                "ip": ip
                            })
            except:
                continue
    except ImportError:
        # Упрощенный вариант для Windows или если netifaces не установлен
        try:
            hostname = socket.gethostname()
            ip_info["local"] = [{
                "interface": hostname,
                "ip": socket.gethostbyname(hostname)
            }]
        except:
            pass
    
    # Пробуем получить внешний IP через API (без зависимостей)
    try:
        external_ip_apis = [
            "https://api.ipify.org",
            "https://ipinfo.io/ip",
            "https://ifconfig.me/ip"
        ]
        
        for api in external_ip_apis:
            try:
                import urllib.request
                with urllib.request.urlopen(api, timeout=2) as response:
                    ip_info["public"] = response.read().decode('utf-8').strip()
                if ip_info["public"]:
                    break
            except:
                continue
    except:
        pass
    
    return ip_info

# --- Утилиты для работы с кешем ---

class ResponseCache:
    """Простой кеш для хранения ответов моделей."""
    
    def __init__(self, ttl: int = 3600):
        self.cache = {}  # key -> (value, timestamp)
        self.ttl = ttl
    
    def get(self, key: str) -> Optional[Any]:
        """Получает значение из кеша, если оно не истекло."""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            else:
                # Удаляем истекшее значение
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Сохраняет значение в кеш."""
        self.cache[key] = (value, time.time())
    
    def clear(self, prefix: Optional[str] = None) -> None:
        """Очищает весь кеш или только элементы с определенным префиксом."""
        if prefix is None:
            self.cache.clear()
        else:
            keys_to_delete = [k for k in self.cache.keys() if k.startswith(prefix)]
            for k in keys_to_delete:
                del self.cache[k]

# Инициализация глобального кеша
response_cache = ResponseCache(ttl=settings.response_cache_ttl)
_CACHE_TTL = settings.models_cache_ttl  # TTL для кеша моделей

# --- Утилиты для парсинга и доступа к провайдерам ---

def _parse_model_id(full_model_id: str) -> Tuple[str, str]:
    """Разбирает полный ID модели (e.g., 'openai/gpt-4o') на провайдера и имя."""
    if '/' not in full_model_id:
        # По умолчанию считаем Hugging Face, если нет префикса
        # Или можно выбросить ошибку, если формат неверный
        logger.warning(f"Неверный формат model_id '{full_model_id}'. Предполагается Hugging Face.")
        return "huggingface_hub", full_model_id
    provider, model_name = full_model_id.split('/', 1)
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Неподдерживаемый провайдер '{provider}' в ID модели '{full_model_id}'")
    return provider, model_name