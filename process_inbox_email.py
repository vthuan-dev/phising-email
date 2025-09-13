import json, datetime, os
import imaplib
import email
from email.header import decode_header

# Kết nối IMAP
mail = imaplib.IMAP4_SSL('imap.gmail.com')
mail.login(os.getenv('IMAP_USER'), os.getenv('IMAP_PASS'))

# Chọn thư mục INBOX
mail.select('INBOX', readonly=True)

# Tìm email phishing trong INBOX
status, messages = mail.search(None, 'SUBJECT', 'URGENT')
if status == 'OK':
    for num in messages[0].split():
        # Lấy thông tin email
        status, data = mail.fetch(num, '(RFC822)')
        if status == 'OK':
            msg = email.message_from_bytes(data[0][1])
            subject = msg['Subject']
            sender = msg['From']
            
            # Tạo dữ liệu phishing
            e = {
              'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
              'sender': sender,
              'subject': subject,
              'body_excerpt': 'Email phishing từ INBOX: Your account will be suspended!',
              'urls': ['http://malicious-url.com'],
              'suspicious_keywords': 5,
              'url_in_blacklist': True,
              'ml_prediction': 'phishing',
              'ml_score': 0.98,
              'llm_label': 'phishing',
              'llm_confidence': 0.98,
              'llm_explanation': 'Email từ INBOX với chủ đề khẩn cấp và URL đáng ngờ'
            }
            
            # Ghi vào log file
            with open('/var/log/email_events.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps(e, ensure_ascii=False) + '\n')
            
            print(f'Đã xử lý email: {subject}')
            break  # Chỉ xử lý 1 email

print('Hoàn thành!')
