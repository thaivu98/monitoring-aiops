# 📋 AIOps Roadmap & Backlog

Danh sách các tính năng và cải tiến để đưa hệ thống tiến gần hơn tới các giải pháp Enterprise như LogicMonitor.

## 1. 🔗 Đa dạng nguồn dữ liệu (Multi-source)
Mở rộng khả năng thu thập dữ liệu ngoài Prometheus.
- [ ] **Task 1.1**: Hỗ trợ lấy dữ liệu từ Cloud (AWS CloudWatch, Azure Monitor).
- [ ] **Task 1.2**: Hỗ trợ lấy dữ liệu từ Log (Elasticsearch/Loki/Splunk) để phân kỳ lỗi.
- [ ] **Task 1.3**: Hỗ trợ SNMP cho thiết bị Network và WMI cho Windows servers.

## 2. 🤖 Tương quan sự kiện & RCA (Correlation & Root Cause)
Giúp AI không chỉ thấy lỗi mà còn hiểu "tại sao lỗi".
- [ ] **Task 2.1**: **Metric Correlation**: AI tự động tìm liên kết giữa các metric (ví dụ: CPU tăng do Java Restart, Disk I/O tăng do Database Backup).
- [ ] **Task 2.2**: **Cross-Source RCA**: Khi có anomaly, tự động fetch log/event 5 phút gần nhất để tìm nguyên nhân gốc (Root Cause).
- [ ] **Task 2.3**: **Topology Mapping**: Định nghĩa mối quan hệ giữa các service để hiểu lỗi lan truyền.

## 3. 📈 Dự báo & Dashboard (Forecasting & UI)
Trực quan hóa và nhìn về tương lai.
- [ ] **Task 3.1**: **Dự báo (Forecasting)**: Sử dụng mô hình Prophet hoặc Holt-Winters để dự báo khi nào ổ cứng đầy hoặc băng thông quá tải.
- [ ] **Task 3.2**: **Web Dashboard**: Xây dựng giao diện đơn giản (Streamlit hoặc React) để xem danh sách các Anomaly và Biểu đồ.
- [ ] **Task 3.3**: **Kpi Report**: Tự động gửi báo cáo sức khỏe hệ thống hàng tuần qua Email/Slack.

## 4. 🛠️ Quản trị & Tối ưu (Admin & Performance)
Nâng cao tính ổn định và dễ dùng.
- [ ] **Task 4.1**: **Auto-Discovery**: Tự động lấy danh sách job từ Prometheus API thay vì cấu hình cứng trong `.env`.
- [ ] **Task 4.2**: **Config UI**: Giao diện để chỉnh sửa `CHECK_INTERVAL` và `LOOKBACK` mà không cần restart container.
- [ ] **Task 4.3**: **Vector Similarity Search**: Tận dụng `pgvector` để tìm các "lỗi tương tự trong quá khứ" và gợi ý cách xử lý.

## 5. 🔔 Thông báo & Hành động (Alerting & Remediation)
Không chỉ báo lỗi mà còn sửa lỗi.
- [ ] **Task 5.1**: **Multi-channel**: Hỗ trợ Telegram, Slack, Microsoft Teams, và Webhook.
- [ ] **Task 5.2**: **Auto-Remediation**: Tự động chạy script sửa lỗi (ví dụ: restart service) khi AI xác nhận lỗi 100%.
