# backend/database.py

import datetime
import hashlib
from typing import AsyncGenerator, List, Optional, Tuple, Dict, Any, Union
import logging
import os

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float, LargeBinary, Index, UniqueConstraint, ForeignKey, func, desc, Boolean
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from contextlib import asynccontextmanager

from backend.config import settings, fernet, SUPPORTED_PROVIDERS
# Импортируем Pydantic модели для type hinting и возвращаемых значений
from backend.config import ApiKeyCreate, ApiKeyRead, RatingCreate, RatingRead, LeaderboardEntry, SystemPromptCreate, SystemPromptRead

# Настройка логгера
logger = logging.getLogger(__name__)

# --- Шифрование/Дешифрование ---

def encrypt_data(data: str) -> bytes:
    """Шифрует строку с использованием Fernet."""
    return fernet.encrypt(data.encode())

def decrypt_data(encrypted_data: bytes) -> str:
    """Дешифрует данные с использованием Fernet."""
    return fernet.decrypt(encrypted_data).decode()

# --- Настройка SQLAlchemy ---

# Создаем асинхронный движок
try:
    # Проверяем, является ли БД SQLite
    is_sqlite = 'sqlite' in settings.database_url.lower()
    
    db_params = {
        'echo': settings.log_level == "DEBUG",  # Включаем логирование SQL запросов в DEBUG режиме
        'pool_pre_ping': True,  # Проверяет соединение перед использованием
    }
    
    # Добавляем параметры пула только если это не SQLite
    if not is_sqlite:
        db_params.update({
            'pool_size': 5,        # Количество соединений в пуле
            'max_overflow': 10,    # Максимальное количество соединений сверх pool_size
        })
    
    async_engine = create_async_engine(
        settings.database_url,
        **db_params
    )
    logger.info(f"Async engine created for URL: {'sqlite' if 'sqlite' in settings.database_url else settings.database_url.split('@')[1] if '@' in settings.database_url else settings.database_url}")
except Exception as e:
    logger.exception(f"Failed to create async engine for URL: {settings.database_url}", exc_info=e)
    raise

# Создаем асинхронную фабрику сессий
AsyncSessionFactory = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False, # Важно для асинхронных задач
    class_=AsyncSession,
    autoflush=False,        # Отключаем автоматический flush для контроля транзакций
    autocommit=False        # Явно указываем, что автокоммита нет
)

# Базовый класс для декларативных моделей
Base = declarative_base()

# --- Модели Таблиц ---

class ApiKey(Base):
    """Модель для хранения API ключей провайдеров."""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False, index=True)
    encrypted_api_key = Column(LargeBinary, nullable=False) # Храним зашифрованный ключ
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    # Добавим поле для отслеживания, кто создал ключ
    created_by = Column(String(50), nullable=True)

    # Ограничение: одна запись на провайдера (можно изменить, если нужны ключи для разных аккаунтов)
    __table_args__ = (UniqueConstraint('provider', name='uq_provider'),)

    def __repr__(self):
        return f"<ApiKey(id={self.id}, provider='{self.provider}')>"

class SystemPrompt(Base):
    """Модель для хранения системных промтов для моделей."""
    __tablename__ = "system_prompts"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String(255), nullable=False, index=True)
    prompt_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    created_by = Column(String(50), nullable=True)
    is_default = Column(Boolean, default=False)
    
    # Ограничение: один дефолтный промт на модель
    __table_args__ = (
        UniqueConstraint('model_id', 'is_default', name='uq_model_default_prompt'),
        Index('ix_system_prompts_model_default', 'model_id', 'is_default'),
    )
    
    def __repr__(self):
        return f"<SystemPrompt(id={self.id}, model_id='{self.model_id}', is_default={self.is_default})>"

