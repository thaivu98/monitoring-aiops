# 🚩 Trạng thái dự án AIOps (Project Status)

File này lưu giữ ngữ cảnh và tiến độ của dự án để AI và Con người có thể tiếp nối công việc ngay lập tức.

## 📍 Trạng thái hiện tại (Current Context)
- **Kiến trúc**: Toàn bộ code đã được dồn vào thư mục `app/`. Chạy ở chế độ Daemon (vòng lặp 1 phút).
- **Database**: PostgreSQL 16 + pgvector (đã kích hoạt extension `vector`).
- **Data Flow**: Incremental Sync (chỉ fetch delta từ Prometheus mỗi 1 phút và lưu vào `MetricValue`).
- **Học tập**: AI sử dụng 30 ngày (720h) dữ liệu quá khứ lưu tại local DB để phân tích.

## 🏆 Các mốc đã hoàn thành (Milestones)
- [x] Refactor cấu trúc thư mục phẳng (`app/`).
- [x] Đóng gói Docker Compose (App + Postgres).
- [x] Cơ chế Incremental Sync & Local Caching giúp giảm tải Prometheus.
- [x] Chế độ Daemon chạy ngầm liên tục 24/7.
- [x] Tài liệu README.md và .env.example chuyên nghiệp (Tiếng Việt).
- [x] Hệ thống phát hiện bất thường nâng cao (Sliding Window 3/5, Seasonality Aware).

## 🔍 Cách kiểm tra trạng thái (Diagnostics)
- **Qua Logs**: Chạy `docker-compose logs -f aiops-app`.
    - ⚡ `[STAGE: LEARNING]`: Đang nạp dữ liệu lịch sử.
    - 🔍 `[STAGE: MONITORING]`: AI đang hoạt động và giám sát lỗi.
- **Qua File Status**: Kiểm tra file `status.json` trong container để xem danh sách metric và số lượng dữ liệu đã học được.

## ⚠️ Lưu ý quan trọng (Important Notes)
- File cấu hình thực tế nằm ở `.env` (đã có trong `.gitignore`).
- Dữ liệu raw metric được lưu tại bảng `metric_values`, tự động xóa sau 30 ngày.
- Muốn test logic AI: Chạy `PYTHONPATH=. python tests/test_anomaly.py` trong thư mục `app`.

## ⏭️ Kế hoạch tiếp theo (Roadmap & Priority)
Được trích xuất và ưu tiên từ [BACKLOG.md](file:///Users/thaivd/Downloads/AIOPS/ai_monitoring/monitoring-aiops/BACKLOG.md):

1. **Ưu tiên 1 (Short-term)**: Triển khai **Auto-Discovery** (Task 4.1) để hệ thống tự động nhận diện các job mới từ Prometheus.
2. **Ưu tiên 2 (Intelligence)**: Tích hợp **Log Correlation & RCA** (Task 2.1 & 2.2).
3. **Ưu tiên 3 (UX)**: Xây dựng **Web Dashboard** cơ bản (Task 3.2).

---

## 📖 Hướng dẫn cho phiên làm việc tiếp theo (Handover Instruction)
*Khi bạn quay lại và làm việc với AI (là tôi hoặc người kế nhiệm), hãy copy-paste câu lệnh này:*

> "Hãy đọc file `PROJECT_STATUS.md` và `BACKLOG.md` để nắm bắt ngữ cảnh dự án AIOps hiện tại, sau đó kiểm tra file `.env` và tiếp tục thực hiện Task [Tên Task/Số Task] trong Backlog."

---
*Cập nhật lần cuối: 28/01/2026 - 23:55*
