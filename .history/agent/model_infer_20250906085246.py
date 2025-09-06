# agent/model_infer.py
import os
import pickle
import logging
from typing import Tuple
import numpy as np
from pathlib import Path

class MLInference:
    """Machine Learning inference for email classification"""
    
    def __init__(self, artifacts_path: str):
        self.artifacts_path = Path(artifacts_path)
        self.vectorizer = None
        self.model = None
        self.logger = logging.getLogger(__name__)
        
        self._load_artifacts()
    
    def _load_artifacts(self):
        """Load ML model and vectorizer"""
        try:
            # Load vectorizer
            vectorizer_path = self.artifacts_path / "vectorizer.pkl"
            if vectorizer_path.exists():
                with open(vectorizer_path, 'rb') as f:
                    self.vectorizer = pickle.load(f)
                self.logger.info("Vectorizer loaded successfully")
            else:
                raise FileNotFoundError(f"Vectorizer not found at {vectorizer_path}")
            
            # Load model
            model_path = self.artifacts_path / "model.pkl"
            if model_path.exists():
                with open(model_path, 'rb') as f:
                    self.model = pickle.load(f)
                self.logger.info("Model loaded successfully")
            else:
                raise FileNotFoundError(f"Model not found at {model_path}")
                
        except Exception as e:
            self.logger.error(f"Failed to load ML artifacts: {e}")
            raise
    
    def _preprocess_text(self, subject: str, body: str) -> str:
        """Preprocess email text for ML inference"""
        # Combine subject and body
        text = f"{subject} {body}" if subject and body else (subject or body or "")
        
        # Basic preprocessing
        text = text.lower()
        
        # Remove extra whitespace
        import re
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def predict(self, subject: str, body: str) -> Tuple[str, float]:
        """
        Predict phishing probability for an email
        
        Args:
            subject: Email subject line
            body: Email body content
            
        Returns:
            Tuple of (prediction_label, confidence_score)
        """
        try:
            if not self.vectorizer or not self.model:
                raise ValueError("Model artifacts not loaded")
            
            # Preprocess text
            text = self._preprocess_text(subject, body)
            
            if not text:
                self.logger.warning("Empty text input for prediction")
                return "legit", 0.5
            
            # Vectorize
            X = self.vectorizer.transform([text])
            
            # Get prediction and probability
            prediction = self.model.predict(X)[0]
            
            # Get probability scores
            if hasattr(self.model, 'predict_proba'):
                proba = self.model.predict_proba(X)[0]
                # Assuming binary classification with classes [0, 1] or ['legit', 'phishing']
                if len(proba) == 2:
                    # Get probability of phishing class
                    phishing_prob = proba[1] if hasattr(self.model, 'classes_') and self.model.classes_[1] == 'phishing' else proba[0]
                else:
                    phishing_prob = proba[0]
            elif hasattr(self.model, 'decision_function'):
                # For SVC, use decision function and apply sigmoid
                decision = self.model.decision_function(X)[0]
                phishing_prob = 1 / (1 + np.exp(-decision))  # Sigmoid transformation
            else:
                # Fallback - use prediction as binary indicator
                phishing_prob = 1.0 if prediction == 'phishing' else 0.0
            
            # Convert prediction to string label
            if isinstance(prediction, (int, np.integer)):
                prediction_label = "phishing" if prediction == 1 else "legit"
            else:
                prediction_label = str(prediction)
            
            # Ensure score is between 0 and 1
            score = max(0.0, min(1.0, float(phishing_prob)))
            
            self.logger.debug(f"ML prediction: {prediction_label}, score: {score:.3f}")
            
            return prediction_label, score
            
        except Exception as e:
            self.logger.error(f"ML prediction failed: {e}")
            # Return safe defaults
            return "legit", 0.0
    
    def get_model_info(self) -> dict:
        """Get information about the loaded model"""
        info = {
            'model_type': type(self.model).__name__ if self.model else None,
            'vectorizer_type': type(self.vectorizer).__name__ if self.vectorizer else None,
            'model_loaded': self.model is not None,
            'vectorizer_loaded': self.vectorizer is not None
        }
        
        if self.vectorizer:
            if hasattr(self.vectorizer, 'vocabulary_'):
                info['vocab_size'] = len(self.vectorizer.vocabulary_)
            if hasattr(self.vectorizer, 'get_feature_names_out'):
                info['feature_count'] = len(self.vectorizer.get_feature_names_out())
        
        if self.model:
            if hasattr(self.model, 'classes_'):
                info['classes'] = self.model.classes_.tolist()
            if hasattr(self.model, 'n_features_in_'):
                info['n_features'] = self.model.n_features_in_
        
        return info