class Rating(Base):
    """Модель для хранения оценок пользователей."""
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String(255), nullable=False, index=True) # e.g., "openai/gpt-4o"
    prompt_hash = Column(String(64), nullable=False, index=True) # SHA-256 hash
    prompt_excerpt = Column(String(100), nullable=True) # Сохраняем начало промта для отладки
    rating = Column(Integer, nullable=False) # 1-10
    comparison_winner = Column(String(50), nullable=True) # 'model_1', 'model_2', 'tie'
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    user_identifier = Column(String(255), nullable=True, index=True) # Session ID or User ID
    
    # Новые поля для детального анализа
    system_prompt = Column(Text, nullable=True)
    temperature = Column(Float, nullable=True)
    max_tokens = Column(Integer, nullable=True)
    top_p = Column(Float, nullable=True)
    frequency_penalty = Column(Float, nullable=True)
    presence_penalty = Column(Float, nullable=True)

    # Дополнительные индексы для ускорения запросов лидерборда
    __table_args__ = (
        Index('ix_ratings_model_rating', 'model_id', 'rating'),
        Index('ix_ratings_model_ts', 'model_id', 'timestamp'),
    )

    def __repr__(self):
        return f"<Rating(id={self.id}, model_id='{self.model_id}', rating={self.rating})>"

class PromptTemplate(Base):
    """Модель для хранения шаблонов промтов."""
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    prompt_text = Column(Text, nullable=False)
    tags = Column(String(255), nullable=True)  # Хранение тегов в виде строки, разделенных запятыми
    created_by = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    is_public = Column(Boolean, default=True)  # Определяет, доступен ли шаблон всем пользователям

    __table_args__ = (
        Index('ix_prompt_templates_name_created_by', 'name', 'created_by'),
    )

    def __repr__(self):
        return f"<PromptTemplate(id={self.id}, name='{self.name}')>"

# --- Функции для работы с БД ---

# Функция get_db для FastAPI Depends
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Предоставляет сессию для API-эндпойнтов через FastAPI Depends."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Ошибка SQLAlchemy во время сессии: {e}", exc_info=True)
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Неизвестная ошибка во время сессии БД: {e}", exc_info=True)
            raise

async def init_db():
    """Инициализирует базу данных, создавая таблицы и добавляя начальные данные."""
    async with async_engine.begin() as conn:
        logger.info("Инициализация базы данных...")
        try:
            # Создаем все таблицы, если они еще не существуют
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Таблицы успешно созданы (или уже существовали).")
            
            # Проверяем, существуют ли таблицы действительно
            # Это поможет обнаружить ошибки с путями к SQLite
            try:
                await check_db_connection()
                logger.info("Проверка соединения с базой данных успешно пройдена.")
                
                # Добавляем начальные системные промты, если их нет
                async with AsyncSessionFactory() as session:
                    await add_default_system_prompts(session)
                
            except Exception as e:
                logger.error(f"Ошибка проверки соединения с БД: {e}")
                raise
                
        except Exception as e:
            logger.exception("Ошибка при создании таблиц БД.", exc_info=e)
            raise

async def check_db_connection():
    """Проверяет соединение с базой данных и корректность схемы."""
    async with AsyncSessionFactory() as session:
        try:
            # Пробуем выполнить простой запрос для проверки
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1, "Ошибка проверки соединения с БД"
            
            # Проверяем наличие ожидаемых таблиц
            tables_query = """
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('api_keys', 'ratings', 'system_prompts', 'prompt_templates')
            """
            if "sqlite" in str(async_engine.url):
                tables = await session.execute(text(tables_query))
                table_names = [row[0] for row in tables]
                
                logger.info(f"Обнаружены таблицы в БД: {table_names}")
                
                if "api_keys" not in table_names or "ratings" not in table_names or "system_prompts" not in table_names or "prompt_templates" not in table_names:
                    logger.warning(f"Не все ожидаемые таблицы существуют. Найдены: {table_names}")
                    # Пытаемся повторно создать таблицы
                    async with async_engine.begin() as conn:
                        await conn.run_sync(Base.metadata.create_all)
                    
        except Exception as e:
            logger.error(f"Ошибка проверки соединения с БД: {e}")
            raise

