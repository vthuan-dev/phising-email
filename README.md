### Phishing Detection Pipeline — ELK + Agent + Telegram Alerts

## 1) Giới thiệu
- Hệ thống phát hiện email lừa đảo end‑to‑end: thu thập log, phân tích (ML/LLM), lưu vào Elasticsearch, hiển thị trên Kibana, và cảnh báo Telegram qua ElastAlert2.

Sơ đồ luồng dữ liệu:
```
Email Agent → JSON log → Filebeat → Logstash → Elasticsearch → Kibana
                                                └→ ElastAlert2 → Telegram
```

## 2) Thành phần chính
- `agent/`: Tác tử xử lý email (LLM/ML), ghi sự kiện JSON vào `/var/log/email_events.log`.
- `api/`: API phục vụ chấm điểm (tùy chọn).
- `llm/`: Demo giao diện Gradio (tùy chọn).
- `ml/`: Train/infer mô hình truyền thống (tùy chọn).
- `config/filebeat/filebeat.yml`: Thu thập log JSON.
- `config/logstash/pipeline.conf`: Parse/enrich và index vào `phish-mail-*`.
- `config/elastalert/`: Cấu hình ElastAlert2 + rule Telegram.
- `config/kibana/saved_objects.ndjson`: Dashboard/Discover mẫu.

## 3) Yêu cầu
- Docker, Docker Compose.
- Internet (kéo image, gọi Telegram).
- Telegram bot token và `chat_id` để nhận cảnh báo.

## 4) Chuẩn bị `.env`
Tạo file `.env` ở thư mục gốc:
```bash
# LLM (tùy chọn nếu chạy agent/api/llm)
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-1.5-flash

# Telegram (khuyên dùng để gửi cảnh báo)
TELEGRAM_BOT_TOKEN=123456789:your_bot_token
TELEGRAM_CHAT_ID=-100xxxxxxxxxx

# Tuỳ chọn khác
MODE=llm
LOG_LEVEL=INFO
```
Mở chat với bot và gửi "/start" trước khi test.

## 5) Khởi chạy
```bash
docker compose up -d
docker compose ps
```
Truy cập:
- Kibana: http://localhost:5601
- Elasticsearch: http://localhost:9200
- API (nếu bật): http://localhost:8000

Theo dõi log nhanh:
```bash
docker compose logs -f --tail 100 filebeat
docker compose logs -f --tail 100 logstash
docker compose logs -f --tail 100 elastalert
```

## 6) Import dashboard Kibana
Kibana → Stack Management → Saved Objects → Import → chọn `config/kibana/saved_objects.ndjson`.

## 7) Tạo dữ liệu mẫu
Sinh 100 sự kiện email để pipeline hoạt động:
```bash
docker compose exec agent python /app/generate_sample_logs.py --num-events 50 --output /var/log/email_events.log
```
Hoặc tạo 1 sự kiện phishing ngay lập tức (tránh gộp bằng subject mới):
```bash
docker compose exec agent python - <<'PY'
import json, datetime
e = {
  "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
  "sender": "security@fake-bank.com",
  "subject": "URGENT Verify " + datetime.datetime.utcnow().strftime("%H%M%S"),
  "body_excerpt": "Your account will be suspended. Click the link.",
  "urls": ["http://phishing-example.com/verify"],
  "suspicious_keywords": 3,
  "url_in_blacklist": True,
  "ml_prediction": "phishing",
  "ml_score": 0.93,
  "llm_label": "phishing",
  "llm_confidence": 0.92,
  "llm_explanation": "High urgency + suspicious URL"
}
open("/var/log/email_events.log","a",encoding="utf-8").write(json.dumps(e, ensure_ascii=False)+"\n")
print("Wrote one event.")
PY
```

Trong vòng 10–60s dữ liệu sẽ vào index `phish-mail-*`, dashboard hiển thị và ElastAlert sẽ gửi Telegram nếu thỏa điều kiện.

## 8) Quy tắc cảnh báo (ElastAlert)
- Rule: `config/elastalert/rules/phish_rule.yaml` và `phish_telegram_rule.yaml`.
- Index pattern: `phish-mail-*`.
- Điều kiện (tóm tắt):
  - `ml_score >= 0.85` hoặc `llm_confidence >= 0.85`,
  - hoặc `suspicious_keywords >= 2` kèm điểm trung bình,
  - hoặc `url_in_blacklist: true`.
