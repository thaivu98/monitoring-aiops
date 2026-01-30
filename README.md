# 🧠 Hệ thống AIOps Phát hiện Bất thường (Anomaly Detection) v2

Phiên bản nâng cấp mạnh mẽ với khả năng xử lý chu kỳ (seasonality), làm sạch dữ liệu bằng AI và cơ chế chống nhiễu cảnh báo thông minh.

---

## 🚀 Tính năng nổi bật

- **Nhận diện chu kỳ (Seasonality Aware)**: Tự động phân tích các đặc điểm thời gian (giờ trong ngày, ngày trong tuần) để hiểu các biểu đồ lưu lượng theo chu kỳ.
- **Cơ chế Local Caching (Incremental Sync)**: Hệ thống sử dụng PostgreSQL để lưu giữ dữ liệu 30 ngày tại local. Thay vì kéo toàn bộ 30 ngày từ Prometheus mỗi chu kỳ, App sẽ chỉ kéo phần dữ liệu mới (delta) phát sinh, giúp giảm tải Prometheus gấp hàng trăm lần.
- **Tự động làm sạch dữ liệu (Auto Data Cleaning)**: Sử dụng thuật toán nội suy (Interpolation) để lấp đầy các khoảng trống dữ liệu bị thiếu từ Prometheus.
- **Cơ chế Chống nhiễu (Anti-Spam)**: Áp dụng logic **Sliding Window 3/5** (chỉ bắn alert nếu phát hiện 3/5 điểm bất thường liên tiếp), giúp giảm thiểu báo động giả do nhiễu tức thời.
- **Hạ tầng AI-Ready**: Sử dụng **PostgreSQL 16** đi kèm extension **pgvector**, sẵn sàng cho các tính năng tìm kiếm lỗi tương tự bằng Vector Similarity Search.

---

## 🏗️ Cấu trúc dự án

Dự án được cấu trúc theo mô hình phẳng bên trong thư mục `app/` để tối ưu hóa việc đóng gói và triển khai:

```text
.
├── app/                    # Toàn bộ mã nguồn ứng dụng
│   ├── clients/            # Kết nối: Prometheus, Alertmanager, LLM
│   ├── core/               # Cấu hình hệ thống & Khởi tạo Database
│   ├── models/             # Định nghĩa cấu trúc bảng dữ liệu (SQLAlchemy)
│   ├── services/           # Trái tim AI: Engine phát hiện bất thường
│   ├── tests/              # Hệ thống kiểm thử (Unit tests)
│   ├── main.py             # File thực thi chính
│   └── requirements.txt    # Danh sách thư viện Python cần thiết
├── database/               # Dữ liệu PostgreSQL (được mount từ container)
├── Dockerfile              # Cấu hình đóng gói Container
├── docker-compose.yml      # Quản lý dịch vụ (App + Postgres)
├── .env.example            # File cấu hình mẫu
└── README.md
```

---

## 🛠️ Hướng dẫn cài đặt & Triển khai

### Cách 1: Sử dụng Docker Compose (Khuyên dùng)

Đây là cách nhanh nhất và đảm bảo môi trường hoạt động ổn định nhất.

1.  **Thiết lập cấu hình**:
    ```bash
    cp .env.example .env
    # Mở file .env và cập nhật PROM_URL, ALERTMANAGER_URL cùng mật khẩu DB.
    ```
2.  **Khởi chạy**:
    ```bash
    docker-compose up -d --build
    ```
    *   Hệ thống sẽ tự khởi tạo Database PostgreSQL 16 tại folder `./database`.
    *   Dịch vụ AIOps sẽ tự động kết nối và bắt đầu quét dữ liệu theo chu kỳ.

### Cách 2: Cài đặt thủ công (Local Development)