async def add_default_system_prompts(db: AsyncSession):
    """Добавляет дефолтные системные промты при первом запуске."""
    from sqlalchemy import select
    
    # Проверяем, есть ли уже системные промты
    stmt = select(func.count()).select_from(SystemPrompt)
    result = await db.execute(stmt)
    count = result.scalar()
    
    if count == 0:
        logger.info("Добавление дефолтных системных промтов...")
        
        # Распространенные модели и их дефолтные промты
        default_prompts = [
            ("openai/gpt-4", "Ты — GPT-4, большая языковая модель, разработанная OpenAI. Следуй инструкциям пользователя тщательно и ответственно."),
            ("openai/gpt-3.5-turbo", "Ты — GPT-3.5, полезный ассистент, разработанный OpenAI."),
            ("anthropic/claude-3-opus", "Ты — Клод, полезный и этичный ассистент, разработанный Anthropic для помощи пользователям."),
            ("anthropic/claude-3-sonnet", "Ты — Клод, полезный и этичный ассистент, разработанный Anthropic для помощи пользователям."),
            ("google/gemini-pro", "Ты — Gemini, доброжелательный и полезный ассистент, разработанный Google."),
            ("mistral/mistral-large", "Ты — Mistral, большая языковая модель от Mistral AI. Давай полезные и точные ответы."),
            ("groq/llama2-70b", "Ты — Llama 2, большая языковая модель, разработанная Meta и запущенная через Groq.")
        ]
        
        for model_id, prompt_text in default_prompts:
            system_prompt = SystemPrompt(
                model_id=model_id,
                prompt_text=prompt_text,
                is_default=True,
                created_by="system"
            )
            db.add(system_prompt)
        
        await db.commit()
        logger.info(f"Добавлено {len(default_prompts)} дефолтных системных промтов.")
                
# --- CRUD операции для ApiKey ---

async def create_api_key(db: AsyncSession, api_key_data: ApiKeyCreate, username: Optional[str] = None) -> ApiKey:
    """Создает или обновляет API ключ для провайдера."""
    # Проверяем, существует ли ключ для этого провайдера
    from sqlalchemy import select, update

    stmt_select = select(ApiKey).where(ApiKey.provider == api_key_data.provider)
    result = await db.execute(stmt_select)
    db_api_key = result.scalar_one_or_none()

    encrypted_key = encrypt_data(api_key_data.api_key.get_secret_value())

    try:
        if db_api_key:
            # Обновляем существующий ключ
            logger.info(f"Обновление API ключа для провайдера: {api_key_data.provider}")
            stmt_update = (
                update(ApiKey)
                .where(ApiKey.provider == api_key_data.provider)
                .values(
                    encrypted_api_key=encrypted_key, 
                    updated_at=datetime.datetime.utcnow(),
                    created_by=username if username else db_api_key.created_by
                )
            )
            await db.execute(stmt_update)
            # Нужно перезагрузить объект, чтобы получить обновленные данные, или просто вернуть существующий с обновленным ключом
            # Проще всего просто вернуть существующий объект, т.к. ID не меняется
            db_api_key.encrypted_api_key = encrypted_key # Обновляем в памяти для возврата, если нужно
            db_api_key.updated_at = datetime.datetime.utcnow()
            if username:
                db_api_key.created_by = username
            await db.flush() # Убедимся, что изменения записаны перед возвратом
            await db.refresh(db_api_key) # Обновим объект из БД
            return db_api_key
        else:
            # Создаем новый ключ
            logger.info(f"Создание нового API ключа для провайдера: {api_key_data.provider}")
            db_api_key = ApiKey(
                provider=api_key_data.provider,
                encrypted_api_key=encrypted_key,
                created_by=username
            )
            db.add(db_api_key)
            await db.flush() # Получаем ID
            await db.refresh(db_api_key) # Обновляем объект из БД
            return db_api_key
    except IntegrityError as e:
        logger.error(f"Ошибка целостности БД при сохранении ключа для {api_key_data.provider}: {e}")
        await db.rollback()
        raise ValueError(f"Не удалось сохранить ключ для {api_key_data.provider}: ошибка целостности данных")
    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при сохранении ключа для {api_key_data.provider}: {e}")
        await db.rollback()
        raise ValueError(f"Не удалось сохранить ключ для {api_key_data.provider}: {str(e)}")

