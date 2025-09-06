# agent/email_agent.py
import os
import json
import time
import logging
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import imaplib
import email
from email.mime.text import MIMEText
import glob
from pathlib import Path

from config import Config
from utils import (
    extract_features, 
    redact_pii, 
    extract_urls, 
    count_suspicious_keywords,
    check_blacklist,
    setup_logging
)
from model_infer import MLInference

# Import LLM client only if needed
try:
    import sys
    sys.path.append('../llm')
    from client import LLMClient
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

@dataclass
class EmailEvent:
    timestamp: str
    sender: str
    sender_hash: str
    recipients: List[str]
    subject: str
    body_excerpt: str
    urls: List[str]
    suspicious_keywords: int
    url_in_blacklist: bool
    ml_prediction: str
    ml_score: float
    ml_model: str = "tfidf_linear_svc"
    llm_label: Optional[str] = None
    llm_confidence: Optional[float] = None
    llm_explanation: Optional[str] = None
    llm_model: Optional[str] = None
    llm_latency_ms: Optional[int] = None
    llm_tokens_used: Optional[int] = None
    llm_error: Optional[str] = None
    sender_ip: Optional[str] = None
    headers: Optional[Dict] = None
    features: Optional[Dict] = None

class EmailAgent:
    def __init__(self, config: Config):
        self.config = config
        self.logger = setup_logging(config.log_level)
        # Initialize ML inference only if needed (we're going Gemini-only)
        self.ml_inference = None
        
        # Initialize Gemini client for LLM processing
        self.llm_client = None
        if config.mode == 'llm' and LLM_AVAILABLE:
            try:
                from client import GeminiClient
                self.llm_client = GeminiClient(
                    api_key=config.gemini_api_key,
                    model=config.gemini_model,
                    rate_limit=config.gemini_rate_limit,
                    cache_enabled=config.llm_cache_enabled
                )
                self.logger.info(f"Gemini client initialized with model: {config.gemini_model}")
            except Exception as e:
                self.logger.error(f"Failed to initialize Gemini client: {e}")
                if config.mode == 'llm':
                    raise
        elif config.mode == 'llm' and not LLM_AVAILABLE:
            self.logger.warning("LLM mode requested but LLM client not available")
            raise ImportError("LLM mode requires Gemini client")

    def connect_imap(self) -> imaplib.IMAP4_SSL:
        """Connect to IMAP server"""
        try:
            mail = imaplib.IMAP4_SSL(self.config.imap_host)
            mail.login(self.config.imap_user, self.config.imap_pass)
            mail.select('inbox')
            self.logger.info(f"Connected to IMAP server: {self.config.imap_host}")
            return mail
        except Exception as e:
            self.logger.error(f"IMAP connection failed: {e}")
            raise

    def fetch_unseen_emails(self, mail: imaplib.IMAP4_SSL) -> List[Dict]:
        """Fetch unseen emails from IMAP"""
        emails = []
        try:
            status, messages = mail.search(None, 'UNSEEN')
            if status == 'OK':
                for msg_id in messages[0].split():
                    status, msg_data = mail.fetch(msg_id, '(RFC822)')
                    if status == 'OK':
                        email_body = msg_data[0][1]
                        email_message = email.message_from_bytes(email_body)
                        emails.append(self._parse_email(email_message))
                        # Mark as seen
                        mail.store(msg_id, '+FLAGS', '\\Seen')
            
            self.logger.info(f"Fetched {len(emails)} unseen emails")
            return emails
            
        except Exception as e:
            self.logger.error(f"Error fetching emails: {e}")
            return []

    def load_sample_emails(self) -> List[Dict]:
        """Load sample emails from local files"""
        emails = []
        samples_dir = Path(self.config.samples_path)
        
        for file_path in samples_dir.glob("*.eml"):
            try:
                with open(file_path, 'rb') as f:
                    email_message = email.message_from_bytes(f.read())
                    emails.append(self._parse_email(email_message))
            except Exception as e:
                self.logger.error(f"Error reading {file_path}: {e}")
        
        for file_path in samples_dir.glob("*.txt"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Simple text file parsing
                    lines = content.split('\n')
                    subject = lines[0] if lines else "No Subject"
                    body = '\n'.join(lines[1:]) if len(lines) > 1 else ""
                    
                    fake_email = {
                        'from': 'unknown@example.com',
                        'to': ['recipient@example.com'],
                        'subject': subject,
                        'body': body,
                        'headers': {}
                    }
                    emails.append(fake_email)
            except Exception as e:
                self.logger.error(f"Error reading {file_path}: {e}")
        
        self.logger.info(f"Loaded {len(emails)} sample emails")
        return emails

    def _parse_email(self, email_message) -> Dict:
        """Parse email message into structured format"""
        # Extract basic headers
        sender = email_message.get('From', '')
        recipients = email_message.get('To', '').split(',')
        subject = email_message.get('Subject', '')
        
        # Extract body
        body = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    break
        else:
            body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')

        # Extract additional headers
        headers = {
            'message_id': email_message.get('Message-ID', ''),
            'reply_to': email_message.get('Reply-To', ''),
            'x_originating_ip': email_message.get('X-Originating-IP', ''),
            'received': email_message.get('Received', '')
        }

        return {
            'from': sender.strip(),
            'to': [r.strip() for r in recipients],
            'subject': subject.strip(),
            'body': body,
            'headers': headers
        }

    def process_email(self, email_data: Dict) -> EmailEvent:
        """Process a single email and return event data"""
        start_time = time.time()
        
        # Extract and redact features
        sender = email_data['from']
        subject = email_data['subject']
        body = email_data['body']
        
        # Redact PII
        redacted_sender = redact_pii(sender)
        redacted_body = redact_pii(body)
        
        # Create sender hash
        sender_hash = hashlib.sha256(sender.encode()).hexdigest()[:16]
        
        # Extract features
        features = extract_features(subject, body)
        urls = extract_urls(body)
        suspicious_keywords = count_suspicious_keywords(subject + " " + body)
        url_in_blacklist = check_blacklist(urls)
        
        # Truncate body for excerpt
        body_excerpt = redacted_body[:2000] if len(redacted_body) > 2000 else redacted_body
        
        # No ML inference for Gemini-only mode
        ml_prediction = None
        ml_score = None
        
        # Initialize LLM fields
        llm_label = None
        llm_confidence = None
        llm_explanation = None
        llm_model = None
        llm_latency_ms = None
        llm_tokens_used = None
        llm_error = None
        
        # Gemini LLM inference (main classification method)
        if self.llm_client and self.config.mode == 'llm':
            try:
                llm_start = time.time()
                llm_result = self.llm_client.classify_email(
                    sender=redacted_sender,
                    subject=subject,
                    body=body_excerpt
                )
                llm_latency_ms = int((time.time() - llm_start) * 1000)
                
                if llm_result:
                    llm_label = llm_result.label
                    llm_confidence = llm_result.confidence
                    llm_explanation = llm_result.explanation
                    llm_model = llm_result.model
                    llm_tokens_used = llm_result.tokens_used
                    
            except Exception as e:
                llm_error = str(e)
                self.logger.error(f"Gemini inference failed: {e}")
                # Set defaults for failed LLM calls
                llm_label = "unavailable"
                llm_confidence = 0.0
                llm_explanation = f"Error: {str(e)[:100]}"

        # Create event
        event = EmailEvent(
            timestamp=datetime.utcnow().isoformat() + 'Z',
            sender=redacted_sender,
            sender_hash=sender_hash,
            recipients=[redact_pii(r) for r in email_data['to']],
            subject=subject,
            body_excerpt=body_excerpt,
            urls=urls,
            suspicious_keywords=suspicious_keywords,
            url_in_blacklist=url_in_blacklist,
            ml_prediction=ml_prediction,
            ml_score=ml_score,
            ml_model="tfidf_linear_svc",
            llm_label=llm_label,
            llm_confidence=llm_confidence,
            llm_explanation=llm_explanation,
            llm_model=llm_model,
            llm_latency_ms=llm_latency_ms,
            llm_tokens_used=llm_tokens_used,
            llm_error=llm_error,
            headers=email_data.get('headers'),
            features=features
        )
        
        processing_time = time.time() - start_time
        self.logger.debug(f"Processed email in {processing_time:.2f}s")
        
        return event

    def write_event_to_log(self, event: EmailEvent):
        """Write event to JSON log file"""
        try:
            log_path = Path(self.config.log_file_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(log_path, 'a', encoding='utf-8') as f:
                json.dump(asdict(event), f, ensure_ascii=False)
                f.write('\n')
                
        except Exception as e:
            self.logger.error(f"Failed to write event to log: {e}")

    def run_local_mode(self):
        """Run in local mode processing sample files"""
        self.logger.info("Running in local mode")
        emails = self.load_sample_emails()
        
        for email_data in emails:
            try:
                event = self.process_email(email_data)
                self.write_event_to_log(event)
                
                self.logger.info(
                    f"Processed: {event.subject[:50]}... "
                    f"ML: {event.ml_prediction}({event.ml_score:.3f}) "
                    f"LLM: {event.llm_label}({event.llm_confidence or 0:.3f})"
                )
                
            except Exception as e:
                self.logger.error(f"Error processing email: {e}")
        
        self.logger.info(f"Processed {len(emails)} emails")

    def run_imap_mode(self):
        """Run in IMAP mode with polling"""
        self.logger.info("Running in IMAP mode")
        
        while True:
            try:
                mail = self.connect_imap()
                emails = self.fetch_unseen_emails(mail)
                mail.close()
                mail.logout()
                
                for email_data in emails:
                    try:
                        event = self.process_email(email_data)
                        self.write_event_to_log(event)
                        
                        self.logger.info(
                            f"Processed: {event.subject[:50]}... "
                            f"ML: {event.ml_prediction}({event.ml_score:.3f}) "
                            f"LLM: {event.llm_label}({event.llm_confidence or 0:.3f})"
                        )
                        
                    except Exception as e:
                        self.logger.error(f"Error processing email: {e}")
                
                if emails:
                    self.logger.info(f"Processed {len(emails)} new emails")
                
                # Wait before next poll
                time.sleep(self.config.agent_poll_interval)
                
            except KeyboardInterrupt:
                self.logger.info("Stopping agent...")
                break
            except Exception as e:
                self.logger.error(f"IMAP polling error: {e}")
                time.sleep(30)  # Wait before retry

    def run(self):
        """Main run method"""
        self.logger.info(f"Starting email agent in {self.config.mode} mode")
        
        if self.config.imap_host and self.config.imap_user and self.config.imap_pass:
            self.run_imap_mode()
        else:
            self.run_local_mode()

def main():
    config = Config()
    agent = EmailAgent(config)
    agent.run()

if __name__ == "__main__":
    main()
