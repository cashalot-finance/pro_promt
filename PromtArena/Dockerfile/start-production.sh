#!/bin/bash

# Скрипт запуска Промт Арены в продакшен-режиме

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Заголовок
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║                                                                   ║"
echo "║  ██████╗ ██████╗  ██████╗ ███╗   ███╗████████╗                   ║"
echo "║  ██╔══██╗██╔══██╗██╔═══██╗████╗ ████║╚══██╔══╝                   ║"
echo "║  ██████╔╝██████╔╝██║   ██║██╔████╔██║   ██║                      ║"
echo "║  ██╔═══╝ ██╔══██╗██║   ██║██║╚██╔╝██║   ██║                      ║"
echo "║  ██║     ██║  ██║╚██████╔╝██║ ╚═╝ ██║   ██║                      ║"
echo "║  ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝   ╚═╝                      ║"
echo "║  ███████╗██████╗ ███████╗██████╗ ███████╗ █████╗                 ║"
echo "║  ██╔════╝██╔══██╗██╔════╝██╔══██╗██╔════╝██╔══██╗                ║"
echo "║  █████╗  ██████╔╝█████╗  ██║  ██║█████╗  ███████║                ║"
echo "║  ██╔══╝  ██╔══██╗██╔══╝  ██║  ██║██╔══╝  ██╔══██║                ║"
echo "║  ██║     ██║  ██║███████╗██████╔╝███████╗██║  ██║                ║"
echo "║  ╚═╝     ╚═╝  ╚═╝╚══════╝╚═════╝ ╚══════╝╚═╝  ╚═╝                ║"
echo "║                                                                   ║"
echo "║                 Запуск в продакшен-режиме                        ║"
echo "║                                                                   ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Переход в директорию проекта
# Получаем директорию, в которой находится скрипт
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo -e "${YELLOW}[ПРЕДУПРЕЖДЕНИЕ]${NC} Файл .env не найден. Создаем из .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${GREEN}[OK]${NC} Файл .env создан. Пожалуйста, отредактируйте его с вашими настройками."
    else
        echo -e "${RED}[ОШИБКА]${NC} Файл .env.example не найден. Пожалуйста, создайте файл .env вручную."
        exit 1
    fi
fi

# Проверка наличия директории data
if [ ! -d data ]; then
    echo -e "${YELLOW}[СОЗДАНИЕ]${NC} Создание директории для данных..."
    mkdir -p data
    echo -e "${GREEN}[OK]${NC} Директория data создана."
fi

# Выбор способа запуска
echo "Выберите способ запуска:"
echo "1. Через Docker (рекомендуется)"
echo "2. Напрямую через Python"
read -p "Введите номер (1/2): " choice

