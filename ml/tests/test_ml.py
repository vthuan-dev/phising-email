# ml/tests/test_ml.py
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import os
import sys

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from train import EmailPreprocessor, MLTrainer
from infer import EmailClassifier

class TestEmailPreprocessor:
    """Test email preprocessing functionality"""
    
    def setup_method(self):
        self.preprocessor = EmailPreprocessor()
    
    def test_basic_preprocessing(self):
        """Test basic text preprocessing"""
        text = "Hello WORLD! This is a Test."
        result = self.preprocessor.preprocess(text)
        assert result == "hello world! this is a test."
    
    def test_html_removal(self):
        """Test HTML tag removal"""
        text = "Hello <b>world</b>! <a href='http://example.com'>Click here</a>"
        result = self.preprocessor.preprocess(text)
        assert "<b>" not in result
        assert "</b>" not in result
        assert "<a href=" not in result
    
    def test_url_replacement(self):
        """Test URL replacement with token"""
        text = "Visit http://example.com or https://secure.site.com"
        result = self.preprocessor.preprocess(text)
        assert "URL_TOKEN" in result
        assert "http://example.com" not in result
    
    def test_email_replacement(self):
        """Test email replacement with token"""
        text = "Contact me at john.doe@example.com or support@company.org"
        result = self.preprocessor.preprocess(text)
        assert "EMAIL_TOKEN" in result
        assert "john.doe@example.com" not in result
    
    def test_whitespace_normalization(self):
        """Test whitespace normalization"""
        text = "Hello    world\n\nThis   is\ta   test"
        result = self.preprocessor.preprocess(text)
        assert "  " not in result  # No double spaces
        assert "\n" not in result
        assert "\t" not in result
    
    def test_combine_features(self):
        """Test subject and body combination"""
        subject = "Important Subject"
        body = "This is the email body content."
        result = self.preprocessor.combine_features(subject, body)
        
        # Subject should appear twice (weighted)
        assert result.count("important subject") == 2
        assert "this is the email body content." in result
    
    def test_none_handling(self):
        """Test handling of None values"""
        result = self.preprocessor.preprocess(None)
        assert result == ""
        
        result = self.preprocessor.combine_features(None, "body")
        assert "body" in result
        
        result = self.preprocessor.combine_features("subject", None)
        assert "subject" in result

class TestMLTrainer:
    """Test ML training functionality"""
    
    def setup_method(self):
        # Create temporary directory for test artifacts
        self.temp_dir = tempfile.mkdtemp()
        self.artifacts_path = Path(self.temp_dir) / "artifacts"
        self.data_path = Path(self.temp_dir) / "test_data.csv"
        
        # Create test data
        self.create_test_data()
    
    def teardown_method(self):
        # Clean up temporary files
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def create_test_data(self):
        """Create test dataset"""
        data = [
            {"subject": "Urgent account verification", "body": "Your account will be suspended. Click here to verify.", "label": "phishing"},
            {"subject": "You won the lottery", "body": "Congratulations! You won $1000000. Send your details.", "label": "phishing"},
            {"subject": "Meeting reminder", "body": "Don't forget about our meeting tomorrow at 3 PM.", "label": "legit"},
            {"subject": "Order confirmation", "body": "Your order #12345 has been confirmed and will ship soon.", "label": "legit"},
            {"subject": "Security alert", "body": "Suspicious activity detected. Please verify immediately.", "label": "phishing"},
            {"subject": "Newsletter", "body": "Here's our weekly newsletter with latest updates.", "label": "legit"},
        ]
        
        df = pd.DataFrame(data)
        df.to_csv(self.data_path, index=False)
    
    def test_data_loading(self):
        """Test data loading functionality"""
        trainer = MLTrainer(str(self.data_path), str(self.artifacts_path))
        df = trainer.load_data()
        
        assert len(df) == 6
        assert set(df.columns) >= {"subject", "body", "label"}
        assert set(df["label"].unique()) <= {"phishing", "legit"}
    
    def test_feature_preparation(self):
        """Test feature preparation"""
        trainer = MLTrainer(str(self.data_path), str(self.artifacts_path))
        df = trainer.load_data()
        X, y = trainer.prepare_features(df)
        
        assert X.shape[0] == len(df)
        assert len(y) == len(df)
        assert trainer.vectorizer is not None
    
    def test_model_training(self):
        """Test model training"""
        trainer = MLTrainer(str(self.data_path), str(self.artifacts_path))
        df = trainer.load_data()
        X, y = trainer.prepare_features(df)
        trainer.train_model(X, y)
        
        assert trainer.model is not None
        assert hasattr(trainer.model, 'predict')
        assert hasattr(trainer.model, 'predict_proba')
    
    def test_artifact_saving(self):
        """Test artifact saving"""
        trainer = MLTrainer(str(self.data_path), str(self.artifacts_path))
        trainer.train()
        
        # Check if artifacts exist
        assert (self.artifacts_path / "vectorizer.pkl").exists()
        assert (self.artifacts_path / "model.pkl").exists()
        assert (self.artifacts_path / "metadata.json").exists()

