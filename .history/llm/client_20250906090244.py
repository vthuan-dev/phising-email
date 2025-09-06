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

class GeminiClient:
    """Google Gemini API client for email classification"""
    
    def __init__(self, 
                 api_key: str,
                 model: str = "gemini-1.5-flash",
                 rate_limit: int = 60,  # Gemini has higher free tier limits
                 cache_enabled: bool = True):
        
        if not GEMINI_AVAILABLE:
            raise ImportError("google-generativeai package not installed")
        
        self.api_key = api_key
        self.model = model
        self.logger = logging.getLogger(__name__)
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model)
        
        # Rate limiting
        self.rate_limiter = RateLimiter(max_requests=rate_limit, time_window=60)
        
        # Cache
        self.cache = LLMCache() if cache_enabled else None
        
        # Load prompt
        self.system_prompt = self._load_prompt()
        
        # Stats
        self.stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'errors': 0,
            'total_tokens': 0,
            'total_latency_ms': 0
        }
        
        self.logger.info(f"Gemini client initialized with model: {model}")
    
    def _load_prompt(self) -> str:
        """Load system prompt from file"""
        try:
            prompt_file = Path(__file__).parent / "prompt.txt"
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            self.logger.error(f"Failed to load prompt: {e}")
            return self._get_default_prompt()
    
    def _get_default_prompt(self) -> str:
        """Default Vietnamese prompt for Gemini"""
        return """Bạn là một chuyên gia bảo mật email chuyên nghiệp với nhiều năm kinh nghiệm phát hiện email lừa đảo (phishing).

NHIỆM VỤ: Phân tích email được cung cấp và xác định xem đây có phải là email lừa đảo hay không.

CÁC DẤU HIỆU PHISHING CẦN CHÚ Ý:
- Yêu cầu cấp bách hoặc đe dọa (tài khoản bị khóa, hết hạn)
- Yêu cầu xác minh thông tin cá nhân hoặc tài khoản
- Links đáng ngờ hoặc không khớp với tên miền chính thức
- Lỗi chính tả, ngữ pháp
- Người gửi giả mạo tổ chức uy tín
- Yêu cầu chuyển tiền, thanh toán
- Thông báo trúng thưởng, phần thưởng không thực
- Nội dung tạo áp lực tâm lý

QUY TRÌNH PHÂN TÍCH:
1. Kiểm tra người gửi và tên miền
2. Phân tích nội dung và ngôn ngữ
3. Xem xét các yêu cầu và links
4. Đánh giá mức độ khả nghi tổng thể

ĐỊNH DẠNG TRẢ LỜI (chỉ trả lời JSON, không thêm text khác):
{
  "label": "phishing" hoặc "legit",
  "confidence": số từ 0.0 đến 1.0 (0.0 = không chắc chắn, 1.0 = rất chắc chắn),
  "explanation": "Giải thích ngắn gọn lý do phân loại (tối đa 100 từ)"
}"""
    
    def _create_cache_key(self, sender: str, subject: str, body: str) -> str:
        """Create cache key for request"""
        # Normalize inputs for consistent caching
        content = f"{sender.lower()}|{subject.lower()}|{body.lower()[:1000]}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _parse_gemini_response(self, response_text: str) -> Optional[Dict]:
        """Parse Gemini response to extract JSON"""
        try:
            # Try to extract JSON from response
            response_text = response_text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.startswith('```'):
                response_text = response_text[3:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            # Find JSON object
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            
            if start != -1 and end > start:
                json_str = response_text[start:end]
                result = json.loads(json_str)
                
                # Validate required fields
                if 'label' in result and 'confidence' in result and 'explanation' in result:
                    return result
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to parse Gemini response: {e}")
            return None
    
    def classify_email(self, sender: str, subject: str, body: str) -> Optional[LLMResult]:
        """Classify email using Gemini API"""
        start_time = time.time()
        
        try:
            # Create cache key
            cache_key = self._create_cache_key(sender, subject, body)
            
            # Check cache first
            if self.cache:
                cached = self.cache.get(cache_key)
                if cached:
                    self.stats['cache_hits'] += 1
                    self.logger.debug("Cache hit for email classification")
                    
                    return LLMResult(
                        label=cached['label'],
                        confidence=cached['confidence'],
                        explanation=cached['explanation'],
                        model=self.model,
                        latency_ms=int((time.time() - start_time) * 1000)
                    )
            
            self.stats['cache_misses'] += 1
            
            # Rate limiting
            self.rate_limiter.wait_if_needed()
            
            # Prepare prompt
            email_content = f"""
THÔNG TIN EMAIL CẦN PHÂN TÍCH:

Người gửi: {sender}
Tiêu đề: {subject}
Nội dung: {body[:1500]}"""
            
            full_prompt = f"{self.system_prompt}\n\n{email_content}"
            
            # Call Gemini API
            api_start = time.time()
            response = self.client.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,  # Low temperature for consistent results
                    max_output_tokens=500,
                    top_p=0.8,
                    top_k=40
                )
            )
            api_latency = int((time.time() - api_start) * 1000)
            
            # Parse response
            if response and response.text:
                parsed = self._parse_gemini_response(response.text)
                
                if parsed:
                    # Create result
                    result = LLMResult(
                        label=parsed['label'],
                        confidence=float(parsed['confidence']),
                        explanation=parsed['explanation'],
                        model=self.model,
                        tokens_used=None,  # Gemini doesn't provide token count easily
                        latency_ms=api_latency
                    )
                    
                    # Update stats
                    self.stats['total_requests'] += 1
                    self.stats['total_latency_ms'] += api_latency
                    
                    # Cache result
                    if self.cache:
                        cache_data = {
                            'label': result.label,
                            'confidence': result.confidence,
                            'explanation': result.explanation
                        }
                        self.cache.set(cache_key, cache_data)
                    
                    self.logger.debug(f"Gemini classification: {result.label} ({result.confidence:.3f})")
                    return result
                else:
                    self.logger.error("Failed to parse Gemini response JSON")
            else:
                self.logger.error("Empty response from Gemini")
            
            self.stats['errors'] += 1
            return None
            
        except Exception as e:
            self.logger.error(f"Gemini API error: {e}")
            self.stats['errors'] += 1
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        avg_latency = 0
        if self.stats['total_requests'] > 0:
            avg_latency = self.stats['total_latency_ms'] / self.stats['total_requests']
        
        cache_hit_rate = 0
        total_cache_requests = self.stats['cache_hits'] + self.stats['cache_misses']
        if total_cache_requests > 0:
            cache_hit_rate = self.stats['cache_hits'] / total_cache_requests
        
        stats = {
            'model': self.model,
            'total_requests': self.stats['total_requests'],
            'errors': self.stats['errors'],
            'avg_latency_ms': round(avg_latency, 2),
            'cache_hit_rate': round(cache_hit_rate, 3),
            'cache_enabled': self.cache is not None
        }
        
        if self.cache:
            cache_stats = self.cache.get_stats()
            stats.update(cache_stats)
        
        return stats

# Legacy alias for compatibility
LLMClient = GeminiClient
