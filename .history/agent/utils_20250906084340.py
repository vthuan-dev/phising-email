# agent/utils.py
import re
import logging
import hashlib
from typing import List, Dict, Any
from urllib.parse import urlparse
import logging.handlers

# Suspicious keywords for phishing detection
SUSPICIOUS_KEYWORDS = [
    'urgent', 'immediately', 'verify', 'confirm', 'suspended', 'expired',
    'click here', 'act now', 'limited time', 'verify account', 'update payment',
    'security alert', 'unusual activity', 'locked account', 'winner',
    'congratulations', 'prize', 'free', 'bonus', 'claim', 'lottery',
    'inheritance', 'million', 'bitcoin', 'cryptocurrency', 'investment',
    'prince', 'nigeria', 'transfer', 'beneficiary', 'confidential'
]

# Known malicious domains (simplified blacklist)
BLACKLIST_DOMAINS = [
    'phishing-example.com',
    'malicious-site.net', 
    'fake-bank.org',
    'scam-site.com'
]

def setup_logging(level: str = "INFO") -> logging.Logger:
    """Setup structured logging with rotation"""
    logger = logging.getLogger("email_agent")
    logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            '/var/log/agent.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except (OSError, PermissionError):
        # Fallback if can't write to /var/log
        logger.warning("Could not setup file logging")
    
    return logger

def redact_pii(text: str) -> str:
    """Redact personally identifiable information"""
    if not text:
        return text
    
    # Email addresses
    text = re.sub(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 
        '[EMAIL_REDACTED]', 
        text, 
        flags=re.IGNORECASE
    )
    
    # Phone numbers (various formats)
    phone_patterns = [
        r'\b\d{3}-\d{3}-\d{4}\b',  # 123-456-7890
        r'\b\(\d{3}\)\s*\d{3}-\d{4}\b',  # (123) 456-7890
        r'\b\d{3}\.\d{3}\.\d{4}\b',  # 123.456.7890
        r'\b\+1\s*\d{3}\s*\d{3}\s*\d{4}\b',  # +1 123 456 7890
    ]
    
    for pattern in phone_patterns:
        text = re.sub(pattern, '[PHONE_REDACTED]', text)
    
    # Credit card numbers (simplified)
    text = re.sub(
        r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
        '[CARD_REDACTED]',
        text
    )
    
    # SSN
    text = re.sub(
        r'\b\d{3}-\d{2}-\d{4}\b',
        '[SSN_REDACTED]',
        text
    )
    
    return text

def extract_urls(text: str) -> List[str]:
    """Extract URLs from text"""
    if not text:
        return []
    
    # URL pattern
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_pattern, text, re.IGNORECASE)
    
    # Also look for www. patterns without http
    www_pattern = r'www\.(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    www_urls = re.findall(www_pattern, text, re.IGNORECASE)
    urls.extend(['http://' + url for url in www_urls])
    
    return list(set(urls))  # Remove duplicates

def count_suspicious_keywords(text: str) -> int:
    """Count suspicious keywords in text"""
    if not text:
        return 0
    
    text_lower = text.lower()
    count = 0
    
    for keyword in SUSPICIOUS_KEYWORDS:
        if keyword.lower() in text_lower:
            count += 1
    
    return count

def check_blacklist(urls: List[str]) -> bool:
    """Check if any URL is in blacklist"""
    for url in urls:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            
            if domain in BLACKLIST_DOMAINS:
                return True
        except Exception:
            continue
    
    return False

def extract_features(subject: str, body: str) -> Dict[str, Any]:
    """Extract additional features for analysis"""
    features = {}
    
    # Basic counts
    features['subject_length'] = len(subject) if subject else 0
    features['body_length'] = len(body) if body else 0
    features['char_count'] = len(body) if body else 0
    
    # HTML detection
    features['has_html'] = bool(re.search(r'<[^>]+>', body)) if body else False
    
    # URL count
    features['url_count'] = len(extract_urls(body)) if body else 0
    
    # Punctuation analysis
    if body:
        features['exclamation_count'] = body.count('!')
        features['question_count'] = body.count('?')
        features['caps_ratio'] = sum(1 for c in body if c.isupper()) / len(body) if body else 0
    else:
        features['exclamation_count'] = 0
        features['question_count'] = 0
        features['caps_ratio'] = 0.0
    
    # Attachment indicators (would need proper email parsing)
    features['has_attachments'] = bool(re.search(r'attachment|attached|file|document', body, re.IGNORECASE)) if body else False
    
    return features

def hash_sender(sender: str) -> str:
    """Create a hash of sender for privacy-preserving analytics"""
    return hashlib.sha256(sender.encode()).hexdigest()[:16]

def normalize_text(text: str) -> str:
    """Normalize text for ML processing"""
    if not text:
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove URLs (already extracted separately)
    text = re.sub(r'http[s]?://\S+', '[URL]', text)
    
    return text.strip()

def truncate_text(text: str, max_length: int = 2000) -> str:
    """Truncate text to maximum length for LLM processing"""
    if not text or len(text) <= max_length:
        return text
    
    # Try to truncate at sentence boundary
    truncated = text[:max_length]
    last_period = truncated.rfind('.')
    
    if last_period > max_length * 0.8:  # If we found a period reasonably close to the end
        return truncated[:last_period + 1]
    else:
        return truncated + "..."

def validate_email_data(email_data: Dict) -> bool:
    """Validate email data structure"""
    required_fields = ['from', 'to', 'subject', 'body']
    
    for field in required_fields:
        if field not in email_data:
            return False
    
    # Basic type checks
    if not isinstance(email_data['to'], list):
        return False
    
    if not isinstance(email_data['subject'], str):
        return False
    
    if not isinstance(email_data['body'], str):
        return False
    
    return True
