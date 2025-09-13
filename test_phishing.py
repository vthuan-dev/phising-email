import json
import datetime

# Tạo dữ liệu test phishing
test_event = {
    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    "sender": "test-phishing@fake-bank.com",
    "subject": "URGENT: Account Suspension " + datetime.datetime.utcnow().strftime("%H%M%S"),
    "body_excerpt": "Your account will be suspended. Click here: https://secure-banking.vn-verify.com/login",
    "llm_label": "phishing",
    "llm_confidence": 0.95,
    "llm_explanation": "Contains suspicious URL and urgent language",
    "url_in_blacklist": True,
    "suspicious_keywords": 3,
    "urls": ["https://secure-banking.vn-verify.com/login"]
}

# Ghi vào log file
with open("/var/log/email_events.log", "a", encoding="utf-8") as f:
    f.write(json.dumps(test_event, ensure_ascii=False) + "\n")

print("Created test phishing event!")