async def get_api_key(db: AsyncSession, provider: str) -> Optional[str]:
    """Получает API ключ из базы данных и расшифровывает его."""
    try:
        query = await db.execute(
            ApiKey.__table__.select().where(ApiKey.provider == provider)
        )
        row = query.first()
        if row:
            # Расшифровываем ключ перед возвратом
            return decrypt_data(row.encrypted_api_key)
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении API ключа для {provider}: {e}")
        return None

async def check_api_key_exists(db: AsyncSession, provider: str, username: Optional[str] = None) -> bool:
    """
    Проверяет, существует ли API ключ для указанного провайдера.
    
    Args:
        db: Асинхронная сессия SQLAlchemy
        provider: Идентификатор провайдера (например, 'openai')
        username: Опциональное имя пользователя, если нужно проверить для конкретного пользователя
    
    Returns:
        bool: True, если ключ существует, False в противном случае
    """
    try:
        # Базовый запрос
        query = ApiKey.__table__.select().where(ApiKey.provider == provider)
        
        # Если указан пользователь, добавляем условие
        if username:
            query = query.where(ApiKey.created_by == username)
        
        # Выполняем запрос
        result = await db.execute(query)
        
        # Проверяем наличие результата
        return result.first() is not None
    except Exception as e:
        logger.error(f"Ошибка при проверке существования API ключа для {provider}: {e}")
        return False

async def get_all_api_keys_info(db: AsyncSession) -> List[ApiKeyRead]:
    """Получает информацию обо всех сохраненных ключах (без самих ключей)."""
    from sqlalchemy import select
    stmt = select(ApiKey)
    result = await db.execute(stmt)
    keys = result.scalars().all()
    # Преобразуем в Pydantic модель, которая маскирует ключ
    return [ApiKeyRead.model_validate(key) for key in keys]

async def delete_api_key(db: AsyncSession, provider: str) -> bool:
    """Удаляет API ключ для провайдера."""
    from sqlalchemy import delete
    try:
        stmt = delete(ApiKey).where(ApiKey.provider == provider)
        result = await db.execute(stmt)
        # result.rowcount > 0 означает, что строка была удалена
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"API ключ для провайдера {provider} удален.")
        else:
            logger.warning(f"Попытка удаления несуществующего API ключа для провайдера: {provider}")
        return deleted
    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при удалении ключа для {provider}: {e}")
        await db.rollback()
        raise ValueError(f"Не удалось удалить ключ для {provider}: {str(e)}")

# --- CRUD операции для SystemPrompt ---