case $choice in
    1)
        # Запуск через Docker
        echo -e "${BLUE}[ЗАПУСК]${NC} Запуск через Docker..."
        
        # Проверка наличия Docker
        if ! command -v docker &> /dev/null; then
            echo -e "${RED}[ОШИБКА]${NC} Docker не установлен. Пожалуйста, установите Docker и Docker Compose."
            exit 1
        fi
        
        # Проверка наличия Docker Compose
        if ! command -v docker-compose &> /dev/null; then
            echo -e "${RED}[ОШИБКА]${NC} Docker Compose не установлен. Пожалуйста, установите Docker Compose."
            exit 1
        fi
        
        # Запуск через Docker Compose
        echo -e "${YELLOW}[СБОРКА]${NC} Сборка Docker образа (может занять некоторое время)..."
        docker-compose up --build -d
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}[УСПЕХ]${NC} Промт Арена запущена через Docker!"
            echo -e "Для остановки выполните: ${YELLOW}docker-compose down${NC}"
            
            # Получение IP адреса для доступа
            PUBLIC_IP=$(curl -s https://api.ipify.org || curl -s https://ifconfig.me)
            echo -e "${BLUE}[ИНФО]${NC} Приложение доступно по адресам:"
            echo -e "Локально: ${GREEN}http://localhost:8000${NC}"
            if [ ! -z "$PUBLIC_IP" ]; then
                echo -e "Внешний доступ: ${GREEN}http://$PUBLIC_IP:8000${NC}"
                
                # Сообщение для шаринга
                echo -e "\n${BLUE}[ДОСТУП]${NC} Для предоставления доступа другим пользователям:"
                echo -e "🔗 Ссылка для доступа к Промт Арене: http://$PUBLIC_IP:8000"
                echo -e "Логин: 13guest"
                echo -e "Пароль: 13"
            else
                echo -e "${YELLOW}[ПРЕДУПРЕЖДЕНИЕ]${NC} Не удалось определить внешний IP."
            fi
        else
            echo -e "${RED}[ОШИБКА]${NC} Не удалось запустить через Docker. Проверьте ошибки выше."
            exit 1
        fi
        ;;
    2)
        # Запуск через Python напрямую
        echo -e "${BLUE}[ЗАПУСК]${NC} Запуск через Python..."
        
        # Проверка наличия Python
        if ! command -v python3 &> /dev/null; then
            echo -e "${RED}[ОШИБКА]${NC} Python3 не установлен. Пожалуйста, установите Python 3.7 или выше."
            exit 1
        fi
        
        # Проверка наличия виртуального окружения
        if [ ! -d "venv" ]; then
            echo -e "${YELLOW}[СОЗДАНИЕ]${NC} Создание виртуального окружения Python..."
            python3 -m venv venv
            echo -e "${GREEN}[OK]${NC} Виртуальное окружение создано."
        fi
        
        # Активация виртуального окружения
        echo -e "${BLUE}[АКТИВАЦИЯ]${NC} Активация виртуального окружения..."
        source venv/bin/activate
        
        # Установка зависимостей
        echo -e "${YELLOW}[УСТАНОВКА]${NC} Установка зависимостей..."
        pip install -r backend/requirements.txt
        
        # Запуск приложения с uvicorn
        echo -e "${BLUE}[ЗАПУСК]${NC} Запуск веб-сервера Uvicorn..."
        python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
        
        # Сохраняем PID в файл для возможности остановки
        echo $! > .prompt_arena.pid
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}[УСПЕХ]${NC} Промт Арена запущена через Python!"
            echo -e "Для остановки выполните: ${YELLOW}kill \$(cat .prompt_arena.pid)${NC}"
            
            # Получение IP адреса для доступа
            PUBLIC_IP=$(curl -s https://api.ipify.org || curl -s https://ifconfig.me)
            echo -e "${BLUE}[ИНФО]${NC} Приложение доступно по адресам:"
            echo -e "Локально: ${GREEN}http://localhost:8000${NC}"
            if [ ! -z "$PUBLIC_IP" ]; then
                echo -e "Внешний доступ: ${GREEN}http://$PUBLIC_IP:8000${NC}"
                
                # Сообщение для шаринга
                echo -e "\n${BLUE}[ДОСТУП]${NC} Для предоставления доступа другим пользователям:"
                echo -e "🔗 Ссылка для доступа к Промт Арене: http://$PUBLIC_IP:8000"
                echo -e "Логин: 13guest"
                echo -e "Пароль: 13"
            else
                echo -e "${YELLOW}[ПРЕДУПРЕЖДЕНИЕ]${NC} Не удалось определить внешний IP."
            fi
        else
            echo -e "${RED}[ОШИБКА]${NC} Не удалось запустить через Python. Проверьте ошибки выше."
            exit 1
        fi
        ;;
    *)
        echo -e "${RED}[ОШИБКА]${NC} Неверный выбор. Пожалуйста, введите 1 или 2."
        exit 1
        ;;
esac

echo -e "\n${BLUE}[ИНФО]${NC} Приложение успешно запущено!"
echo -e "Данные аутентификации:"
echo -e "  ► Администратор: ${GREEN}логин: 13${NC}, ${GREEN}пароль: 131313${NC}"
echo -e "  ► Гость: ${GREEN}логин: 13guest${NC}, ${GREEN}пароль: 13${NC}"