- Giới hạn spam: `realert: minutes: 30` và nhóm theo `query_key`/`aggregation_key`.
Sau khi chỉnh rule, chạy:
```bash
docker compose restart elastalert
```

## 9) Troubleshooting nhanh
- Không thấy alert, log báo "0 hits": kiểm tra dữ liệu vào `phish-mail-*` trên Discover.
- Có hits nhưng log "Ignoring match for silenced rule": xoá silence cho rule rồi khởi động lại:
```bash
docker compose exec elasticsearch \
  curl -s -X POST elasticsearch:9200/elastalert_status/_delete_by_query \
  -H "Content-Type: application/json" \
  -d "{\"query\":{\"term\":{\"rule_name.keyword\":\"Phishing Email Detection - Telegram Alert\"}}}" | cat
docker compose restart elastalert
```
- Lỗi 404 `botYOUR_TELEGRAM_BOT_TOKEN`: chưa đặt biến `.env` hoặc rule dùng placeholder; cập nhật token/chat id (dưới dạng chuỗi) và restart.

## 10) Bảo mật & triển khai
- Không commit token thật; dùng `.env`/secret manager.
- Cân nhắc bật security cho Elasticsearch/Kibana khi lên production.
- Hạn chế quyền bot Telegram và chỉ thêm vào group cần thiết.

## 11) Lệnh hữu ích
```bash
docker compose down            # dừng
docker compose down -v         # dừng + xoá dữ liệu
docker compose build agent api gradio_demo  # rebuild app
```

## 12) License
MIT — xem `LICENSE` nếu có.

## 13) Thay đổi cấu hình API Gemini

### Cách 1: Thay đổi qua file .env (Khuyến nghị)
1. Mở file `.env` ở thư mục gốc project
2. Sửa các dòng sau:
   ```bash
   # Google Gemini API
   GEMINI_API_KEY=your_new_gemini_api_key_here
   GEMINI_MODEL=gemini-1.5-flash  # hoặc gemini-1.5-pro
   ```
3. Khởi động lại container agent:
   ```bash
   docker compose restart agent
   ```

### Cách 2: Thay đổi trực tiếp trong code
1. Mở file `agent/config.py`
2. Sửa các biến:
   ```python
   GEMINI_API_KEY = "your_new_api_key"
   GEMINI_MODEL = "gemini-1.5-flash"
   ```
3. Rebuild và restart:
   ```bash
   docker compose build agent
   docker compose up -d agent
   ```

### Lấy API Key Gemini
1. Truy cập: https://makersuite.google.com/app/apikey
2. Đăng nhập bằng Google account
3. Tạo API key mới
4. Copy key và paste vào `.env`

### Kiểm tra API hoạt động
```bash
# Test API key
docker compose exec agent python -c "
from client import GeminiClient
client = GeminiClient()
print('API Key valid:', client.test_connection())
"
```

## 14) Thay đổi cấu hình Target Mail

### Cách 1: Thay đổi qua file .env (Khuyến nghị)
1. Mở file `.env` ở thư mục gốc project
2. Sửa các dòng sau:
   ```bash
   # IMAP Email Configuration
   IMAP_HOST=imap.gmail.com
   IMAP_USER=your_email@gmail.com
   IMAP_PASS=your_app_password
   IMAP_PORT=993
   IMAP_SSL=true
   
   # Email Processing Settings
   EMAIL_CHECK_INTERVAL=60  # seconds
   MAX_EMAILS_PER_BATCH=10
   ```
3. Khởi động lại container agent:
   ```bash
   docker compose restart agent
   ```

### Cách 2: Thay đổi trực tiếp trong code
1. Mở file `agent/config.py`
2. Sửa các biến:
   ```python
   IMAP_HOST = "imap.gmail.com"
   IMAP_USER = "your_email@gmail.com"
   IMAP_PASS = "your_app_password"
   IMAP_PORT = 993
   IMAP_SSL = True
   ```
3. Rebuild và restart:
   ```bash
   docker compose build agent
   docker compose up -d agent
   ```

### Cấu hình Gmail App Password
1. Truy cập: https://myaccount.google.com/security
2. Bật **2-Step Verification**
3. Tạo **App Password** cho ứng dụng
4. Copy password và paste vào `.env` (IMAP_PASS)

### Cấu hình Outlook/Hotmail
```bash
IMAP_HOST=outlook.office365.com
IMAP_PORT=993
IMAP_SSL=true
```

### Cấu hình Yahoo Mail
```bash
IMAP_HOST=imap.mail.yahoo.com
IMAP_PORT=993
IMAP_SSL=true
```

