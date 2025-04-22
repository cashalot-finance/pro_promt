#!/usr/bin/env python
"""
Скрипт настройки и проверки окружения для Промт Арены
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import List, Tuple, Dict, Optional

# Цвета для вывода в консоль
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Пути
CURRENT_DIR = Path(__file__).parent
BACKEND_DIR = CURRENT_DIR / "backend"
FRONTEND_DIR = CURRENT_DIR / "frontend"
DATA_DIR = CURRENT_DIR / "data"
ENV_FILE = CURRENT_DIR / ".env"

# Минимальные версии Python
MIN_PYTHON_VERSION = (3, 7)

def print_header(text: str):
    """Выводит заголовок с форматированием"""
    print(f"\n{BLUE}{BOLD}{text}{RESET}")

def print_ok(text: str):
    """Выводит успешное сообщение"""
    print(f"{GREEN}✓ {text}{RESET}")

def print_warning(text: str):
    """Выводит предупреждение"""
    print(f"{YELLOW}⚠ {text}{RESET}")

def print_error(text: str):
    """Выводит сообщение об ошибке"""
    print(f"{RED}✗ {text}{RESET}")

def verify_python_version() -> bool:
    """Проверяет версию Python"""
    print_header("Проверка версии Python")
    
    major, minor = sys.version_info.major, sys.version_info.minor
    version_str = f"{major}.{minor}"
    
    if (major, minor) >= MIN_PYTHON_VERSION:
        print_ok(f"Установлен Python {version_str} (минимальная версия {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]})")
        return True
    else:
        print_error(f"Установлен Python {version_str}, но требуется {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]} или выше")
        return False

def check_directory_structure() -> bool:
    """Проверяет и создает структуру директорий проекта"""
    print_header("Проверка структуры директорий")
    
    needed_dirs = [
        (BACKEND_DIR, "директория с бэкендом"),
        (FRONTEND_DIR, "директория с фронтендом"), 
        (DATA_DIR, "директория для данных")
    ]
    
    all_ok = True
    for path, desc in needed_dirs:
        if not path.exists():
            try:
                path.mkdir(parents=True)
                print_ok(f"Создана {desc}: {path}")
            except Exception as e:
                print_error(f"Не удалось создать {desc}: {path}. Ошибка: {e}")
                all_ok = False
        else:
            if path.is_dir():
                print_ok(f"Найдена {desc}: {path}")
            else:
                print_error(f"{path} существует, но это не директория")
                all_ok = False
    
    return all_ok

def check_requirements() -> bool:
    """Проверяет наличие файла requirements.txt"""
    print_header("Проверка файла requirements.txt")
    
    req_file = BACKEND_DIR / "requirements.txt"
    if not req_file.exists():
        print_error(f"Файл {req_file} не найден")
        return False
    
    print_ok(f"Файл requirements.txt найден")
    return True

def install_dependencies() -> bool:
    """Устанавливает зависимости из requirements.txt"""
    print_header("Установка зависимостей")
    
    req_file = BACKEND_DIR / "requirements.txt"
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
            check=True
        )
        print_ok("Зависимости установлены успешно")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Ошибка при установке зависимостей: {e}")
        return False

def setup_env_file() -> bool:
    """Создает файл .env если он не существует"""
    print_header("Настройка конфигурации (.env)")
    
    if ENV_FILE.exists():
        print_ok(f"Файл .env уже существует: {ENV_FILE}")
        return True
    
    try:
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
    except ImportError:
        # Если cryptography не установлена, используем базовый генератор
        import base64
        import secrets
        key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    
    try:
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write(f"# Автоматически сгенерированный файл конфигурации\n\n")
            f.write(f"# Ключ шифрования для API ключей (не меняйте его после создания БД!)\n")
            f.write(f"ENCRYPTION_KEY={key}\n\n")
            f.write(f"# Путь к базе данных SQLite\n")
            f.write(f"DATABASE_URL=sqlite+aiosqlite:///./data/prompt_arena.db\n\n")
            f.write(f"# Уровень логирования (DEBUG, INFO, WARNING, ERROR)\n")
            f.write(f"LOG_LEVEL=INFO\n\n")
            f.write(f"# Разрешенные источники для CORS\n")
            f.write(f"CORS_ORIGINS=[\"*\"]\n\n")
            f.write(f"# Токен Hugging Face Hub (опционально)\n")
            f.write(f"# HUGGING_FACE_HUB_TOKEN=\n")
        
        print_ok(f"Файл .env создан с базовыми настройками: {ENV_FILE}")
        return True
    except Exception as e:
        print_error(f"Ошибка при создании файла .env: {e}")
        return False

def setup_docker() -> bool:
    """Проверяет наличие Docker файлов"""
    print_header("Проверка файлов Docker")
    
    docker_files = [
        (CURRENT_DIR / "Dockerfile", "Dockerfile"),
        (CURRENT_DIR / "docker-compose.yml", "docker-compose.yml")
    ]
    
    all_ok = True
    for path, name in docker_files:
        if path.exists():
            print_ok(f"Файл {name} найден")
        else:
            print_warning(f"Файл {name} не найден. Docker-запуск будет недоступен.")
            all_ok = False
    
    if all_ok:
        print_ok("Все файлы Docker на месте. Вы можете запустить приложение через Docker.")
    else:
        print_warning("Для запуска через Docker создайте недостающие файлы.")
    
    return all_ok

def main():
    """Основная функция настройки проекта"""
    print(f"\n{BOLD}=== Установка и настройка Промт Арены ==={RESET}\n")
    
    # Проверка версии Python
    if not verify_python_version():
        print_error("Требуется Python 3.7 или выше. Установка прервана.")
        sys.exit(1)
    
    # Проверка и создание директорий
    if not check_directory_structure():
        print_warning("Не все директории удалось создать. Это может вызвать проблемы при работе.")
    
    # Проверка requirements.txt
    if not check_requirements():
        print_error("Файл requirements.txt не найден. Невозможно продолжить установку.")
        sys.exit(1)
    
    # Установка зависимостей
    if not install_dependencies():
        print_error("Ошибка при установке зависимостей. Приложение может работать некорректно.")
    
    # Настройка .env
    if not setup_env_file():
        print_warning("Не удалось создать файл .env. Вам нужно создать его вручную.")
    
    # Проверка файлов Docker
    setup_docker()
    
    # Информация о запуске
    print_header("Установка завершена")
    print(f"{BOLD}Для запуска приложения используйте:{RESET}")
    print(f"  • Обычный запуск: {GREEN}python run.py{RESET}")
    print(f"  • Docker: {GREEN}docker-compose up{RESET}")
    print(f"\n{BOLD}Документация API будет доступна по адресу:{RESET}")
    print(f"  • {BLUE}http://localhost:8000/api/v1/docs{RESET}")
    print(f"\n{BOLD}Веб-интерфейс будет доступен по адресу:{RESET}")
    print(f"  • {BLUE}http://localhost:8000{RESET}")

if __name__ == "__main__":
    main() 