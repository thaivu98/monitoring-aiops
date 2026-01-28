# Hệ thống AIOps Phát hiện Bất thường (Anomaly Detection) v2

Phiên bản nâng cấp với khả năng xử lý chu kỳ (seasonality), làm sạch dữ liệu và chống spam alert.

## Tính năng mới (v2)
- **Seasonality Aware**: Nhận diện giờ cao điểm/thấp điểm qua features `hour`, `weekday`.
- **Auto Data Cleaning**: Tự động interpolate dữ liệu thiếu (NaN) từ Prometheus.
- **Anti-Spam**: Cơ chế "3/5" (chỉ báo lỗi nếu 3/5 lần check gần nhất bất thường).
- **Dynamic Config**: Tùy chỉnh độ nhạy (`contamination`) cho từng metric.

## Cài đặt & Chạy

1. **Yêu cầu**: Python 3.8+, Prometheus, Alertmanager (hoặc Docker).
2. **Cài đặt local**:
   ```bash
   # Cài đặt môi trường ảo
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   
   # Chạy service
   python main.py
   ```

### Chạy bằng Docker Compose (Khuyên dùng)

1. **Cấu hình**: Clone file mẫu và chỉnh sửa thông tin trong `.env`:
   ```bash
   cp .env.example .env
   # Sửa PROM_URL, ALERTMANAGER_URL và mật khẩu DB trong .env
   ```
2. **Khởi chạy**:
   ```bash
   docker-compose up -d --build
   ```
   *   Hệ thống tự động tạo database trong folder `./database`.
   *   Tự động khởi chạy **PostgreSQL 16** đi kèm extension **pgvector** (sẵn sàng cho các tính năng AI Similarity Search).
   *   Tự động khởi tạo schema và chạy engine.

## Cấu hình (.env)

Hệ thống sử dụng Environment Variables (hoặc file `.env`) để cấu hình:

```env
PROM_URL=http://localhost:9090           # URL của Prometheus
ALERTMANAGER_URL=http://localhost:9093   # URL của Alertmanager
DATABASE_URL=postgresql://...            # Connect string đến DB
PROM_QUERY=up                           # Query mặc định nếu không set
CONTAMINATION=0.05                      # Độ nhạy mặc định (0.01 - 0.1)
```

## Cấu trúc dự án

```text
.
├── app/
│   ├── core/       # Cấu hình & Database setup
│   ├── clients/    # Prometheus, Alertmanager, LLM clients
│   ├── models/     # SQLAlchemy models
│   ├── services/   # Anomaly Detection Engine logic
│   └── main.py     # Logic chạy chính
├── tests/          # Unit tests & Simulation tests
├── main.py         # Entry point (chống lỗi import)
└── docker-compose.yml
```

## Logic Anti-Spam
Hệ thống duy trì một bộ nhớ đệm (sliding window). Nếu metric có biểu đồ trạng thái: `[Norm, Anom, Norm, Anom, Anom]` -> 3/5 là Anomaly -> **Bắn Alert**.
Nếu chỉ là: `[Norm, Norm, Norm, Norm, Anom]` -> 1/5 -> **Bỏ qua** (coi là nhiễu).
