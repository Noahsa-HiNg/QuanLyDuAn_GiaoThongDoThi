FROM python:3.11-slim

# Tránh Python tạo file .pyc và buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy requirements trước để tận dụng Docker layer cache
# (chỉ rebuild layer pip khi requirements.txt thay đổi)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ source code
COPY . .

# --reload: tự reload khi code thay đổi (phù hợp dev vì volume mount)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]