### Kiểm tra kết nối IMAP
```bash
# Test IMAP connection
docker compose exec agent python -c "
from email_agent import EmailAgent
agent = EmailAgent()
print('IMAP Connection:', agent.test_imap_connection())
"
```

## 15) Thay đổi cấu hình Telegram & Email

- Thay đổi Telegram (khuyến nghị chỉ cấu hình tại `phish_telegram_rule.yaml`):
  1. Mở `config/elastalert/rules/phish_telegram_rule.yaml`.
  2. Sửa hai dòng:
     - `telegram_bot_token: "<TOKEN_MOI>"`
     - `telegram_room_id: "<CHAT_ID_MOI>"`  (luôn để dạng chuỗi, kể cả số âm `-100...`).
  3. Khởi động lại ElastAlert để áp dụng:
     ```bash
     docker compose restart elastalert
     ```

Gợi ý: Không commit token/password thật vào repo. Lưu trong `.env` hoặc
secret manager và cập nhật thủ công khi deploy.

## 16) Hướng dẫn chạy trên Ubuntu

1) Cài Docker & Compose plugin (Ubuntu 22.04+):
```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

2) Cho phép chạy Docker không cần sudo (đăng xuất/đăng nhập lại sau khi chạy):
```bash
sudo usermod -aG docker $USER
newgrp docker
```

3) Clone repo và tạo `.env`:
```bash
git clone <your-repo-url> attt
cd attt
cp .env.example .env  # nếu không có thì tạo .env theo README
vi .env   # đặt TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY (nếu dùng)
```

4) Chạy dịch vụ:
```bash
docker compose up -d
docker compose ps
```

5) Kiểm tra nhanh và tạo dữ liệu mẫu:
```bash
docker compose logs -f --tail 100 elasticsearch logstash filebeat elastalert | cat
docker compose exec agent python /app/generate_sample_logs.py --num-events 50 --output /var/log/email_events.log
```

6) Truy cập:
- Kibana: http://<IP_UBUNTU>:5601
- Elasticsearch: http://<IP_UBUNTU>:9200

7) Sự cố phổ biến trên Ubuntu:
- "permission denied" khi Filebeat đọc `/var/log`: đã mount `log_data` volume sẵn, không cần sudo; nếu sửa mount, đảm bảo quyền đọc/ghi cho user trong container.
- RAM thiếu cho Elasticsearch: tăng tài nguyên host hoặc chỉnh `ES_JAVA_OPTS` trong `docker-compose.yml` (ví dụ `-Xms512m -Xmx512m`).
- Telegram không nhận: xác nhận đã `/start` với bot, `CHAT_ID` là chuỗi (kể cả số âm), restart ElastAlert: `docker compose restart elastalert`.
# Phishing Email Detection Pipeline with Google Gemini

## Overview

A comprehensive end-to-end phishing email detection system powered by Google Gemini AI, integrated into an ELK stack for real-time monitoring, visualization, and alerting.

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────┐
│   Email Agent   │───▶│   JSON Logs  │───▶│  Filebeat   │
│  (Gemini AI)    │    │  (Rotating)  │    │             │
└─────────────────┘    └──────────────┘    └─────────────┘
                                                 │
                                                 ▼
┌─────────────────┐    ┌──────────────┐    ┌─────────────┐
│    Kibana       │◀───│Elasticsearch │◀───│  Logstash   │
│  (Dashboard +   │    │  (Storage +  │    │ (Processing)│
│   Alerting)     │    │   Indexing)  │    │             │
└─────────────────┘    └──────────────┘    └─────────────┘
                              │
                              ▼
                       ┌─────────────┐
                       │ ElastAlert  │
                       │ (Email/Slack│
                       │  Alerts)    │
                       └─────────────┘
```

## Features

- **Google Gemini AI**: Advanced phishing detection using Gemini 1.5 Flash model
- **Vietnamese Language Support**: Specialized prompts and explanations in Vietnamese
- **Multiple Input Modes**: Local files (.eml/.txt) or live IMAP email fetching
- **PII Protection**: Automatic redaction of emails, phones, and sensitive data
- **Real-time Processing**: Filebeat → Logstash → Elasticsearch pipeline
- **Rich Visualization**: Kibana dashboards with Gemini AI insights
- **Smart Alerting**: ElastAlert rules based on Gemini confidence and heuristics
- **Containerized**: Full Docker Compose setup with health checks

