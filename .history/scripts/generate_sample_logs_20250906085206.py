# scripts/generate_sample_logs.py
import json
import random
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_sender_hash(sender):
    """Generate sender hash"""
    return hashlib.sha256(sender.encode()).hexdigest()[:16]

def generate_sample_events(num_events=100):
    """Generate sample email events for testing"""
    
    # Sample data
    phishing_senders = [
        "security@fake-bank.com",
        "noreply@phishing-site.net",
        "admin@scam-domain.org",
        "support@malicious-site.com",
        "prince@nigeria-email.com"
    ]
    
    legit_senders = [
        "noreply@company.com",
        "team@startup.io",
        "support@legitimate-service.com",
        "newsletter@tech-blog.com",
        "hr@corporation.com"
    ]
    
    phishing_subjects = [
        "URGENT: Your account will be suspended",
        "Congratulations! You've won $1,000,000",
        "Security Alert: Unusual Activity Detected",
        "Update your payment information immediately",
        "Inheritance Fund Transfer - Action Required"
    ]
    
    legit_subjects = [
        "Weekly team meeting reminder",
        "Order confirmation #{}",
        "Monthly newsletter - Tech Updates",
        "Project deadline reminder",
        "Welcome to our service"
    ]
    
    phishing_bodies = [
        "Your account has been compromised. Click here to verify: http://phishing-example.com/verify",
        "You are the lucky winner! Send your details to claim your prize immediately.",
        "We detected suspicious activity. Please verify your identity now or account will be locked.",
        "Your payment method has expired. Update immediately: http://scam-site.com/payment",
        "I need your help to transfer inheritance funds. Please send your bank details."
    ]
    
    legit_bodies = [
        "Hi team, reminder about our weekly meeting tomorrow at 2 PM in the conference room.",
        "Thank you for your purchase. Your order has been confirmed and will ship soon.",
        "Here's our monthly newsletter with the latest tech industry updates and insights.",
        "Friendly reminder that the project deadline is approaching next Friday.",
        "Welcome to our platform! Please take time to explore the features available."
    ]
    
    phishing_urls = [
        ["http://phishing-example.com/verify"],
        ["http://scam-site.com/payment", "http://malicious.net/claim"],
        ["http://fake-bank.org/login"],
        [],
        ["http://suspicious-domain.com/transfer"]
    ]
    
    legit_urls = [
        [],
        ["https://company.com/tracking"],
        ["https://newsletter.tech-blog.com"],
        [],
        ["https://platform.startup.io/welcome"]
    ]
    
    events = []
    
    for i in range(num_events):
        # Determine if this should be phishing or legit (70% legit, 30% phishing)
        is_phishing = random.random() < 0.3
        
        if is_phishing:
            sender = random.choice(phishing_senders)
            subject = random.choice(phishing_subjects)
            body = random.choice(phishing_bodies)
            urls = random.choice(phishing_urls)
            ml_prediction = "phishing"
            ml_score = random.uniform(0.7, 0.98)
            llm_label = "phishing" if random.random() < 0.9 else "legit"
            llm_confidence = random.uniform(0.75, 0.95)
            llm_explanation = "Email chứa các dấu hiệu lừa đảo: yêu cầu cấp bách, link đáng ngờ, đe dọa khóa tài khoản"
        else:
            sender = random.choice(legit_senders)
            subject = random.choice(legit_subjects)
            if "{}" in subject:
                subject = subject.format(random.randint(10000, 99999))
            body = random.choice(legit_bodies)
            urls = random.choice(legit_urls)
            ml_prediction = "legit"
            ml_score = random.uniform(0.02, 0.4)
            llm_label = "legit" if random.random() < 0.95 else "phishing"
            llm_confidence = random.uniform(0.8, 0.95)
            llm_explanation = "Email có vẻ hợp lệ: nội dung bình thường, không có dấu hiệu lừa đảo"
        
        # Generate timestamp (last 7 days)
        timestamp = datetime.utcnow() - timedelta(
            days=random.randint(0, 7),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59)
        )
        
        # Create event
        event = {
            "timestamp": timestamp.isoformat() + 'Z',
            "sender": sender,
            "sender_hash": generate_sender_hash(sender),
            "recipients": [f"user{random.randint(1, 100)}@company.com"],
            "subject": subject,
            "body_excerpt": body[:200] + "..." if len(body) > 200 else body,
            "urls": urls,
            "suspicious_keywords": random.randint(0, 5) if is_phishing else random.randint(0, 2),
            "url_in_blacklist": random.random() < 0.2 if is_phishing else False,
            "ml_prediction": ml_prediction,
            "ml_score": round(ml_score, 3),
            "ml_model": "tfidf_linear_svc",
            "llm_label": llm_label if random.random() < 0.8 else None,  # Sometimes LLM fails
            "llm_confidence": round(llm_confidence, 3) if llm_label else None,
            "llm_explanation": llm_explanation if llm_label else None,
            "llm_model": "gpt-4o-mini" if llm_label else None,
            "llm_latency_ms": random.randint(200, 800) if llm_label else None,
            "llm_tokens_used": random.randint(50, 200) if llm_label else None,
            "llm_error": None,
            "sender_ip": f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}",
            "headers": {
                "message_id": f"<{random.randint(100000, 999999)}@{sender.split('@')[1]}>",
                "reply_to": sender,
                "x_originating_ip": f"203.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}"
            },
            "features": {
                "has_attachments": random.random() < 0.1,
                "has_html": random.random() < 0.6,
                "url_count": len(urls),
                "char_count": len(body),
                "exclamation_count": body.count('!')
            }
        }
        
        events.append(event)
    
    return events

def write_events_to_log(events, log_file="/var/log/email_events.log"):
    """Write events to log file"""
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(log_path, 'w', encoding='utf-8') as f:
        for event in events:
            json.dump(event, f, ensure_ascii=False)
            f.write('\n')
    
    logger.info(f"Written {len(events)} events to {log_path}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate sample email events')
    parser.add_argument('--num-events', type=int, default=100,
                       help='Number of events to generate')
    parser.add_argument('--output', default='/var/log/email_events.log',
                       help='Output log file path')
    parser.add_argument('--append', action='store_true',
                       help='Append to existing file instead of overwriting')
    
    args = parser.parse_args()
    
    # Generate events
    logger.info(f"Generating {args.num_events} sample events...")
    events = generate_sample_events(args.num_events)
    
    # Sort by timestamp
    events.sort(key=lambda x: x['timestamp'])
    
    # Write to file
    log_path = Path(args.output)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    mode = 'a' if args.append else 'w'
    with open(log_path, mode, encoding='utf-8') as f:
        for event in events:
            json.dump(event, f, ensure_ascii=False)
            f.write('\n')
    
    action = "Appended" if args.append else "Written"
    logger.info(f"{action} {len(events)} events to {log_path}")
    
    # Show statistics
    phishing_count = sum(1 for e in events if e['ml_prediction'] == 'phishing')
    legit_count = len(events) - phishing_count
    
    logger.info(f"Event statistics:")
    logger.info(f"  Phishing: {phishing_count} ({phishing_count/len(events)*100:.1f}%)")
    logger.info(f"  Legitimate: {legit_count} ({legit_count/len(events)*100:.1f}%)")
    logger.info(f"  Time range: {events[0]['timestamp']} to {events[-1]['timestamp']}")

if __name__ == "__main__":
    main()