async def create_or_update_system_prompt(db: AsyncSession, prompt_data: SystemPromptCreate, username: Optional[str] = None) -> SystemPrompt:
    """Создает или обновляет системный промт для модели."""
    from sqlalchemy import select, update
    
    # Проверяем, существует ли промт для этой модели
    stmt_select = select(SystemPrompt).where(
        SystemPrompt.model_id == prompt_data.model_id,
        SystemPrompt.is_default == True
    )
    result = await db.execute(stmt_select)
    db_prompt = result.scalar_one_or_none()
    
    try:
        if db_prompt:
            # Обновляем существующий промт
            logger.info(f"Обновление системного промта для модели: {prompt_data.model_id}")
            stmt_update = (
                update(SystemPrompt)
                .where(
                    SystemPrompt.model_id == prompt_data.model_id,
                    SystemPrompt.is_default == True
                )
                .values(
                    prompt_text=prompt_data.prompt_text,
                    updated_at=datetime.datetime.utcnow(),
                    created_by=username if username else db_prompt.created_by
                )
            )
            await db.execute(stmt_update)
            await db.refresh(db_prompt)
            return db_prompt
        else:
            # Создаем новый промт
            logger.info(f"Создание нового системного промта для модели: {prompt_data.model_id}")
            db_prompt = SystemPrompt(
                model_id=prompt_data.model_id,
                prompt_text=prompt_data.prompt_text,
                is_default=True,
                created_by=username
            )
            db.add(db_prompt)
            await db.flush()
            await db.refresh(db_prompt)
            return db_prompt
    except IntegrityError as e:
        logger.error(f"Ошибка целостности БД при сохранении промта для {prompt_data.model_id}: {e}")
        await db.rollback()
        raise ValueError(f"Не удалось сохранить промт для {prompt_data.model_id}: ошибка целостности данных")
    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при сохранении промта для {prompt_data.model_id}: {e}")
        await db.rollback()
        raise ValueError(f"Не удалось сохранить промт для {prompt_data.model_id}: {str(e)}")

async def get_system_prompt(db: AsyncSession, model_id: str) -> Optional[str]:
    """Получает текст системного промта для указанной модели."""
    from sqlalchemy import select
    stmt = select(SystemPrompt.prompt_text).where(
        SystemPrompt.model_id == model_id,
        SystemPrompt.is_default == True
    )
    result = await db.execute(stmt)
    prompt_text = result.scalar_one_or_none()
    
    # Если промта нет для конкретной модели, попробуем найти для провайдера
    if not prompt_text and '/' in model_id:
        provider = model_id.split('/')[0]
        stmt = select(SystemPrompt.prompt_text).where(
            SystemPrompt.model_id.like(f"{provider}/%"),
            SystemPrompt.is_default == True
        )
        result = await db.execute(stmt)
        prompt_text = result.scalar_one_or_none()
        
    # Если все равно нет, используем дефолтный из настроек
    if not prompt_text:
        return settings.default_system_prompt
        
    return prompt_text

async def get_all_system_prompts(db: AsyncSession) -> List[SystemPromptRead]:
    """Получает все системные промты."""
    from sqlalchemy import select
    stmt = select(SystemPrompt)
    result = await db.execute(stmt)
    prompts = result.scalars().all()
    
    return [SystemPromptRead.model_validate(prompt) for prompt in prompts]

async def delete_system_prompt(db: AsyncSession, model_id: str) -> bool:
    """Удаляет системный промт для модели."""
    from sqlalchemy import delete
    try:
        stmt = delete(SystemPrompt).where(
            SystemPrompt.model_id == model_id,
            SystemPrompt.is_default == True
        )
        result = await db.execute(stmt)
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Системный промт для модели {model_id} удален.")
        else:
            logger.warning(f"Попытка удаления несуществующего системного промта для модели: {model_id}")
        return deleted
    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при удалении промта для {model_id}: {e}")
        await db.rollback()
        raise ValueError(f"Не удалось удалить промт для {model_id}: {str(e)}")

# --- CRUD операции для PromptTemplate ---

async def create_prompt_template(db: AsyncSession, template_data: dict, username: Optional[str] = None):
    """Создает новый шаблон промта."""
    try:
        # Создаем новый шаблон
        new_template = PromptTemplate(
            name=template_data.get("name"),
            description=template_data.get("description"),
            prompt_text=template_data.get("prompt_text"),
            tags=template_data.get("tags"),
            created_by=username,
            is_public=template_data.get("is_public", True)
        )
        
        db.add(new_template)
        await db.commit()
        await db.refresh(new_template)
        
        logger.info(f"Создан новый шаблон промта: {new_template.name}")
        return new_template
    except IntegrityError as e:
        await db.rollback()
        logger.error(f"Ошибка при создании шаблона промта: {e}")
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Неожиданная ошибка при создании шаблона промта: {e}")
        raise