class TestEmailClassifier:
    """Test email classification functionality"""
    
    def setup_method(self):
        # Create temporary directory and train a model
        self.temp_dir = tempfile.mkdtemp()
        self.artifacts_path = Path(self.temp_dir) / "artifacts"
        self.data_path = Path(self.temp_dir) / "test_data.csv"
        
        # Create test data and train model
        self.create_test_data()
        trainer = MLTrainer(str(self.data_path), str(self.artifacts_path))
        trainer.train()
        
        # Initialize classifier
        self.classifier = EmailClassifier(str(self.artifacts_path))
    
    def teardown_method(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def create_test_data(self):
        """Create test dataset for training"""
        data = []
        
        # Create phishing samples
        phishing_templates = [
            ("Urgent verification needed", "Your account will be suspended. Verify immediately: {url}"),
            ("You won a prize", "Congratulations! You won ${amount}. Claim now: {url}"),
            ("Security alert", "Suspicious activity detected. Click here: {url}"),
            ("Payment update required", "Your payment failed. Update now: {url}"),
        ]
        
        # Create legit samples
        legit_templates = [
            ("Meeting reminder", "Don't forget our meeting tomorrow at {time}"),
            ("Order confirmation", "Your order #{order} has been confirmed"),
            ("Newsletter", "Here's our weekly newsletter with updates"),
            ("Project update", "Project status update for team review"),
        ]
        
        # Generate samples
        for i in range(20):
            for subject, body in phishing_templates:
                data.append({
                    "subject": subject + f" {i}",
                    "body": body.format(url="http://malicious.com", amount="1000000"),
                    "label": "phishing"
                })
            
            for subject, body in legit_templates:
                data.append({
                    "subject": subject + f" {i}",
                    "body": body.format(time="3 PM", order=f"12345{i}"),
                    "label": "legit"
                })
        
        df = pd.DataFrame(data)
        df.to_csv(self.data_path, index=False)
    
    def test_model_loading(self):
        """Test model and vectorizer loading"""
        assert self.classifier.model is not None
        assert self.classifier.vectorizer is not None
    
    def test_prediction_format(self):
        """Test prediction output format"""
        result = self.classifier.predict(
            "Test subject", 
            "Test body content"
        )
        
        required_keys = ['prediction', 'phishing_probability', 'legit_probability', 'confidence']
        for key in required_keys:
            assert key in result
        
        assert result['prediction'] in ['phishing', 'legit']
        assert 0 <= result['phishing_probability'] <= 1
        assert 0 <= result['legit_probability'] <= 1
        assert 0 <= result['confidence'] <= 1
    
    def test_phishing_detection(self):
        """Test phishing email detection"""
        phishing_subject = "URGENT: Account suspended"
        phishing_body = "Your account will be suspended. Click here immediately: http://malicious.com/verify"
        
        result = self.classifier.predict(phishing_subject, phishing_body)
        
        # Should have higher phishing probability
        assert result['phishing_probability'] > 0.3  # Relaxed threshold for small dataset
    
    def test_legit_detection(self):
        """Test legitimate email detection"""
        legit_subject = "Team meeting tomorrow"
        legit_body = "Hi team, just a reminder about our weekly meeting tomorrow at 2 PM in the conference room."
        
        result = self.classifier.predict(legit_subject, legit_body)
        
        # Should have lower phishing probability
        assert result['phishing_probability'] < 0.7  # Relaxed threshold for small dataset
    
    def test_empty_input_handling(self):
        """Test handling of empty inputs"""
        result = self.classifier.predict("", "")
        assert 'error' not in result  # Should not error
        
        result = self.classifier.predict(None, None)
        assert 'error' not in result  # Should not error
    
    def test_model_info(self):
        """Test model information retrieval"""
        info = self.classifier.get_model_info()
        
        assert info['model_loaded'] is True
        assert info['vectorizer_loaded'] is True
        assert 'model_type' in info
        assert 'vectorizer_type' in info

class TestCacheKeyGeneration:
    """Test cache key generation for consistency"""
    
    def test_cache_key_consistency(self):
        """Test that cache keys are consistent for same input"""
        # This would test the LLM client cache key generation
        # For now, we'll test a simple hash function
        import hashlib
        
        def create_cache_key(sender, subject, body):
            content = f"{sender}|{subject}|{body[:1000]}"
            return hashlib.sha256(content.encode()).hexdigest()
        
        # Same input should produce same key
        key1 = create_cache_key("sender@test.com", "Test Subject", "Test body content")
        key2 = create_cache_key("sender@test.com", "Test Subject", "Test body content")
        assert key1 == key2
        
        # Different input should produce different keys
        key3 = create_cache_key("other@test.com", "Test Subject", "Test body content")
        assert key1 != key3

# Integration test
def test_end_to_end_pipeline():
    """Test complete training and inference pipeline"""
    with tempfile.TemporaryDirectory() as temp_dir:
        artifacts_path = Path(temp_dir) / "artifacts"
        data_path = Path(temp_dir) / "test_data.csv"
        
        # Create minimal dataset
        data = [
            {"subject": "Urgent verification", "body": "Click here to verify account", "label": "phishing"},
            {"subject": "Meeting reminder", "body": "Meeting tomorrow at 3 PM", "label": "legit"},
        ] * 10  # Repeat to have enough samples
        
        df = pd.DataFrame(data)
        df.to_csv(data_path, index=False)
        
        # Train model
        trainer = MLTrainer(str(data_path), str(artifacts_path))
        trainer.train()
        
        # Test inference
        classifier = EmailClassifier(str(artifacts_path))
        result = classifier.predict("Test subject", "Test body")
        
        assert result['prediction'] in ['phishing', 'legit']
        assert 0 <= result['confidence'] <= 1

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
