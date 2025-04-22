# backend/utils.py

import os
import sys
import time
import socket
import logging
import hashlib
import platform
import requests
import netifaces
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

logger = logging.getLogger(__name__)

# --- Функции для работы с файловой системой ---

def ensure_directory_exists(path: str) -> bool:
    """Проверяет наличие директории и создает ее при необходимости."""
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Не удалось создать директорию {path}: {e}")
        return False

def get_project_root() -> Path:
    """Возвращает корневую директорию проекта."""
    return Path(__file__).parent.parent

# --- Функции для сетевой диагностики ---

def get_ip_addresses() -> Dict[str, Any]:
    """Получает информацию о сетевых интерфейсах и IP-адресах."""
    ip_info = {
        "local": [],
        "public": None,
        "hostname": socket.gethostname()
    }
    
    # Пытаемся получить локальные IP адреса
    try:
        # Используем netifaces для более надежного получения IP адресов
        for interface in netifaces.interfaces():
            try:
                # Пропускаем loopback
                if interface == 'lo' or interface.startswith('lo'):
                    continue
                    
                addresses = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addresses:
                    for addr in addresses[netifaces.AF_INET]:
                        ip = addr['addr']
                        # Пропускаем петлевые адреса
                        if not ip.startswith('127.'):
                            # Определяем, является ли интерфейс внутренним или внешним
                            ip_type = "internal" if ip.startswith(('10.', '172.16.', '192.168.')) else "external"
                            ip_info["local"].append({
                                "interface": interface,
                                "ip": ip,
                                "netmask": addr.get('netmask', '255.255.255.0'),
                                "type": ip_type
                            })
            except Exception as e:
                logger.debug(f"Ошибка при получении информации для интерфейса {interface}: {e}")
                continue
    except ImportError:
        # Если netifaces не установлен, используем более простой метод
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            if ip and not ip.startswith('127.'):
                ip_info["local"].append({
                    "interface": hostname,
                    "ip": ip,
                    "netmask": "255.255.255.0",
                    "type": "internal" if ip.startswith(('10.', '172.16.', '192.168.')) else "external"
                })
        except Exception as e:
            logger.debug(f"Ошибка при получении localhost IP: {e}")
    
    # Пробуем получить внешний IP через API
    try:
        external_ip_apis = [
            "https://api.ipify.org",
            "https://ipinfo.io/ip",
            "https://ifconfig.me/ip"
        ]
        
        for api in external_ip_apis:
            try:
                response = requests.get(api, timeout=3)
                if response.status_code == 200:
                    ip_info["public"] = response.text.strip()
                    break
            except requests.RequestException:
                continue
    except Exception as e:
        logger.debug(f"Ошибка при получении публичного IP: {e}")
    
    return ip_info

def check_port_available(port: int, host: str = '0.0.0.0') -> bool:
    """Проверяет, доступен ли порт."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result != 0
    except Exception as e:
        logger.debug(f"Ошибка при проверке порта {port}: {e}")
        return False

def generate_access_links(port: int = 8000, secure: bool = True) -> Dict[str, List[str]]:
    """
    Генерирует ссылки для доступа к приложению.
    
    Args:
        port: Порт, на котором запущено приложение
        secure: Использовать HTTPS или HTTP
        
    Returns:
        Dictionary с ключами 'local', 'public' и списками ссылок
    """
    ip_info = get_ip_addresses()
    links = {
        "local": [],
        "public": [],
        "internal_network": [],
        "share_message": ""
    }
    
    protocol = "https" if secure else "http"
    
    # Локальные ссылки всегда доступны
    links["local"].append(f"{protocol}://localhost:{port}")
    links["local"].append(f"{protocol}://127.0.0.1:{port}")
    
    # Добавляем локальные IP-адреса в сети
    for interface in ip_info["local"]:
        ip = interface["ip"]
        if interface.get("type") == "internal":
            links["internal_network"].append(f"{protocol}://{ip}:{port}")
        else:
            # Внешние IP-адреса
            links["public"].append(f"{protocol}://{ip}:{port}")
    
    # Публичный IP адрес, если доступен
    if ip_info["public"]:
        public_url = f"{protocol}://{ip_info['public']}:{port}"
        links["public"].append(public_url)
        
        # Создаем удобное сообщение для шаринга
        links["share_message"] = f"🔗 Ссылка для доступа к Промт Арене: {public_url}\n\n"\
                                f"Логин: 13guest\nПароль: 13\n\n"\
                                f"Откройте эту ссылку в браузере для доступа к приложению."
    
    return links

# --- Функции безопасности ---

def hash_password(password: str) -> str:
    """Хеширует пароль с помощью SHA-256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def generate_random_string(length: int = 32) -> str:
    """Генерирует случайную строку."""
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# --- Функции для мониторинга системы ---

def get_system_info() -> Dict[str, Any]:
    """Собирает общую информацию о системе."""
    info = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "processor": platform.processor(),
        "memory": get_memory_info(),
        "disk": get_disk_info()
    }
    return info