async def get_prompt_templates(db: AsyncSession, username: Optional[str] = None, tag: Optional[str] = None):
    """Получает список шаблонов промтов.
    
    Если username указан, возвращает шаблоны, созданные данным пользователем,
    а также публичные шаблоны. Если tag указан, фильтрует шаблоны по тегу.
    """
    try:
        from sqlalchemy import select, or_
        
        # Базовый запрос
        query = select(PromptTemplate)
        
        # Добавляем фильтры
        if username:
            # Пользователь видит свои шаблоны и публичные шаблоны
            query = query.where(or_(
                PromptTemplate.created_by == username,
                PromptTemplate.is_public == True
            ))
        else:
            # Без пользователя показываем только публичные шаблоны
            query = query.where(PromptTemplate.is_public == True)
            
        # Фильтр по тегу
        if tag:
            query = query.where(PromptTemplate.tags.like(f"%{tag}%"))
            
        # Сортировка по времени создания (сначала новые)
        query = query.order_by(PromptTemplate.created_at.desc())
        
        result = await db.execute(query)
        templates = result.scalars().all()
        
        return templates
    except Exception as e:
        logger.error(f"Ошибка при получении шаблонов промтов: {e}")
        raise

async def get_prompt_template_by_id(db: AsyncSession, template_id: int, username: Optional[str] = None):
    """Получает шаблон по ID. Учитывает права доступа."""
    try:
        from sqlalchemy import select, or_
        
        query = select(PromptTemplate).where(PromptTemplate.id == template_id)
        
        if username:
            # Пользователь может видеть свои шаблоны и публичные
            query = query.where(or_(
                PromptTemplate.created_by == username,
                PromptTemplate.is_public == True
            ))
        else:
            # Без пользователя только публичные
            query = query.where(PromptTemplate.is_public == True)
            
        result = await db.execute(query)
        template = result.scalar_one_or_none()
        
        return template
    except Exception as e:
        logger.error(f"Ошибка при получении шаблона промта по ID {template_id}: {e}")
        raise

async def update_prompt_template(db: AsyncSession, template_id: int, template_data: dict, username: Optional[str] = None):
    """Обновляет шаблон промта. Пользователь может обновлять только свои шаблоны."""
    try:
        from sqlalchemy import select
        
        # Сначала получаем существующий шаблон
        query = select(PromptTemplate).where(PromptTemplate.id == template_id)
        
        if username:
            # Только свои шаблоны можно редактировать
            query = query.where(PromptTemplate.created_by == username)
            
        result = await db.execute(query)
        template = result.scalar_one_or_none()
        
        if not template:
            return None
            
        # Обновляем поля
        if "name" in template_data:
            template.name = template_data["name"]
        if "description" in template_data:
            template.description = template_data["description"]
        if "prompt_text" in template_data:
            template.prompt_text = template_data["prompt_text"]
        if "tags" in template_data:
            template.tags = template_data["tags"]
        if "is_public" in template_data:
            template.is_public = template_data["is_public"]
            
        await db.commit()
        await db.refresh(template)
        
        logger.info(f"Обновлен шаблон промта: {template.name} (ID: {template.id})")
        return template
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка при обновлении шаблона промта {template_id}: {e}")
        raise

