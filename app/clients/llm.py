import os
import logging


class LLMClient:
    """A small wrapper that returns an explainable text for an anomaly.
    If `OPENAI_API_KEY` is set, this stub can be extended to call OpenAI.
    For now it provides a deterministic explanation based on inputs so the
    project runs without external credentials.
    """

    def __init__(self, api_key_env='OPENAI_API_KEY'):
        self.api_key = os.environ.get(api_key_env)

    def explain_anomaly(self, metric_name: str, result: dict) -> str:
        reason = result.get('reason', 'unknown')
        conf = result.get('confidence', 0.0)
        expl_raw = result.get('explanation', '')

        # Simple parser for the raw explanation string: last=325.040, mean=325.006, std=0.010...
        metrics = {}
        try:
            parts = expl_raw.split(', ')
            for p in parts:
                if '=' in p:
                    # Handle "CRITICAL: Host is DOWN (up=0). last=0" case
                    sub_parts = p.split('. ') if '. ' in p else [p]
                    for sp in sub_parts:
                        if '=' in sp:
                            k, v = sp.split('=')
                            metrics[k.strip().lower()] = v.strip()
        except Exception:
            pass

        last = metrics.get('last', 'N/A')
        mean = metrics.get('mean', 'N/A')
        std = metrics.get('std', 'N/A')

        # Map metric names to human-readable Vietnamese titles
        metric_map = {
            'up': 'Trạng thái Server (Uptime)',
            'node_cpu_seconds_total': 'Sử dụng CPU',
            'node_memory_MemAvailable_bytes': 'Bộ nhớ trống (Available)',
            'node_memory_MemTotal_bytes': 'Tổng dung lượng RAM',
            'node_filesystem_avail_bytes': 'Dung lượng ổ đĩa trống',
            'node_filesystem_size_bytes': 'Tổng dung lượng ổ đĩa',
            'node_network_receive_bytes_total': 'Băng thông Tải về (Download)',
            'node_network_transmit_bytes_total': 'Băng thông Tải lên (Upload)',
        }
        
        friendly_name = "Chỉ số hệ thống"
        for key, val in metric_map.items():
            if key in metric_name:
                friendly_name = val
                break

        # Determine Impact and Action based on metric types
        impact = "Có thể gây chậm hệ thống hoặc gián đoạn dịch vụ."
        action = "Kiểm tra log hệ thống và tình trạng các service đang chạy."

        if 'up' in metric_name:
            friendly_name = "Kết nối Server"
            impact = "Server không phản hồi, toàn bộ dịch vụ trên server này bị sập."
            action = "Kiểm tra nguồn điện, kết nối mạng hoặc restart server vật lý."
        elif 'cpu' in metric_name:
            impact = "Ứng dụng bị chậm, phản hồi lâu, có thể gây treo hệ thống."
            action = "Kiểm tra các tiến trình đang chiếm dụng CPU (lệnh top/htop)."
        elif 'memory' in metric_name:
            impact = "Hệ thống có nguy cơ bị lỗi Out-Of-Memory (OOM) và tự kill app."
            action = "Giải phóng bộ nhớ hoặc kiểm tra rò rỉ bộ nhớ (memory leak)."
        elif 'filesystem' in metric_name:
            friendly_name = "Dung lượng Ổ đĩa"
            impact = "Không thể ghi thêm dữ liệu, Database hoặc Log có thể bị lỗi."
            action = "Xóa các file log cũ hoặc mở rộng thêm dung lượng ổ đĩa."

        if reason == 'host_down':
            title = "❌ SERVER KHÔNG PHẢN HỒI"
            status_text = f"Giá trị hiện tại: {last} (Phải là 1 để hoạt động)"
        else:
            title = f"⚠️ BẤT THƯỜNG: {friendly_name.upper()}"
            status_text = f"Giá trị hiện tại: {last}"

        baseline_text = f"Ngưỡng bình thường: ~{mean} (±{std})"
        
        text = (
            f"<b>{title}</b>\n\n"
            f"📍 <b>Hiện trạng:</b> {status_text}\n"
            f"📉 <b>Ngưỡng lý tưởng:</b> {baseline_text}\n"
            f"🔥 <b>Tác động:</b> {impact}\n"
            f"🛡️ <b>Hành động:</b> {action}\n\n"
            f"<i>-- Phân tích bởi AI (Độ tin cậy: {conf*100:.0f}%) --</i>"
        )
        return text
