@echo off
echo ==========================================
echo   Запуск Промт Арены через Docker
echo ==========================================

REM Проверка наличия Docker
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Ошибка: Docker не установлен. Пожалуйста, установите Docker.
    pause
    exit /b 1
)

REM Проверка наличия Docker Compose
docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Ошибка: Docker Compose не установлен. Пожалуйста, установите Docker Compose.
    pause
    exit /b 1
)

REM Проверяем, запущен ли Docker демон
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Ошибка: Docker демон не запущен. Пожалуйста, запустите Docker Desktop.
    pause
    exit /b 1
)

REM Проверяем наличие .env файла
if not exist .env (
    echo Файл .env не найден. Создаем его из примера...
    (
        echo # Ключ шифрования для API ключей (не меняйте его после создания БД!)
        echo ENCRYPTION_KEY=BEAaatnZAwNNGgN333h8MyrFvC5t6rGgoEmWOOZ29AU=
        echo.
        echo # Путь к БД SQLite
        echo DATABASE_URL=sqlite+aiosqlite:///./data/prompt_arena.db
        echo.
        echo # Уровень логирования (DEBUG, INFO, WARNING, ERROR)
        echo LOG_LEVEL=INFO
        echo.
        echo # Разрешенные источники для CORS
        echo CORS_ORIGINS=["*"]
        echo.
        echo # Настройки авторизации
        echo AUTH_USERNAME=admin
        echo AUTH_PASSWORD=131313
        echo GUEST_USERNAME=guest
        echo GUEST_PASSWORD=13
        echo DISABLE_AUTH=false
        echo.
        echo # Настройки сервера
        echo HOST=0.0.0.0
        echo PORT=8000
        echo DEBUG=false
    ) > .env
    echo Файл .env создан успешно!
)

REM Создаем директорию для данных, если её нет
if not exist data (
    echo Директория data не существует. Создаем...
    mkdir data
    echo Директория data создана!
)

REM Проверяем наличие docker-compose-new.yml
if not exist docker-compose-new.yml (
    echo Ошибка: Файл docker-compose-new.yml не найден!
    pause
    exit /b 1
)

REM Проверяем наличие Dockerfile-new
if not exist Dockerfile-new (
    echo Ошибка: Файл Dockerfile-new не найден!
    pause
    exit /b 1
)

echo Запуск приложения через Docker Compose...
docker-compose -f docker-compose-new.yml down
docker-compose -f docker-compose-new.yml up --build -d

echo ==========================================
echo   Промт Арена запущена!
echo   Доступ: http://localhost:8000
echo   Логи: docker-compose -f docker-compose-new.yml logs -f
echo   Остановка: docker-compose -f docker-compose-new.yml down
echo ==========================================

REM Открываем браузер через 3 секунды
echo Открытие приложения в браузере через 3 секунды...
timeout /t 3 >nul
start http://localhost:8000

pause 