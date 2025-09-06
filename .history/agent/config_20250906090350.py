# agent/config.py
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    # Processing mode
    mode: str = "llm"  # llm only (using Gemini API)
    
    # Paths
    ml_artifacts_path: str = "/app/ml_artifacts"
    log_file_path: str = "/var/log/email_events.log"
    samples_path: str = "/app/samples"
    
    # Google Gemini Configuration
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-flash"
    
    # IMAP Configuration
    imap_host: Optional[str] = None
    imap_user: Optional[str] = None
    imap_pass: Optional[str] = None
    
    # Logging
    log_level: str = "INFO"
    
    # Rate Limiting
    gemini_rate_limit: int = 60  # requests per minute (Gemini has higher limits)
    llm_cache_enabled: bool = True
    
    # Operational Settings
    agent_poll_interval: int = 60  # seconds
    
    def __post_init__(self):
        # Load from environment variables
        self.mode = os.getenv("MODE", self.mode)
        self.ml_artifacts_path = os.getenv("ML_ARTIFACTS_PATH", self.ml_artifacts_path)
        self.log_file_path = os.getenv("LOG_FILE_PATH", self.log_file_path)
        self.samples_path = os.getenv("SAMPLES_PATH", self.samples_path)
        
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.gemini_model = os.getenv("GEMINI_MODEL", self.gemini_model)
        
        self.imap_host = os.getenv("IMAP_HOST")
        self.imap_user = os.getenv("IMAP_USER") 
        self.imap_pass = os.getenv("IMAP_PASS")
        
        self.log_level = os.getenv("LOG_LEVEL", self.log_level)
        
        self.gemini_rate_limit = int(os.getenv("GEMINI_RATE_LIMIT", self.gemini_rate_limit))
        self.llm_cache_enabled = os.getenv("LLM_CACHE_ENABLED", "true").lower() == "true"
        
        self.agent_poll_interval = int(os.getenv("AGENT_POLL_INTERVAL", self.agent_poll_interval))
        
        # Validation
        if self.mode in ['llm', 'hybrid'] and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY required for LLM modes")
        
        if self.mode not in ['classic', 'llm', 'hybrid']:
            raise ValueError(f"Invalid mode: {self.mode}")
            
        if self.openai_model not in ['gpt-4o-mini', 'gpt-4o']:
            raise ValueError(f"Invalid OpenAI model: {self.openai_model}")
