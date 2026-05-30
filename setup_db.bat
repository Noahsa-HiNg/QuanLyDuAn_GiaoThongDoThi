@echo off
REM ============================================================
REM setup_db.bat — Khởi tạo database cho teammate (Windows)
REM Chạy 1 lần sau khi clone repo hoặc khi cần reset streets/districts
REM ============================================================

echo [1/4] Khoi dong postgres...
docker compose up -d postgres
echo Doi postgres san sang (15 giay)...
timeout /t 15 /nobreak > nul

echo [2/4] Copy backup vao container...
FOR /F %%i IN ('docker compose ps -q postgres') DO SET PG_CONTAINER=%%i
docker cp data_export\load_streets_districts.sql %PG_CONTAINER%:/tmp/load_streets_districts.sql

echo [3/4] Load streets + districts tu backup...
docker compose exec postgres psql -U myadmin -d qlda_dothithongminh -f /tmp/load_streets_districts.sql

echo [4/4] Kiem tra ket qua...
docker compose exec postgres psql -U myadmin -d qlda_dothithongminh -c "SELECT 'districts' AS tabel, COUNT(*) FROM districts UNION ALL SELECT 'streets', COUNT(*) FROM streets;"

echo.
echo Xong! Chay tiep: docker compose up -d
echo Backend se tu crawl traffic data sau khi khoi dong.
pause
