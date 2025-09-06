# api/app.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
import logging
from typing import Optional
from pydantic import BaseModel
import uvicorn
from pathlib import Path

# Add paths for imports
sys.path.append('../ml')
sys.path.append('../llm')

from ml.infer import EmailClassifier

# Initialize FastAPI app
app = FastAPI(
    title="Phishing Detection API",
    description="API for phishing email detection using ML and optional LLM",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize ML classifier
try:
    ml_artifacts_path = os.getenv("ML_ARTIFACTS_PATH", "/app/ml_artifacts")
    classifier = EmailClassifier(ml_artifacts_path)
    logger.info("ML classifier initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize ML classifier: {e}")
    classifier = None

# Initialize Gemini client (main classification method)
llm_client = None
try:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if gemini_api_key:
        from llm.client import GeminiClient
        llm_client = GeminiClient(
            api_key=gemini_api_key,
            model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            rate_limit=60,  # Higher limit for API
            cache_enabled=True
        )
        logger.info("Gemini client initialized successfully")
except Exception as e:
    logger.warning(f"Gemini client not available: {e}")

# Request models
class EmailScoreRequest(BaseModel):
    sender: str
    subject: str
    body: str
    mode: Optional[str] = "classic"  # classic, llm, hybrid

class EmailScoreResponse(BaseModel):
    ml_prediction: Optional[str] = None
    ml_score: Optional[float] = None
    llm_label: Optional[str] = None
    llm_confidence: Optional[float] = None
    llm_explanation: Optional[str] = None
    risk_level: str
    processing_time_ms: int
    model_info: dict

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "ml_available": classifier is not None,
        "llm_available": llm_client is not None,
        "timestamp": "2024-01-01T00:00:00Z"
    }

# Model info endpoint
@app.get("/model/info")
async def get_model_info():
    """Get model information"""
    if not classifier:
        raise HTTPException(status_code=503, detail="ML classifier not available")
    
    info = classifier.get_model_info()
    
    if llm_client:
        info["llm_stats"] = llm_client.get_stats()
    
    return info

# Main scoring endpoint
@app.post("/score", response_model=EmailScoreResponse)
async def score_email(request: EmailScoreRequest):
    """Score an email for phishing probability"""
    import time
    start_time = time.time()
    
    try:
        # Validate inputs
        if not request.sender or not request.subject or not request.body:
            raise HTTPException(status_code=400, detail="All fields (sender, subject, body) are required")
        
        # Initialize response
        response = EmailScoreResponse(
            risk_level="unknown",
            processing_time_ms=0,
            model_info={}
        )
        
        # ML classification
        if classifier and request.mode in ["classic", "hybrid"]:
            try:
                ml_result = classifier.predict(request.subject, request.body)
                response.ml_prediction = ml_result.get("prediction")
                response.ml_score = ml_result.get("phishing_probability")
                response.model_info["ml"] = "available"
            except Exception as e:
                logger.error(f"ML classification failed: {e}")
                response.model_info["ml"] = f"error: {str(e)}"
        
        # LLM classification
        if llm_client and request.mode in ["llm", "hybrid"]:
            try:
                # Import utils for redaction
                sys.path.append('../agent')
                from utils import redact_pii, truncate_text
                
                # Redact and truncate for LLM
                redacted_sender = redact_pii(request.sender)
                truncated_body = truncate_text(request.body, 1500)
                
                llm_result = llm_client.classify_email(
                    sender=redacted_sender,
                    subject=request.subject,
                    body=truncated_body
                )
                
                if llm_result:
                    response.llm_label = llm_result.label
                    response.llm_confidence = llm_result.confidence
                    response.llm_explanation = llm_result.explanation
                    response.model_info["llm"] = llm_result.model
                else:
                    response.llm_label = "unavailable"
                    response.llm_confidence = 0.0
                    response.llm_explanation = "LLM classification failed"
                    response.model_info["llm"] = "error"
                    
            except Exception as e:
                logger.error(f"LLM classification failed: {e}")
                response.llm_label = "error"
                response.llm_confidence = 0.0
                response.llm_explanation = f"Error: {str(e)}"
                response.model_info["llm"] = f"error: {str(e)}"
        
        # Determine risk level
        ml_score = response.ml_score or 0.0
        llm_confidence = response.llm_confidence or 0.0
        
        if ml_score >= 0.85 or llm_confidence >= 0.85:
            response.risk_level = "high"
        elif ml_score >= 0.6 or llm_confidence >= 0.6:
            response.risk_level = "medium"
        else:
            response.risk_level = "low"
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000
        response.processing_time_ms = int(processing_time)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in score_email: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Batch scoring endpoint
@app.post("/score/batch")
async def score_emails_batch(requests: list[EmailScoreRequest]):
    """Score multiple emails in batch"""
    if len(requests) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 emails per batch")
    
    results = []
    for request in requests:
        try:
            result = await score_email(request)
            results.append(result)
        except Exception as e:
            # Add error result for failed emails
            results.append({
                "error": str(e),
                "risk_level": "unknown",
                "processing_time_ms": 0,
                "model_info": {}
            })
    
    return {"results": results, "total": len(results)}

# Cache stats endpoint
@app.get("/cache/stats")
async def get_cache_stats():
    """Get LLM cache statistics"""
    if not llm_client:
        raise HTTPException(status_code=503, detail="LLM client not available")
    
    return llm_client.get_stats()

# Cache clear endpoint
@app.delete("/cache")
async def clear_cache():
    """Clear LLM cache"""
    if not llm_client or not llm_client.cache:
        raise HTTPException(status_code=503, detail="LLM cache not available")
    
    try:
        llm_client.cache.clear()
        return {"message": "Cache cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

# Metrics endpoint
@app.get("/metrics")
async def get_metrics():
    """Get API metrics (basic implementation)"""
    return {
        "ml_classifier_available": classifier is not None,
        "llm_client_available": llm_client is not None,
        "uptime": "N/A",  # Would implement proper uptime tracking
        "requests_processed": "N/A"  # Would implement request counting
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )
