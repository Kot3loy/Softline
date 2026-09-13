FROM python:3.12-slim

# ffmpeg — нужен для voice обработки
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Устанавливаем зависимости (кэшируем слой)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

# Запуск от непривилегированного пользователя
RUN adduser --disabled-password --gecos "" appuser
USER appuser

# Health check — pingаем health endpoint
HEALTHCHECK --interval=60s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "-m", "bot.main"]
