# 🚀 Hướng dẫn bắt đầu - Hệ thống phát hiện Email Phishing

## 📋 Tổng quan

Hệ thống này giúp bạn tự động phát hiện email lừa đảo (phishing) và gửi cảnh báo qua Telegram. Hệ thống sử dụng AI Google Gemini để phân tích email và ELK Stack để lưu trữ, hiển thị dữ liệu.

## 🎯 Luồng hoạt động

```
Email → Agent (AI phân tích) → Elasticsearch → Kibana (Dashboard)
                                    ↓
                              ElastAlert → Telegram (Cảnh báo)
```

## ⚡ Cài đặt nhanh (5 phút)

### Bước 1: Chuẩn bị môi trường

**Windows:**
```powershell
# Cài Docker Desktop từ: https://www.docker.com/products/docker-desktop/
# Sau khi cài xong, mở PowerShell và chạy:
docker --version
docker compose version
```

**Ubuntu/Linux:**
```bash
# Cài Docker
sudo apt update
sudo apt install docker.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

### Bước 2: Tạo API Keys

1. **Google Gemini API:**
   - Truy cập: https://makersuite.google.com/app/apikey
   - Đăng nhập Google account
   - Tạo API key mới
   - Copy key (dạng: `AIzaSy...`)

2. **Telegram Bot:**
   - Mở Telegram, tìm `@BotFather`
   - Gửi `/newbot`
   - Đặt tên bot (ví dụ: "Phishing Alert Bot")
   - Copy token (dạng: `123456789:ABC...`)
   - Tạo group mới, thêm bot vào group
   - Gửi `/start` trong group
   - Lấy chat_id từ: https://api.telegram.org/bot<TOKEN>/getUpdates

### Bước 3: Cấu hình hệ thống

1. **Tạo file `.env`:**
```bash
# Tạo file .env trong thư mục gốc
cat > .env << 'EOF'
# Chế độ xử lý
MODE=llm

# Google Gemini API
GEMINI_API_KEY=AIzaSy...your_gemini_key_here
GEMINI_MODEL=gemini-1.5-flash

# Email IMAP (Gmail)
IMAP_HOST=imap.gmail.com
IMAP_USER=your_email@gmail.com
IMAP_PASS=your_app_password

# Telegram Bot
TELEGRAM_BOT_TOKEN=123456789:ABC...your_bot_token
TELEGRAM_CHAT_ID=-1001234567890

# Cài đặt khác
LOG_LEVEL=INFO
AGENT_POLL_INTERVAL=60
EOF
```

2. **Cấu hình Gmail App Password:**
   - Vào: https://myaccount.google.com/security
   - Bật "2-Step Verification"
   - Tạo "App Password" cho ứng dụng
   - Copy password vào `IMAP_PASS` trong `.env`

### Bước 4: Khởi động hệ thống

```bash
# Khởi động tất cả dịch vụ
docker compose up -d

# Kiểm tra trạng thái
docker compose ps

# Xem log để đảm bảo hoạt động
docker compose logs -f --tail=20
```

### Bước 5: Truy cập giao diện

- **Kibana Dashboard:** http://localhost:5601
- **Elasticsearch:** http://localhost:9200

## 🧪 Test hệ thống

### Test 1: Tạo email phishing giả

```bash
# Tạo email phishing test
docker compose exec agent python -c "
import json, datetime
test_email = {
    'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
    'sender': 'security@fake-bank.com',
    'subject': 'URGENT: Verify Account ' + datetime.datetime.utcnow().strftime('%H%M%S'),
    'body_excerpt': 'Your account will be suspended. Click: http://phishing-example.com/verify',
    'urls': ['http://phishing-example.com/verify'],
    'suspicious_keywords': 3,
    'url_in_blacklist': True,
    'llm_label': 'phishing',
    'llm_confidence': 0.95,
    'llm_explanation': 'Email có dấu hiệu lừa đảo rõ ràng'
}
with open('/var/log/email_events.log', 'a', encoding='utf-8') as f:
    f.write(json.dumps(test_email, ensure_ascii=False) + '\n')
print('✅ Đã tạo email phishing test!')
"
```

### Test 2: Kiểm tra cảnh báo Telegram

Trong vòng 1-2 phút, bạn sẽ nhận được thông báo trên Telegram với nội dung:

```
⚠️ CẢNH BÁO EMAIL LỪA ĐẢO! ⚠️

PHÁT HIỆN EMAIL LỪA ĐẢO
THÔNG TIN EMAIL:
• Thời gian: 2025-01-13T10:30:00Z
• Người gửi: security@fake-bank.com
• Tiêu đề: URGENT: Verify Account 103000

