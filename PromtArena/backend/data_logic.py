# backend/data_logic.py

import hashlib
import logging
import time
from typing import List, Optional, Dict, Any, Union
from sqlalchemy.ext.asyncio import AsyncSession

# Импортируем функции и модели из соседних модулей
from backend import database
from backend.config import (
    ApiKeyCreate, ApiKeyRead, RatingCreate, RatingRead, LeaderboardEntry, ModelInfo, CategoryInfo,
    SUPPORTED_PROVIDERS, SystemPromptCreate, SystemPromptRead
)

logger = logging.getLogger(__name__)

# --- Логика Категорий ---

# Определяем статическую структуру категорий
CATEGORIES_STRUCTURE: List[CategoryInfo] = [
    CategoryInfo(id="programming", name="Программирование", subcategories=[
        CategoryInfo(id="programming_general", name="Общие задачи"),
        CategoryInfo(id="programming_frontend", name="Фронтенд"),
        CategoryInfo(id="programming_backend", name="Бэкенд"),
        CategoryInfo(id="programming_devops", name="DevOps"),
        CategoryInfo(id="programming_algorithms", name="Алгоритмы"),
    ]),
    CategoryInfo(id="text_generation", name="Генерация текста", subcategories=[
        CategoryInfo(id="text_creative", name="Креативный текст"),
        CategoryInfo(id="text_business", name="Деловой текст"),
        CategoryInfo(id="text_translation", name="Перевод"),
        CategoryInfo(id="text_summary", name="Суммаризация"),
    ]),
    CategoryInfo(id="knowledge", name="Ответы на вопросы", subcategories=[
        CategoryInfo(id="knowledge_general", name="Общие знания"),
        CategoryInfo(id="knowledge_science", name="Наука"),
        CategoryInfo(id="knowledge_history", name="История"),
    ]),
    CategoryInfo(id="math", name="Математика"),
    CategoryInfo(id="ocr", name="OCR (Распознавание текста)"),
    CategoryInfo(id="multimodal", name="Мультимодальные модели"),
    CategoryInfo(id="embeddings", name="Эмбеддинги"),
    # Добавим категорию для изображений
    CategoryInfo(id="image_generation", name="Генерация изображений"),
]

def get_categories() -> List[CategoryInfo]:
    """Возвращает структуру категорий."""
    logger.debug("Запрос структуры категорий")
    return CATEGORIES_STRUCTURE

# --- Логика API Ключей ---

async def add_or_update_api_key(db: AsyncSession, api_key_data: ApiKeyCreate, username: Optional[str] = None) -> ApiKeyRead:
    """
    Обрабатывает добавление/обновление API ключа, вызывая функцию БД.
    Возвращает информацию о ключе без самого ключа.
    """
    logger.info(f"Запрос на добавление/обновление ключа для провайдера: {api_key_data.provider}")
    # Валидация провайдера уже произошла в Pydantic модели ApiKeyCreate
    db_api_key = await database.create_api_key(db, api_key_data, username)
    return ApiKeyRead.model_validate(db_api_key)

async def list_api_keys(db: AsyncSession) -> List[ApiKeyRead]:
    """Получает список всех добавленных API ключей (без самих ключей)."""
    logger.debug("Запрос списка добавленных API ключей")
    return await database.get_all_api_keys_info(db)

async def remove_api_key(db: AsyncSession, provider: str) -> bool:
    """Обрабатывает удаление API ключа."""
    logger.info(f"Запрос на удаление ключа для провайдера: {provider}")
    if provider not in SUPPORTED_PROVIDERS:
        logger.warning(f"Попытка удаления ключа для неподдерживаемого провайдера: {provider}")
        return False
    return await database.delete_api_key(db, provider)

# --- Логика Системных Промтов ---

async def add_or_update_system_prompt(db: AsyncSession, prompt_data: SystemPromptCreate, username: Optional[str] = None) -> SystemPromptRead:
    """
    Обрабатывает добавление/обновление системного промта, вызывая функцию БД.
    """
    logger.info(f"Запрос на добавление/обновление системного промта для модели: {prompt_data.model_id}")
    db_prompt = await database.create_or_update_system_prompt(db, prompt_data, username)
    return SystemPromptRead.model_validate(db_prompt)

