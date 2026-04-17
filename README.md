
Quản lý dự án phát triển hệ thống AI tổng hợp và phân tích dữ liệu đô thị ( Quản lý agent code)
Lưu ý:
Nhánh main chỉ chưa các code đã chạy được
nhánh phụ phải được đặt tên theo chức năng được triển khai trên nhánh đó

Khi mở code hãy nhập lệnh 
pip install -r requirements.txt
trên cmd để cài đặt các môi trường và công nghệ cần thiết, nếu code thêm môi trường hoặc công nghệ thì hãy thêm vào requirements.txt

Cây cấu trúc
QLDA_DULIEUDOTHI/         <-- Thư mục gốc của dự án
│
├── data/                        <-- PHÒNG CHỨA DỮ LIỆU (Chỉ chứa file, không chứa code)
│   ├── raw_traffic_1000.csv     (Dữ liệu thô Sprint 1 sinh ra)
│   └── clean_traffic_1000.csv   (Dữ liệu đã được AI ETL làm sạch)
│
├── models/                      <-- PHÒNG CHỨA BỘ NÃO AI
│   └── prediction_model.pkl     (File mô hình AI đã học xong từ nhóm Science)
│
├── src/                         <-- PHÒNG LÀM VIỆC CỦA ĐỘI BACKEND & DATA
│   ├── generator.py             (Code để Agent 1.2 sinh dữ liệu giả)
│   ├── cleaner.py               (Code để Agent 1.4 làm sạch dữ liệu nhiễu)
│   └── trainer.py               (Code để Agent 2.2 huấn luyện mô hình)
│
├── app.py                       <-- MẶT TIỀN CỦA DỰ ÁN (File chạy Dashboard Streamlit)
│
├── requirements.txt             <-- DANH SÁCH ĐỒ NGHỀ (Chứa tên các thư viện cần cài đặt)
└── README.md                    <-- BẢN HƯỚNG DẪN (Giới thiệu cách chạy dự án cho Giảng viên)
conda activate traffic_env