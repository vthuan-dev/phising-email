# ml/infer.py
import os
import pickle
import argparse
import logging
from pathlib import Path
import json

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailClassifier:
    """Standalone email classifier for CLI usage"""
    
    def __init__(self, artifacts_path: str):
        self.artifacts_path = Path(artifacts_path)
        self.vectorizer = None
        self.model = None
        self.metadata = None
        
        self._load_artifacts()
    
    def _load_artifacts(self):
        """Load trained model artifacts"""
        try:
            # Load vectorizer
            vectorizer_path = self.artifacts_path / "vectorizer.pkl"
            with open(vectorizer_path, 'rb') as f:
                self.vectorizer = pickle.load(f)
            
            # Load model
            model_path = self.artifacts_path / "model.pkl"
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
            
            # Load metadata
            metadata_path = self.artifacts_path / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    self.metadata = json.load(f)
            
            logger.info("Model artifacts loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load artifacts: {e}")
            raise
    
    def preprocess_text(self, subject: str, body: str) -> str:
        """Preprocess email text (should match training preprocessing)"""
        import re
        
        # Combine subject and body (same as training)
        subject = subject.lower() if subject else ""
        body = body.lower() if body else ""
        
        # Remove HTML tags
        html_pattern = re.compile(r'<[^>]+>')
        body = html_pattern.sub(' ', body)
        
        # Replace URLs
        url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        body = url_pattern.sub(' URL_TOKEN ', body)
        
        # Replace emails
        email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        body = email_pattern.sub(' EMAIL_TOKEN ', body)
        
        # Remove extra whitespace
        body = re.sub(r'\s+', ' ', body)
        subject = re.sub(r'\s+', ' ', subject)
        
        # Combine with subject weight (same as training)
        combined = f"{subject} {subject} {body}"
        return combined.strip()
    
    def predict(self, subject: str, body: str) -> dict:
        """Predict phishing probability"""
        try:
            # Preprocess
            text = self.preprocess_text(subject, body)
            
            # Vectorize
            X = self.vectorizer.transform([text])
            
            # Predict
            prediction = self.model.predict(X)[0]
            probabilities = self.model.predict_proba(X)[0]
            
            # Get probability for phishing class
            if hasattr(self.model, 'classes_'):
                classes = self.model.classes_
                class_idx = list(classes).index('phishing') if 'phishing' in classes else 1
                phishing_prob = probabilities[class_idx]
            else:
                phishing_prob = probabilities[1] if len(probabilities) > 1 else probabilities[0]
            
            return {
                'prediction': prediction,
                'phishing_probability': float(phishing_prob),
                'legit_probability': float(1 - phishing_prob),
                'confidence': float(max(probabilities))
            }
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return {
                'prediction': 'error',
                'phishing_probability': 0.0,
                'legit_probability': 0.0,
                'confidence': 0.0,
                'error': str(e)
            }
    
    def get_model_info(self) -> dict:
        """Get model information"""
        info = {
            'model_loaded': self.model is not None,
            'vectorizer_loaded': self.vectorizer is not None,
            'metadata': self.metadata
        }
        
        if self.model:
            info['model_type'] = type(self.model).__name__
            if hasattr(self.model, 'classes_'):
                info['classes'] = self.model.classes_.tolist()
        
        if self.vectorizer:
            info['vectorizer_type'] = type(self.vectorizer).__name__
            if hasattr(self.vectorizer, 'vocabulary_'):
                info['vocabulary_size'] = len(self.vectorizer.vocabulary_)
        
        return info

def main():
    parser = argparse.ArgumentParser(description='Email phishing detection CLI')
    parser.add_argument('--artifacts-path', default='/app/artifacts', 
                       help='Path to model artifacts')
    parser.add_argument('--subject', required=True, 
                       help='Email subject')
    parser.add_argument('--body', required=True, 
                       help='Email body')
    parser.add_argument('--format', choices=['json', 'text'], default='text',
                       help='Output format')
    parser.add_argument('--info', action='store_true',
                       help='Show model information')
    
    args = parser.parse_args()
    
    try:
        # Initialize classifier
        classifier = EmailClassifier(args.artifacts_path)
        
        if args.info:
            # Show model info
            info = classifier.get_model_info()
            if args.format == 'json':
                print(json.dumps(info, indent=2))
            else:
                print("Model Information:")
                for key, value in info.items():
                    print(f"  {key}: {value}")
            return
        
        # Make prediction
        result = classifier.predict(args.subject, args.body)
        
        if args.format == 'json':
            print(json.dumps(result, indent=2))
        else:
            print(f"Prediction: {result['prediction']}")
            print(f"Phishing Probability: {result['phishing_probability']:.3f}")
            print(f"Confidence: {result['confidence']:.3f}")
            
            if result['prediction'] == 'phishing':
                print("⚠️  WARNING: This email appears to be phishing!")
            else:
                print("✅ This email appears to be legitimate.")
    
    except Exception as e:
        logger.error(f"CLI error: {e}")
        if args.format == 'json':
            print(json.dumps({'error': str(e)}))
        else:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