async def get_system_prompts(db: AsyncSession) -> List[SystemPromptRead]:
    """Получает список всех системных промтов."""
    logger.debug("Запрос списка системных промтов")
    return await database.get_all_system_prompts(db)

async def remove_system_prompt(db: AsyncSession, model_id: str) -> bool:
    """Обрабатывает удаление системного промта."""
    logger.info(f"Запрос на удаление системного промта для модели: {model_id}")
    return await database.delete_system_prompt(db, model_id)

# --- Логика Рейтингов ---

def _hash_prompt(prompt_text: str) -> str:
    """Создает SHA-256 хеш для текста промта."""
    return hashlib.sha256(prompt_text.encode('utf-8')).hexdigest()

async def process_and_save_rating(db: AsyncSession, rating_data: RatingCreate) -> RatingRead:
    """
    Обрабатывает данные оценки, хеширует промт и сохраняет в БД.
    """
    logger.info(f"Обработка оценки {rating_data.rating}/10 для модели {rating_data.model_id}")
    prompt_hash = _hash_prompt(rating_data.prompt_text)
    logger.debug(f"Хеш промта ({rating_data.prompt_text[:20]}...): {prompt_hash}")

    # Вызываем функцию БД для создания записи
    db_rating = await database.create_rating(db, rating_data, prompt_hash)

    # Преобразуем результат в Pydantic модель для ответа API
    rating_read_data = RatingRead.model_validate(db_rating)
    return rating_read_data

# --- Логика Лидерборда ---

# Кеш для деталей моделей, чтобы не дергать models_io постоянно
_model_details_cache: Dict[str, ModelInfo] = {}
_cache_expiry_time = 3600 # Время жизни кеша в секундах (1 час)
_last_cache_update = 0

async def _get_enriched_model_details(db: AsyncSession) -> Dict[str, ModelInfo]:
    """
    Получает детали моделей (имя, провайдер, категория) из кеша или
    вызывает функцию из models_io для их получения.
    """
    import time
    global _last_cache_update, _model_details_cache

    current_time = time.time()
    if not _model_details_cache or (current_time - _last_cache_update > _cache_expiry_time):
        logger.info("Обновление кеша деталей моделей для лидерборда...")
        try:
            # Отложенный импорт чтобы избежать циклических импортов
            from backend.models_io import get_available_models_details
            all_models: List[ModelInfo] = await get_available_models_details(db) # Передаем сессию для получения ключей
            _model_details_cache = {model.id: model for model in all_models}
            _last_cache_update = current_time
            logger.info(f"Кеш деталей моделей обновлен. Загружено {len(_model_details_cache)} моделей.")
        except ImportError:
             logger.error("Функция get_available_models_details не найдена в backend.models_io. Пожалуйста, реализуйте ее.")
             # Возвращаем пустой словарь или старый кеш, чтобы не падать
             return _model_details_cache
        except Exception as e:
            logger.exception("Ошибка при обновлении кеша деталей моделей.", exc_info=e)
            # Возвращаем старый кеш, если он есть
            return _model_details_cache

    return _model_details_cache


