FROM python:3.11-slim

WORKDIR /app

# Копирование файлов зависимостей
COPY ../backend/requirements.txt .

# Установка зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Создание директории для данных
RUN mkdir -p /app/data

# Копирование кода приложения
COPY ../backend ./backend
COPY ../frontend ./frontend

# Порт для API
EXPOSE 8000

# Запуск приложения
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]