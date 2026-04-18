FROM python:3.11-slim

# Tránh Python tạo file .pyc và buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy requirements trước để tận dụng Docker layer cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ source code
COPY . .

# Streamlit: tắt usage stats và welcome message khi chạy trong container
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--browser.gatherUsageStats=false", \
     "--server.headless=true"]