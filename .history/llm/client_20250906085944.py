# llm/client.py
import os
import time
import json
import hashlib
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path

# Rate limiting
from collections import defaultdict, deque

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from cache import LLMCache

@dataclass
class LLMResult:
    label: str
    confidence: float
    explanation: str
    model: str
    tokens_used: Optional[int] = None
    latency_ms: Optional[int] = None

class RateLimiter:
    """Simple rate limiter for API calls"""
    
    def __init__(self, max_requests: int, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self.logger = logging.getLogger(__name__)
    
    def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        now = time.time()
        
        # Remove old requests outside time window
        while self.requests and self.requests[0] <= now - self.time_window:
            self.requests.popleft()
        
        # Check if we need to wait
        if len(self.requests) >= self.max_requests:
            wait_time = self.time_window - (now - self.requests[0])
            if wait_time > 0:
                self.logger.warning(f"Rate limit reached, waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                return self.wait_if_needed()
        
        # Record this request
        self.requests.append(now)

class LLMClient:
    """OpenAI client for email classification"""
    
    def __init__(
        self, 
        api_key: str,
        model: str = "gpt-4o-mini",
        rate_limit: int = 10,
        cache_enabled: bool = True,
        timeout: int = 30
    ):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        
        # Rate limiting
        self.rate_limiter = RateLimiter(max_requests=rate_limit, time_window=60)
        
        # Caching
        self.cache = LLMCache() if cache_enabled else None
        
        # Load prompt
        self.system_prompt = self._load_prompt()
        
        self.logger.info(f"LLM client initialized with model: {model}")
    
    def _load_prompt(self) -> str:
        """Load system prompt from file"""
        try:
            prompt_path = os.path.join(os.path.dirname(__file__), "prompt.txt")
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            # Fallback prompt
            return """Bạn là một chuyên gia bảo mật email. Phân tích email sau và xác định xem đây có phải là email lừa đảo (phishing) hay không.

Trả lời theo định dạng JSON chính xác:
{
  "label": "phishing" hoặc "legit",
  "confidence": số từ 0.0 đến 1.0,
  "explanation": "Giải thích ngắn gọn bằng tiếng Việt"
}

Chỉ trả lời JSON, không thêm text nào khác."""
    
    def _create_cache_key(self, sender: str, subject: str, body: str) -> str:
        """Create cache key from email content"""
        content = f"{sender}|{subject}|{body[:1000]}"  # Limit body for consistency
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _parse_response(self, response_text: str) -> Optional[Dict]:
        """Parse LLM response and extract structured data"""
        try:
            # Try to extract JSON from response
            response_text = response_text.strip()
            
            # If response doesn't start with {, try to find JSON in the text
            if not response_text.startswith('{'):
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group()
            
            result = json.loads(response_text)
            
            # Validate required fields
            if 'label' not in result or 'confidence' not in result:
                raise ValueError("Missing required fields")
            
            # Validate label
            if result['label'] not in ['phishing', 'legit']:
                raise ValueError(f"Invalid label: {result['label']}")
            
            # Validate confidence
            confidence = float(result['confidence'])
            if not 0.0 <= confidence <= 1.0:
                raise ValueError(f"Invalid confidence: {confidence}")
            
            result['confidence'] = confidence
            return result
            
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error(f"Failed to parse LLM response: {e}")
            self.logger.debug(f"Raw response: {response_text}")
            return None
    
    def classify_email(
        self, 
        sender: str, 
        subject: str, 
        body: str,
        max_retries: int = 3
    ) -> Optional[LLMResult]:
        """
        Classify email as phishing or legitimate
        
        Args:
            sender: Email sender (already redacted)
            subject: Email subject
            body: Email body excerpt (already truncated)
            max_retries: Maximum number of retry attempts
            
        Returns:
            LLMResult or None if classification fails
        """
        # Check cache first
        cache_key = self._create_cache_key(sender, subject, body)
        if self.cache:
            cached_result = self.cache.get(cache_key)
            if cached_result:
                self.logger.debug("Using cached LLM result")
                return LLMResult(**cached_result)
        
        # Rate limiting
        if not self.rate_limiter.can_proceed():
            self.logger.warning("Rate limit exceeded")
            return None
        
        # Prepare user message
        user_message = f"""
Email Information:
From: {sender}
Subject: {subject}
Body: {body[:1500]}
"""
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                
                # Make API call
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.1,
                    max_tokens=200,
                    timeout=self.timeout
                )
                
                # Record request for rate limiting
                self.rate_limiter.record_request()
                
                # Extract response
                response_text = response.choices[0].message.content
                tokens_used = response.usage.total_tokens if response.usage else None
                
                # Parse response
                parsed = self._parse_response(response_text)
                if not parsed:
                    if attempt < max_retries - 1:
                        self.logger.warning(f"Retrying LLM call (attempt {attempt + 1})")
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    else:
                        return None
                
                # Create result
                result = LLMResult(
                    label=parsed['label'],
                    confidence=parsed['confidence'],
                    explanation=parsed.get('explanation', ''),
                    model=self.model,
                    tokens_used=tokens_used
                )
                
                # Cache result
                if self.cache:
                    self.cache.set(cache_key, {
                        'label': result.label,
                        'confidence': result.confidence,
                        'explanation': result.explanation,
                        'model': result.model,
                        'tokens_used': result.tokens_used
                    })
                
                latency = time.time() - start_time
                self.logger.debug(f"LLM call completed in {latency:.2f}s, tokens: {tokens_used}")
                
                return result
                
            except openai.APITimeoutError:
                self.logger.error(f"OpenAI API timeout (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                else:
                    return None
                    
            except openai.RateLimitError:
                self.logger.error("OpenAI rate limit exceeded")
                time.sleep(60)  # Wait 1 minute
                if attempt < max_retries - 1:
                    continue
                else:
                    return None
                    
            except openai.APIConnectionError:
                self.logger.error(f"OpenAI connection error (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                else:
                    return None
                    
            except Exception as e:
                self.logger.error(f"Unexpected error in LLM call: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    return None
        
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        stats = {
            'model': self.model,
            'rate_limit': self.rate_limiter.max_requests,
            'current_requests': len(self.rate_limiter.requests),
        }
        
        if self.cache:
            stats.update(self.cache.get_stats())
        
        return stats