async def delete_prompt_template(db: AsyncSession, template_id: int, username: Optional[str] = None):
    """Удаляет шаблон промта. Пользователь может удалять только свои шаблоны."""
    try:
        from sqlalchemy import select, delete
        
        # Сначала проверяем, существует ли шаблон и принадлежит ли он пользователю
        query = select(PromptTemplate).where(PromptTemplate.id == template_id)
        
        if username:
            # Только свои шаблоны можно удалять
            query = query.where(PromptTemplate.created_by == username)
            
        result = await db.execute(query)
        template = result.scalar_one_or_none()
        
        if not template:
            return False
            
        # Удаляем шаблон
        delete_stmt = delete(PromptTemplate).where(PromptTemplate.id == template_id)
        await db.execute(delete_stmt)
        await db.commit()
        
        logger.info(f"Удален шаблон промта: {template.name} (ID: {template.id})")
        return True
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка при удалении шаблона промта {template_id}: {e}")
        raise

# --- CRUD операции для Rating ---

async def create_rating(db: AsyncSession, rating_data: RatingCreate, prompt_hash: str) -> Rating:
    """Создает новую запись рейтинга."""
    try:
        # Сохраняем первые 100 символов промта для удобства отладки
        prompt_excerpt = rating_data.prompt_text[:100] if rating_data.prompt_text else ""
        
        logger.info(f"Сохранение оценки для модели {rating_data.model_id} (hash: {prompt_hash[:8]}...): {rating_data.rating}/10")
        db_rating = Rating(
            model_id=rating_data.model_id,
            prompt_hash=prompt_hash, # Используем переданный хеш
            prompt_excerpt=prompt_excerpt,
            rating=rating_data.rating,
            comparison_winner=rating_data.comparison_winner,
            user_identifier=rating_data.user_identifier,
            # Новые поля
            system_prompt=rating_data.system_prompt,
            temperature=rating_data.temperature,
            max_tokens=rating_data.max_tokens,
            # timestamp генерируется по умолчанию
        )
        db.add(db_rating)
        await db.flush()
        await db.refresh(db_rating)
        return db_rating
    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при сохранении рейтинга: {e}")
        await db.rollback()
        raise ValueError(f"Не удалось сохранить рейтинг: {str(e)}")

async def get_ratings_for_model(db: AsyncSession, model_id: str, limit: int = 100) -> List[RatingRead]:
    """Получает последние N оценок для конкретной модели."""
    from sqlalchemy import select
    stmt = select(Rating).where(Rating.model_id == model_id).order_by(Rating.timestamp.desc()).limit(limit)
    result = await db.execute(stmt)
    ratings = result.scalars().all()
    return [RatingRead.model_validate(rating) for rating in ratings]

async def get_leaderboard_data(db: AsyncSession, category: Optional[str] = None) -> List[Tuple[str, float, int]]:
    """
    Получает агрегированные данные для лидерборда: (model_id, avg_rating, count).
    Фильтрует по категории, если она указана (пока фильтрация по категории не реализована на уровне БД,
    т.к. нет связи модели с категорией в таблице Rating).
    """
    from sqlalchemy import select, func

    # Группируем по model_id и вычисляем средний рейтинг и количество оценок
    stmt = (
        select(
            Rating.model_id,
            func.avg(Rating.rating).label('average_rating'),
            func.count(Rating.id).label('rating_count')
        )
        .group_by(Rating.model_id)
        .order_by(func.avg(Rating.rating).desc(), func.count(Rating.id).desc()) # Сортируем по среднему рейтингу, затем по количеству
    )

    # TODO: Добавить фильтрацию по категории, если это возможно
    # if category:
    #    # Потребуется JOIN с таблицей моделей или передача списка model_id для категории
    #    pass

    try:
        result = await db.execute(stmt)
        # Возвращаем список кортежей (model_id, avg_rating, count)
        # Преобразуем avg_rating в float, т.к. func.avg может вернуть Decimal
        leaderboard_raw = [(row.model_id, float(row.average_rating), row.rating_count) for row in result.all()]
        logger.debug(f"Сырые данные для лидерборда: {leaderboard_raw}")
        return leaderboard_raw
    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при получении данных лидерборда: {e}")
        # Не выполняем rollback, так как это запрос на чтение
        raise ValueError(f"Не удалось получить данные лидерборда: {str(e)}")