## Quick Start

### Option 1: Automated Setup (Recommended)

**Windows (PowerShell):**
```powershell
# Run the setup script
.\setup_gemini.ps1
```

**Linux/macOS:**
```bash
# Make script executable and run
chmod +x setup_gemini.sh
./setup_gemini.sh
```

### Option 2: Manual Setup

1. **Clone and setup environment**:
   ```bash
   git clone <repository>
   cd phishing-detection
   cp .env.example .env
   # Edit .env with your Gemini API key
   ```

2. **Start services**:
   ```bash
   docker-compose up -d
   ```

3. **Access interfaces**:
   - Kibana: http://localhost:5601
   - API: http://localhost:8000
   - Elasticsearch: http://localhost:9200

4. **Optional - Start Gradio demo**:
   ```bash
   docker-compose --profile dev up -d gradio_demo
   # Access at: http://localhost:7860
   ```

## Configuration

### Email Processing Mode

- **`llm`**: Gemini AI only (recommended, high accuracy)

### Environment Variables

Key settings in `.env`:

```bash
# Processing mode (LLM only)
MODE=llm

# Google Gemini API
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-1.5-flash

# IMAP (for live email monitoring)
IMAP_HOST=imap.gmail.com
IMAP_USER=your_email@gmail.com
IMAP_PASS=your_app_password

# Rate Limiting
GEMINI_RATE_LIMIT=60

# Alerting
ALERT_EMAIL=security@company.com
SLACK_WEBHOOK=https://hooks.slack.com/...
```

## Using the System

### API Endpoints

**Score a single email:**
```bash
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "noreply@bank.com",
    "subject": "Urgent: Account Verification Required",
    "body": "Click here to verify your account immediately..."
  }'
```

**Response:**
```json
{
  "llm_label": "phishing",
  "llm_confidence": 0.95,
  "llm_explanation": "Email có dấu hiệu lừa đảo: yêu cầu cấp bách, đường link đáng ngờ",
  "risk_level": "high",
  "processing_time_ms": 1200
}
```

## LLM Integration

### Cost and Latency Notes

- **GPT-4o-mini**: ~$0.0015 per 1K tokens, ~500ms latency
- **GPT-4o**: ~$0.03 per 1K tokens, ~800ms latency
- **Caching**: SHA256-based to avoid duplicate calls
- **Rate limiting**: Configurable (default: 10 req/min)

### Privacy Features

- Email addresses → `[EMAIL_REDACTED]`
- Phone numbers → `[PHONE_REDACTED]`
- Body truncation to 2000 chars
- Sender hashing for analytics

## Alerting Rules

Triggers on:
- ML score ≥ 0.85 OR
- LLM confidence ≥ 0.85 OR
- (ML score ≥ 0.6 OR LLM confidence ≥ 0.6) AND suspicious keywords ≥ 2 OR
- URL in blacklist

## API Endpoints

- `GET /health` - Service health check
- `POST /score` - Score email content
- `GET /metrics` - Processing metrics

## Development

### Run Tests
```bash
make test
```

### Gradio Demo (LLM testing)
```bash
make gradio
# Visit http://localhost:7860
```

### View Logs
```bash
make logs
# Or specific service
make logs-agent
```

## Troubleshooting

See `docs/runbook.md` for detailed troubleshooting guide covering:
- Docker memory issues
- Elasticsearch bootstrap checks
- Logstash pipeline errors
- Filebeat permissions
- ElastAlert authentication

## Security

See `SECURITY.md` for security considerations including:
- PII redaction strategies
- Secret management
- LLM data minimization
- Network security

## Architecture

### Data Flow

1. **Email Collection**: Agent reads emails via IMAP or local files
2. **Feature Extraction**: Headers, URLs, keywords, body excerpts
3. **ML Classification**: TF-IDF vectorization → Linear SVC → calibrated score
4. **LLM Augmentation**: Optional OpenAI API call for secondary opinion
5. **JSON Logging**: Structured events to rotating log files
6. **ELK Pipeline**: Filebeat → Logstash → Elasticsearch
7. **Visualization**: Kibana dashboards and saved searches
8. **Alerting**: ElastAlert monitoring with email/Slack notifications

### Performance

- **Classical ML**: <10ms inference time
- **LLM calls**: 500-800ms with caching and rate limiting
- **Throughput**: 100+ emails/minute in classical mode
- **Storage**: ~1KB per email event in Elasticsearch

## License

MIT License - see LICENSE file for details.
