#!/bin/bash
# ============================================================
# setup_db.sh — Khởi tạo / cập nhật database cho teammate mới
# Chạy 1 lần sau khi clone repo hoặc khi cần reset streets/districts
# ============================================================

echo "📦 Bước 1: Khởi động postgres container..."
docker compose up -d postgres
echo "⏳ Đợi postgres sẵn sàng..."
sleep 10

echo "📥 Bước 2: Load streets + districts từ backup..."
docker cp data_export/load_streets_districts.sql \
    $(docker compose ps -q postgres):/tmp/load_streets_districts.sql

docker compose exec postgres psql -U myadmin -d qlda_dothithongminh \
    -c "TRUNCATE TABLE traffic_data, streets, districts RESTART IDENTITY CASCADE;" \
    2>/dev/null || true

docker compose exec postgres psql -U myadmin -d qlda_dothithongminh \
    -f /tmp/load_streets_districts.sql

echo "✅ Bước 3: Kiểm tra kết quả..."
docker compose exec postgres psql -U myadmin -d qlda_dothithongminh \
    -c "SELECT 'districts' AS table, COUNT(*) FROM districts UNION ALL SELECT 'streets', COUNT(*) FROM streets;"

echo ""
echo "🎉 Xong! Bây giờ chạy: docker compose up -d"
echo "   Backend sẽ tự crawl traffic data sau khi khởi động."