# --- Дополнительные полезные функции ---

async def get_model_rating_stats(db: AsyncSession, model_id: str) -> Dict[str, Any]:
    """Получает статистику рейтингов для конкретной модели."""
    from sqlalchemy import select, func
    
    try:
        # Собираем несколько метрик в одном запросе
        stmt = select(
            func.avg(Rating.rating).label('avg_rating'),
            func.min(Rating.rating).label('min_rating'),
            func.max(Rating.rating).label('max_rating'),
            func.count(Rating.id).label('rating_count')
        ).where(Rating.model_id == model_id)
        
        result = await db.execute(stmt)
        row = result.one_or_none()
        
        if not row:
            return {
                "model_id": model_id,
                "average_rating": 0.0,
                "min_rating": 0,
                "max_rating": 0,
                "rating_count": 0
            }
            
        return {
            "model_id": model_id,
            "average_rating": float(row.avg_rating) if row.avg_rating else 0.0,
            "min_rating": row.min_rating or 0,
            "max_rating": row.max_rating or 0,
            "rating_count": row.rating_count or 0
        }
    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при получении статистики рейтингов для {model_id}: {e}")
        # Возвращаем пустую статистику вместо исключения
        return {
            "model_id": model_id,
            "average_rating": 0.0,
            "min_rating": 0,
            "max_rating": 0,
            "rating_count": 0,
            "error": str(e)
        }

async def get_recent_user_ratings(db: AsyncSession, user_identifier: str, limit: int = 10) -> List[RatingRead]:
    """Получает последние оценки конкретного пользователя."""
    from sqlalchemy import select
    
    stmt = select(Rating).where(Rating.user_identifier == user_identifier).order_by(Rating.timestamp.desc()).limit(limit)
    result = await db.execute(stmt)
    ratings = result.scalars().all()
    return [RatingRead.model_validate(rating) for rating in ratings]

async def get_rating_statistics(db: AsyncSession) -> Dict[str, Any]:
    """Получает общую статистику по рейтингам."""
    from sqlalchemy import select, func
    
    try:
        # Общее количество рейтингов
        stmt_count = select(func.count()).select_from(Rating)
        result_count = await db.execute(stmt_count)
        total_ratings = result_count.scalar() or 0
        
        # Общее количество уникальных моделей с рейтингами
        stmt_models = select(func.count(Rating.model_id.distinct()))
        result_models = await db.execute(stmt_models)
        unique_models = result_models.scalar() or 0
        
        # Средний рейтинг по всем моделям
        stmt_avg = select(func.avg(Rating.rating))
        result_avg = await db.execute(stmt_avg)
        average_rating = float(result_avg.scalar() or 0)
        
        # Количество рейтингов по провайдерам
        stmt_providers = select(
            func.substr(Rating.model_id, 1, func.instr(Rating.model_id, '/')-1).label('provider'),
            func.count().label('count')
        ).group_by('provider')
        result_providers = await db.execute(stmt_providers)
        providers_stats = {row.provider: row.count for row in result_providers}
        
        # Последние рейтинги
        stmt_recent = select(Rating).order_by(Rating.timestamp.desc()).limit(5)
        result_recent = await db.execute(stmt_recent)
        recent_ratings = [
            {
                "model_id": rating.model_id,
                "rating": rating.rating,
                "timestamp": rating.timestamp.isoformat() if rating.timestamp else None
            }
            for rating in result_recent.scalars()
        ]
        
        return {
            "total_ratings": total_ratings,
            "unique_models": unique_models,
            "average_rating": average_rating,
            "providers_stats": providers_stats,
            "recent_ratings": recent_ratings
        }
    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при получении статистики рейтингов: {e}")
        return {
            "error": str(e),
            "total_ratings": 0,
            "unique_models": 0,
            "average_rating": 0.0
        }