async def generate_leaderboard(db: AsyncSession, category_filter: Optional[str] = None) -> List[LeaderboardEntry]:
    """
    Формирует лидерборд: получает агрегированные данные из БД,
    обогащает их деталями моделей (имя, провайдер, категория) и применяет фильтр.
    """
    logger.info(f"Генерация лидерборда. Фильтр по категории: {category_filter}")

    # 1. Получаем сырые данные рейтинга (model_id, avg_rating, count) из БД
    raw_leaderboard_data = await database.get_leaderboard_data(db, category_filter)
    if not raw_leaderboard_data:
        logger.warning("Нет данных о рейтингах для формирования лидерборда.")
        return []

    # 2. Получаем обогащенные детали моделей (имя, провайдер, категория)
    model_details = await _get_enriched_model_details(db)
    if not model_details:
         logger.warning("Нет деталей моделей для обогащения лидерборда. Лидерборд может быть неполным.")
         # В этом случае можно вернуть только ID моделей или пустой список

    # 3. Собираем и фильтруем лидерборд
    leaderboard: List[LeaderboardEntry] = []
    rank = 1
    for model_id, avg_rating, rating_count in raw_leaderboard_data:
        details = model_details.get(model_id)
        if details:
            # Применяем фильтр по категории, если он задан
            # Фильтруем по ID основной категории (e.g., "programming")
            # или по ID подкатегории (e.g., "programming_backend")
            model_category_id = details.category # Предполагаем, что ModelInfo содержит ID категории
            passes_filter = True
            if category_filter:
                # Проверяем прямое совпадение или совпадение с родительской категорией
                if model_category_id != category_filter and (not model_category_id or not model_category_id.startswith(category_filter + "_")):
                     passes_filter = False

            if passes_filter:
                entry = LeaderboardEntry(
                    rank=rank, # Добавляем ранг
                    model_id=details.id,
                    name=details.name,
                    provider=SUPPORTED_PROVIDERS.get(details.provider, details.provider), # Отображаемое имя провайдера
                    category=model_category_id, # Используем ID категории
                    average_rating=round(avg_rating, 2), # Округляем рейтинг
                    rating_count=rating_count
                )
                leaderboard.append(entry)
                rank += 1
        else:
            # Если у нас нет деталей о модели, создаем базовую запись
            if category_filter is None:  # Только если нет фильтра
                # Получаем провайдера из ID модели
                provider = model_id.split('/')[0] if '/' in model_id else "unknown"
                name = model_id.split('/')[-1] if '/' in model_id else model_id
                
                entry = LeaderboardEntry(
                    rank=rank,
                    model_id=model_id,
                    name=name,
                    provider=SUPPORTED_PROVIDERS.get(provider, provider),
                    category=None,
                    average_rating=round(avg_rating, 2),
                    rating_count=rating_count
                )
                leaderboard.append(entry)
                rank += 1
                logger.warning(f"Не найдены детали для модели {model_id} в кеше.")

    logger.info(f"Лидерборд сформирован. Записей: {len(leaderboard)}")
    return leaderboard

# --- Дополнительная бизнес-логика ---

async def get_dashboard_stats(db: AsyncSession) -> Dict[str, Any]:
    """Получает статистику для дашборда."""
    stats = {}
    
    # Общая статистика рейтингов
    try:
        rating_stats = await database.get_rating_statistics(db)
        stats["ratings"] = rating_stats
    except Exception as e:
        logger.error(f"Ошибка при получении статистики рейтингов: {e}")
        stats["ratings"] = {"error": str(e)}
    
    # Количество API ключей
    try:
        api_keys = await list_api_keys(db)
        stats["api_keys"] = {
            "count": len(api_keys),
            "providers": [key.provider for key in api_keys]
        }
    except Exception as e:
        logger.error(f"Ошибка при получении статистики API ключей: {e}")
        stats["api_keys"] = {"error": str(e)}
    
    # Топ-5 моделей (небольшой лидерборд)
    try:
        top_models = await generate_leaderboard(db)
        stats["top_models"] = top_models[:5] if top_models else []
    except Exception as e:
        logger.error(f"Ошибка при получении топ-моделей: {e}")
        stats["top_models"] = {"error": str(e)}
    
    return stats

async def get_model_details(db: AsyncSession, model_id: str) -> Dict[str, Any]:
    """Получает детальную информацию о модели."""
    details = {}
    
    # Получаем рейтинги для модели
    try:
        rating_stats = await database.get_model_rating_stats(db, model_id)
        details["ratings"] = rating_stats
    except Exception as e:
        logger.error(f"Ошибка при получении статистики рейтингов для модели {model_id}: {e}")
        details["ratings"] = {"error": str(e)}
    
    # Получаем системный промт для модели
    try:
        system_prompt = await database.get_system_prompt(db, model_id)
        details["system_prompt"] = system_prompt
    except Exception as e:
        logger.error(f"Ошибка при получении системного промта для модели {model_id}: {e}")
        details["system_prompt"] = None
    
    # Получаем детали модели
    try:
        # Используем кеш моделей, если он есть
        model_details = await _get_enriched_model_details(db)
        model_info = model_details.get(model_id)
        if model_info:
            details["model"] = model_info
        else:
            # Если нет в кеше, пытаемся разобрать ID
            provider = model_id.split('/')[0] if '/' in model_id else "unknown"
            name = model_id.split('/')[-1] if '/' in model_id else model_id
            details["model"] = {
                "id": model_id,
                "name": name,
                "provider": provider
            }
    except Exception as e:
        logger.error(f"Ошибка при получении деталей модели {model_id}: {e}")
        details["model"] = {"id": model_id, "error": str(e)}
    
    return details