PHÂN TÍCH RỦI RO:
• Độ tin cậy AI: 95%
• Phân loại: phishing
• Từ khóa đáng ngờ: 3
• URL trong danh sách đen: True

GIẢI THÍCH CỦA AI:
Email có dấu hiệu lừa đảo rõ ràng

HÀNH ĐỘNG CẦN THIẾT:
Vui lòng kiểm tra email này ngay lập tức trong bảng điều khiển bảo mật.

#CảnhBáoLừaĐảo #BảoMậtEmail
```

## 📊 Sử dụng Kibana Dashboard

1. **Truy cập Kibana:** http://localhost:5601
2. **Import Dashboard:**
   - Vào Stack Management → Saved Objects
   - Import → chọn `config/kibana/saved_objects.ndjson`
3. **Xem dữ liệu:**
   - Vào Dashboard → "Phishing Email Detection Dashboard"
   - Xem thống kê email phishing theo thời gian

## 🔧 Cấu hình nâng cao

### Thay đổi tần suất kiểm tra

```bash
# Sửa file .env
AGENT_POLL_INTERVAL=300  # 5 phút thay vì 1 phút
```

### Thay đổi độ nhạy cảm

Sửa file `config/elastalert/rules/phish_telegram_rule.yaml`:

```yaml
# Giảm độ nhạy (ít cảnh báo hơn)
filter:
- range:
    llm_confidence:
      gte: 0.9  # thay vì 0.85

# Tăng độ nhạy (nhiều cảnh báo hơn)  
filter:
- range:
    llm_confidence:
      gte: 0.7  # thay vì 0.85
```

### Thêm URL đáng ngờ

Sửa file `agent/utils.py`:

```python
BLACKLIST_DOMAINS = [
    'phishing-example.com',
    'fake-bank.org',
    'your-suspicious-domain.com'  # Thêm domain mới
]
```

## 🚨 Xử lý sự cố

### Không nhận được cảnh báo Telegram

1. **Kiểm tra bot token:**
```bash
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"
```

2. **Kiểm tra chat_id:**
```bash
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates"
```

3. **Restart ElastAlert:**
```bash
docker compose restart elastalert
```

### Agent không kết nối được Gmail

1. **Kiểm tra App Password:**
   - Đảm bảo đã bật 2-Step Verification
   - Tạo App Password mới

2. **Kiểm tra log:**
```bash
docker compose logs agent | grep -i "imap\|error"
```

### Không có dữ liệu trong Kibana

1. **Kiểm tra Elasticsearch:**
```bash
curl http://localhost:9200/phish-mail-*/_count
```

2. **Kiểm tra Logstash:**
```bash
docker compose logs logstash | grep -i "error"
```

## 📈 Monitoring

### Xem log real-time

```bash
# Tất cả dịch vụ
docker compose logs -f

# Chỉ agent
docker compose logs -f agent

# Chỉ ElastAlert
docker compose logs -f elastalert
```

### Kiểm tra hiệu suất

```bash
# Số lượng email đã xử lý
docker compose exec elasticsearch curl -s "localhost:9200/phish-mail-*/_count" | jq

# Thống kê theo thời gian
docker compose exec elasticsearch curl -s "localhost:9200/phish-mail-*/_search" -H "Content-Type: application/json" -d '{"aggs":{"by_hour":{"date_histogram":{"field":"@timestamp","interval":"1h"}}}}' | jq
```

## 🎯 Sử dụng thực tế

### Monitor email thật

1. **Cấu hình IMAP cho email công ty**
2. **Đặt agent chạy 24/7**
3. **Nhận cảnh báo real-time qua Telegram**
4. **Xem dashboard để phân tích xu hướng**

### Tích hợp với hệ thống khác

- **Slack:** Thêm webhook vào ElastAlert
- **Email:** Cấu hình SMTP trong ElastAlert
- **Webhook:** Gửi dữ liệu đến hệ thống SIEM

## 📚 Tài liệu tham khảo

- [README.md](../README.md) - Tài liệu chính
- [docs/runbook.md](runbook.md) - Hướng dẫn troubleshooting
- [SECURITY.md](../SECURITY.md) - Bảo mật và quyền riêng tư

## 🆘 Hỗ trợ

Nếu gặp vấn đề:

1. Kiểm tra log: `docker compose logs -f`
2. Xem troubleshooting guide: `docs/runbook.md`
3. Tạo issue trên GitHub với log chi tiết

---

**Chúc bạn sử dụng hệ thống thành công! 🎉**
