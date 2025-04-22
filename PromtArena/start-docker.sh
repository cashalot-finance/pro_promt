#!/bin/bash

echo "=========================================="
echo "  Запуск Промт Арены через Docker"
echo "=========================================="

# Проверка наличия Docker и Docker Compose
if ! command -v docker &> /dev/null; then
    echo "Ошибка: Docker не установлен. Пожалуйста, установите Docker."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Ошибка: Docker Compose не установлен. Пожалуйста, установите Docker Compose."
    exit 1
fi

# Проверяем, запущен ли Docker демон
if ! docker info &> /dev/null; then
    echo "Ошибка: Docker демон не запущен. Пожалуйста, запустите Docker."
    exit 1
fi

# Проверяем наличие .env файла
if [ ! -f .env ]; then
    echo "Файл .env не найден. Создаем его из примера..."
    cat > .env << EOL
# Ключ шифрования для API ключей (не меняйте его после создания БД!)
ENCRYPTION_KEY=BEAaatnZAwNNGgN333h8MyrFvC5t6rGgoEmWOOZ29AU=

# Путь к БД SQLite
DATABASE_URL=sqlite+aiosqlite:///./data/prompt_arena.db

# Уровень логирования (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# Разрешенные источники для CORS
CORS_ORIGINS=["*"]

# Настройки авторизации
AUTH_USERNAME=admin
AUTH_PASSWORD=131313
GUEST_USERNAME=guest
GUEST_PASSWORD=13
DISABLE_AUTH=false

# Настройки сервера
HOST=0.0.0.0
PORT=8000
DEBUG=false
EOL
    echo "Файл .env создан успешно!"
fi

# Создаем директорию для данных, если её нет
if [ ! -d "data" ]; then
    echo "Директория data не существует. Создаем..."
    mkdir -p data
    echo "Директория data создана!"
fi

# Проверяем наличие docker-compose-new.yml
if [ ! -f "docker-compose-new.yml" ]; then
    echo "Ошибка: Файл docker-compose-new.yml не найден!"
    exit 1
fi

# Проверяем наличие Dockerfile-new
if [ ! -f "Dockerfile-new" ]; then
    echo "Ошибка: Файл Dockerfile-new не найден!"
    exit 1
fi

echo "Запуск приложения через Docker Compose..."
docker-compose -f docker-compose-new.yml down
docker-compose -f docker-compose-new.yml up --build -d

echo "=========================================="
echo "  Промт Арена запущена!"
echo "  Доступ: http://localhost:8000"
echo "  Логи: docker-compose -f docker-compose-new.yml logs -f"
echo "  Остановка: docker-compose -f docker-compose-new.yml down"
echo "=========================================="

# Открываем браузер через 3 секунды (опционально)
echo "Открытие приложения в браузере через 3 секунды..."
sleep 3

# Определяем команду для открытия браузера в зависимости от ОС
case "$(uname -s)" in
    Linux*)     xdg-open http://localhost:8000 ;;
    Darwin*)    open http://localhost:8000 ;; # macOS
    CYGWIN*|MINGW*|MSYS*) start http://localhost:8000 ;; # Windows
    *)          echo "Откройте браузер и перейдите по адресу: http://localhost:8000" ;;
esac 