def get_memory_info() -> Dict[str, Any]:
    """Возвращает информацию о памяти."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "total": mem.total,
            "available": mem.available,
            "percent": mem.percent,
            "used": mem.used,
            "free": mem.free
        }
    except ImportError:
        return {
            "error": "psutil не установлен"
        }

def get_disk_info() -> Dict[str, Any]:
    """Возвращает информацию о дисковом пространстве."""
    try:
        import psutil
        disk = psutil.disk_usage('/')
        return {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent
        }
    except ImportError:
        return {
            "error": "psutil не установлен"
        }

# --- Функции для логирования и отладки ---

def setup_logger(log_level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """Настраивает и возвращает логгер."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Очищаем существующие обработчики
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Добавляем обработчик вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(console_handler)
    
    # Добавляем обработчик вывода в файл, если указан
    if log_file:
        # Создаем директорию для лога, если нужно
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(file_handler)
    
    return logger

# Функция для печати красивой стартовой информации
def print_startup_banner(version: str = "0.1.0"):
    """Печатает красивый баннер при запуске приложения."""
    banner = f"""
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║  ██████╗ ██████╗  ██████╗ ███╗   ███╗████████╗                   ║
║  ██╔══██╗██╔══██╗██╔═══██╗████╗ ████║╚══██╔══╝                   ║
║  ██████╔╝██████╔╝██║   ██║██╔████╔██║   ██║                      ║
║  ██╔═══╝ ██╔══██╗██║   ██║██║╚██╔╝██║   ██║                      ║
║  ██║     ██║  ██║╚██████╔╝██║ ╚═╝ ██║   ██║                      ║
║  ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝   ╚═╝                      ║
║  ███████╗██████╗ ███████╗██████╗ ███████╗ █████╗                 ║
║  ██╔════╝██╔══██╗██╔════╝██╔══██╗██╔════╝██╔══██╗                ║
║  █████╗  ██████╔╝█████╗  ██║  ██║█████╗  ███████║                ║
║  ██╔══╝  ██╔══██╗██╔══╝  ██║  ██║██╔══╝  ██╔══██║                ║
║  ██║     ██║  ██║███████╗██████╔╝███████╗██║  ██║                ║
║  ╚═╝     ╚═╝  ╚═╝╚══════╝╚═════╝ ╚══════╝╚═╝  ╚═╝                ║
║                                                                   ║
║                      Версия: {version.ljust(8)}                        ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
    """
    print(banner)
    
    # Информация о системе
    system_info = f"""
    Операционная система: {platform.system()} {platform.release()}
    Python: {platform.python_version()}
    """
    print(system_info)

def check_dependencies():
    """Проверяет наличие всех необходимых зависимостей и выводит предупреждения в случае их отсутствия."""
    import importlib
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Словарь с названиями пакетов и информацией о них
    required_packages = {
        "huggingface_hub": {
            "critical": True,  # Критически важный для работы
            "purpose": "работы с моделями Hugging Face",
            "install_command": "pip install huggingface_hub==0.23.0"
        },
        "openai": {
            "critical": False,
            "purpose": "работы с API OpenAI",
            "install_command": "pip install openai==1.30.1"
        },
        "google.generativeai": {
            "package_name": "google-generativeai",
            "critical": False,
            "purpose": "работы с Google Gemini",
            "install_command": "pip install google-generativeai==0.6.0"
        },
        "anthropic": {
            "critical": False,
            "purpose": "работы с Anthropic Claude",
            "install_command": "pip install anthropic==0.27.0"
        },
        "mistralai": {
            "critical": False, 
            "purpose": "работы с Mistral AI",
            "install_command": "pip install mistralai==0.3.0"
        },
        "groq": {
            "critical": False,
            "purpose": "работы с Groq API",
            "install_command": "pip install groq==0.8.0"
        }
    }
    
    missing_packages = []
    missing_critical = False
    
    for package_import, info in required_packages.items():
        try:
            if "." in package_import:  # Обрабатываем импорты с точкой, как google.generativeai
                main_package = package_import.split(".")[0]
                importlib.import_module(main_package)
            else:
                importlib.import_module(package_import)
                
            # Проверяем версию для huggingface_hub
            if package_import == "huggingface_hub":
                import huggingface_hub
                version = getattr(huggingface_hub, "__version__", "неизвестно")
                logger.info(f"Библиотека 'huggingface_hub' успешно импортирована, версия: {version}")
                
        except ImportError:
            package_name = info.get("package_name", package_import)
            purpose = info.get("purpose", "не указано")
            install_command = info.get("install_command", f"pip install {package_name}")
            
            message = f"Библиотека '{package_name}' не установлена. Функциональность {purpose} будет недоступна."
            
            if info.get("critical", False):
                logger.error(message)
                logger.error(f"Для установки выполните: {install_command}")
                missing_critical = True
            else:
                logger.warning(message)
                logger.warning(f"Для установки выполните: {install_command}")
                
            missing_packages.append(package_name)
    
    if missing_packages:
        if missing_critical:
            logger.error(f"Отсутствуют критически важные зависимости: {', '.join(missing_packages)}")
            logger.error("Некоторая функциональность будет недоступна!")
        else:
            logger.warning(f"Отсутствуют некоторые зависимости: {', '.join(missing_packages)}")
            logger.warning("Часть функциональности может быть недоступна.")
    else:
        logger.info("Все необходимые зависимости установлены.")
    
    return missing_critical, missing_packages