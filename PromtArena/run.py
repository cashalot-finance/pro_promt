#!/usr/bin/env python
"""
Скрипт для быстрого запуска Промт Арены
"""

import os
import sys
import time
import subprocess
import webbrowser
import secrets
import base64
from pathlib import Path

# Текущий путь и путь к файлу .env
CURRENT_DIR = Path(__file__).parent
ENV_FILE = CURRENT_DIR / ".env"
DATA_DIR = CURRENT_DIR / "data"

def generate_encryption_key():
    """Генерирует Fernet ключ для шифрования API ключей"""
    try:
        from cryptography.fernet import Fernet
        return Fernet.generate_key().decode()
    except ImportError:
        # Если cryptography не установлена, создаем случайный base64-строку
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()

def ensure_env_file():
    """Создает файл .env если он не существует"""
    if not ENV_FILE.exists():
        print("Создание файла .env с базовыми настройками...")
        
        # Проверяем/создаем директорию для данных
        if not DATA_DIR.exists():
            DATA_DIR.mkdir(parents=True)
            print(f"Создана директория для данных: {DATA_DIR}")
        
        # Генерируем ключ шифрования
        encryption_key = generate_encryption_key()
        
        # Создаем файл .env
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write(f"# Ключ шифрования для API ключей (не меняйте его после создания БД!)\n")
            f.write(f"ENCRYPTION_KEY={encryption_key}\n\n")
            f.write(f"# Путь к БД SQLite\n")
            f.write(f"DATABASE_URL=sqlite+aiosqlite:///./data/prompt_arena.db\n\n")
            f.write(f"# Уровень логирования (DEBUG, INFO, WARNING, ERROR)\n")
            f.write(f"LOG_LEVEL=INFO\n\n")
            f.write(f"# Разрешенные источники для CORS\n")
            f.write(f"CORS_ORIGINS=[\"*\"]\n")
        
        print(f"Файл .env создан и настроен.")
        return True
    return False

def check_dependencies():
    """Проверяет и устанавливает необходимые зависимости"""
    requirements_file = CURRENT_DIR / "backend" / "requirements.txt"
    
    if not requirements_file.exists():
        print("Ошибка: Файл requirements.txt не найден!")
        return False
    
    print("Проверка и установка зависимостей...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
            check=True
        )
        print("Зависимости установлены успешно.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при установке зависимостей: {e}")
        return False

def run_server():
    """Запускает сервер uvicorn"""
    host = "127.0.0.1"
    port = 8000
    
    print(f"Запуск сервера на http://{host}:{port}...")
    server_process = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", 
            "backend.main:app", 
            "--host", host, 
            "--port", str(port),
            "--reload"
        ],
        cwd=CURRENT_DIR
    )
    
    # Ждем запуска сервера
    print("Ожидание запуска сервера...")
    time.sleep(2)
    
    # Открываем браузер
    print("Открытие Промт Арены в браузере...")
    webbrowser.open(f"http://{host}:{port}")
    
    try:
        # Ждем, пока пользователь не нажмет Ctrl+C
        print("\nСервер запущен! Нажмите Ctrl+C для завершения...\n")
        server_process.wait()
    except KeyboardInterrupt:
        print("\nЗавершение работы сервера...")
        server_process.terminate()
        server_process.wait()
    
    print("Сервер остановлен.")

def main():
    """Основная функция запуска"""
    print("\n=== Промт Арена: Быстрый запуск ===\n")
    
    # Проверяем/создаем .env файл
    ensure_env_file()
    
    # Проверяем и устанавливаем зависимости
    if not check_dependencies():
        print("Не удалось установить необходимые зависимости. Завершение работы.")
        return
    
    # Запускаем сервер и открываем браузер
    run_server()

if __name__ == "__main__":
    main() 