1.  **Yêu cầu**: Python 3.13+, PostgreSQL 16.
2.  **Cài đặt**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r app/requirements.txt
    ```
3.  **Chạy ứng dụng**:
    ```bash
    cd app
    PYTHONPATH=. python main.py
    ```

---

## ⚙️ Giải thích cấu hình (.env)

| `PROM_QUERY` | Câu lệnh PromQL để lấy dữ liệu (Ví dụ: `up`, `{job="node-exporter"}`) |
| `CHECK_INTERVAL_MINUTES` | Tần suất chạy quét (Mặc định: 1 phút) |
| `LOOKBACK_HOURS` | Số giờ dữ liệu quá khứ để AI học (Mặc định: 720h = 30 ngày) |
| `ALERT_REPEAT_INTERVAL_MINUTES` | Thời gian lặp lại cảnh báo nếu lỗi chưa sửa (Mặc định: 60) |
| `CONTAMINATION` | Độ nhạy của thuật toán (Phạm vi: 0.01 - 0.1) |
| `DATABASE_URL` | Chuỗi kết nối đến PostgreSQL |
| `PROM_URL` | Địa chỉ hệ thống Prometheus lấy metric |
| `ALERTMANAGER_URL` | Địa chỉ Alertmanager để gửi cảnh báo |

---

## 📖 Hướng dẫn cấu hình Giám sát (Usage Guide)

AIOps Engine có thể học và giám sát bất kỳ chỉ số (metric) nào mà Prometheus cung cấp. Bạn chỉ cần thay đổi giá trị `PROM_QUERY` trong file `.env`.

### 1. Giám sát Sống/Chết (Server Availability)
Đây là cấu hình mặc định, AI sẽ báo động ngay lập tức nếu server sập (`up=0`).
```env
PROM_QUERY=up
```

### 2. Giám sát Hiệu năng (Performance Monitoring)
AI sẽ tự học ngưỡng (baseline) của CPU/RAM trong 30 ngày qua. Nếu CPU bình thường chạy 20% bỗng dưng vọt lên 90% và duy trì, AI sẽ gửi cảnh báo.

*   **Giám sát CPU (%)**:
    ```env
    PROM_QUERY=100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
    ```
*   **Giám sát RAM sử dụng (%)**:
    ```env
    PROM_QUERY=(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100
    ```

### 3. Giám sát Đa chỉ số (Multiple Metrics)
Bạn có thể bắt AI theo dõi nhiều thông số cùng một lúc bằng cách sử dụng Regex:
```env
PROM_QUERY={__name__=~"up|node_cpu_seconds_total|node_memory_MemAvailable_bytes"}
```

---

## 🤖 AI Engine vs Binary Guard

Hệ thống sử dụng cơ chế bảo vệ kép:
1.  **Binary Guard (Lớp bảo vệ cứng)**: Dành riêng cho metric `up`. Nếu giá trị rơi về `0`, hệ thống coi đây là lỗi nghiêm trọng và báo động ngay (Confidence 100%), không cần chờ AI học.
2.  **AI Engine (Isolation Forest)**: Dành cho các chỉ số biến thiên (CPU, RAM, Traffic). AI sẽ phân tích các điểm dữ liệu bất thường dựa trên mật độ và hình thái biểu đồ (Outlier Detection) so với dữ liệu lịch sử.

---

## ⚖️ Tần suất quét & Tải hệ thống

Để bảo vệ Prometheus không bị quá tải khi học dữ liệu dài hạn (30 ngày), bạn cần lưu ý:

1. **Khối lượng dữ liệu**: Với cơ chế **Incremental Sync**, mỗi lần quét 1 phút app chỉ lấy vài điểm dữ liệu mới. Tải cực kỳ thấp.
2. **Tối ưu hóa**: Mặc định là **1 phút** để đảm bảo tính thời gian thực. Nếu bạn giám sát hàng ngàn server, bạn có thể tăng lên 5 phút nếu cần.
3. **Timeout**: App đã được cấu hình tự động tăng timeout lên 30 giây để đảm bảo việc tải lượng lớn dữ liệu diễn ra trơn tru.

---

## 🧪 Kiểm thử (Testing)

Bạn có thể chạy hệ thống mô phỏng để kiểm tra khả năng phát hiện "Spike" (tăng vọt) hoặc "Trend" (xu hướng giảm dần) của Engine:

```bash
cd app
PYTHONPATH=. python tests/test_anomaly.py
```

---
*Phát triển bởi Đội ngũ AIOps - Tự động hóa giám sát thông minh.*
