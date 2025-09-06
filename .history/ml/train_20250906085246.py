# ml/train.py
import os
import pandas as pd
import numpy as np
import pickle
import logging
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
import re

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailPreprocessor:
    """Preprocessor for email text data"""
    
    def __init__(self):
        self.html_tag_pattern = re.compile(r'<[^>]+>')
        self.url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        
    def preprocess(self, text):
        """Preprocess email text"""
        if not isinstance(text, str):
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove HTML tags
        text = self.html_tag_pattern.sub(' ', text)
        
        # Replace URLs with token
        text = self.url_pattern.sub(' URL_TOKEN ', text)
        
        # Replace email addresses with token
        text = self.email_pattern.sub(' EMAIL_TOKEN ', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def combine_features(self, subject, body):
        """Combine subject and body with preprocessing"""
        subject = self.preprocess(subject) if subject else ""
        body = self.preprocess(body) if body else ""
        
        # Give more weight to subject
        combined = f"{subject} {subject} {body}"
        return combined

class MLTrainer:
    """Machine Learning trainer for phishing detection"""
    
    def __init__(self, data_path: str, artifacts_path: str):
        self.data_path = Path(data_path)
        self.artifacts_path = Path(artifacts_path)
        self.artifacts_path.mkdir(parents=True, exist_ok=True)
        
        self.preprocessor = EmailPreprocessor()
        self.vectorizer = None
        self.model = None
        
    def load_data(self):
        """Load and validate training data"""
        logger.info(f"Loading data from {self.data_path}")
        
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_path}")
        
        # Load CSV
        df = pd.read_csv(self.data_path)
        
        # Validate columns
        required_columns = ['subject', 'body', 'label']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Clean data
        df = df.dropna(subset=['subject', 'body', 'label'])
        
        # Validate labels
        valid_labels = {'phishing', 'legit'}
        invalid_labels = set(df['label'].unique()) - valid_labels
        if invalid_labels:
            raise ValueError(f"Invalid labels found: {invalid_labels}. Expected: {valid_labels}")
        
        logger.info(f"Loaded {len(df)} samples")
        logger.info(f"Label distribution:\n{df['label'].value_counts()}")
        
        return df
    
    def prepare_features(self, df):
        """Prepare features for training"""
        logger.info("Preparing features...")
        
        # Combine subject and body
        X_text = []
        for _, row in df.iterrows():
            combined = self.preprocessor.combine_features(row['subject'], row['body'])
            X_text.append(combined)
        
        # Labels
        y = df['label'].values
        
        # Create TF-IDF vectorizer
        self.vectorizer = TfidfVectorizer(
            max_features=10000,
            ngram_range=(1, 3),  # Unigrams, bigrams, trigrams
            min_df=2,            # Ignore terms that appear in < 2 documents
            max_df=0.95,         # Ignore terms that appear in > 95% of documents
            stop_words='english',
            lowercase=True,
            token_pattern=r'\b\w+\b'
        )
        
        # Fit and transform
        X = self.vectorizer.fit_transform(X_text)
        
        logger.info(f"Feature matrix shape: {X.shape}")
        logger.info(f"Vocabulary size: {len(self.vectorizer.vocabulary_)}")
        
        return X, y
    
    def train_model(self, X, y):
        """Train the classification model"""
        logger.info("Training model...")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Train base model
        base_model = LinearSVC(
            C=1.0,
            random_state=42,
            max_iter=10000
        )
        
        # Calibrate for probability output
        self.model = CalibratedClassifierCV(base_model, cv=3)
        self.model.fit(X_train, y_train)
        
        # Evaluate
        self._evaluate_model(X_train, X_test, y_train, y_test)
        
        return self.model
    
    def _evaluate_model(self, X_train, X_test, y_train, y_test):
        """Evaluate model performance"""
        logger.info("Evaluating model...")
        
        # Training accuracy
        train_score = self.model.score(X_train, y_train)
        logger.info(f"Training accuracy: {train_score:.3f}")
        
        # Test accuracy
        test_score = self.model.score(X_test, y_test)
        logger.info(f"Test accuracy: {test_score:.3f}")
        
        # Predictions
        y_pred = self.model.predict(X_test)
        y_proba = self.model.predict_proba(X_test)
        
        # Classification report
        logger.info("Classification Report:")
        print(classification_report(y_test, y_pred))
        
        # Confusion matrix
        logger.info("Confusion Matrix:")
        print(confusion_matrix(y_test, y_pred))
        
        # AUC score
        if len(self.model.classes_) == 2:
            # Binary classification
            auc = roc_auc_score(y_test, y_proba[:, 1])
            logger.info(f"ROC AUC: {auc:.3f}")
        
        # Cross-validation
        cv_scores = cross_val_score(self.model, X_train, y_train, cv=5)
        logger.info(f"Cross-validation scores: {cv_scores}")
        logger.info(f"CV mean: {cv_scores.mean():.3f} (+/- {cv_scores.std() * 2:.3f})")
    
    def save_artifacts(self):
        """Save trained model and vectorizer"""
        logger.info("Saving artifacts...")
        
        # Save vectorizer
        vectorizer_path = self.artifacts_path / "vectorizer.pkl"
        with open(vectorizer_path, 'wb') as f:
            pickle.dump(self.vectorizer, f)
        logger.info(f"Vectorizer saved to {vectorizer_path}")
        
        # Save model
        model_path = self.artifacts_path / "model.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump(self.model, f)
        logger.info(f"Model saved to {model_path}")
        
        # Save metadata
        metadata = {
            'model_type': type(self.model).__name__,
            'vectorizer_type': type(self.vectorizer).__name__,
            'vocabulary_size': len(self.vectorizer.vocabulary_),
            'classes': self.model.classes_.tolist(),
            'feature_count': self.vectorizer.transform(['test']).shape[1]
        }
        
        metadata_path = self.artifacts_path / "metadata.json"
        import json
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Metadata saved to {metadata_path}")
    
    def train(self):
        """Main training pipeline"""
        logger.info("Starting ML training pipeline...")
        
        # Load data
        df = self.load_data()
        
        # Prepare features
        X, y = self.prepare_features(df)
        
        # Train model
        self.train_model(X, y)
        
        # Save artifacts
        self.save_artifacts()
        
        logger.info("Training completed successfully!")

def create_synthetic_data():
    """Create synthetic training data for demo purposes"""
    logger.info("Creating synthetic training data...")
    
    phishing_samples = [
        {
            'subject': 'URGENT: Your account will be suspended',
            'body': 'Your account has been compromised and will be suspended immediately unless you verify your identity. Click here to verify: http://phishing-example.com/verify. Act now to avoid permanent account closure.',
            'label': 'phishing'
        },
        {
            'subject': 'Congratulations! You have won $1,000,000',
            'body': 'You are the lucky winner of our international lottery! To claim your prize of $1,000,000, please send your personal information immediately. This offer expires in 24 hours.',
            'label': 'phishing'
        },
        {
            'subject': 'Security Alert: Unusual Activity Detected',
            'body': 'We have detected unusual activity on your account. Please verify your identity immediately by clicking this link: http://fake-bank.org/verify. Your account will be locked if you do not respond.',
            'label': 'phishing'
        },
        {
            'subject': 'Update your payment information',
            'body': 'Your payment method has expired. Please update your payment information to continue using our services. Click here: http://scam-site.com/payment',
            'label': 'phishing'
        },
        {
            'subject': 'Inheritance Fund Transfer',
            'body': 'Greetings, I am Prince from Nigeria. I have an inheritance fund that needs to be transferred. I need your help to transfer $5 million. Please send your bank details.',
            'label': 'phishing'
        }
    ]
    
    legit_samples = [
        {
            'subject': 'Weekly team meeting reminder',
            'body': 'Hi Team, Just a reminder that our weekly team meeting is scheduled for tomorrow at 2 PM in the conference room. Please let me know if you have any agenda items. Thanks, Sarah',
            'label': 'legit'
        },
        {
            'subject': 'Order confirmation #12345',
            'body': 'Thank you for your recent purchase. Your order #12345 has been confirmed and will be shipped within 2-3 business days. You can track your order using the provided tracking number.',
            'label': 'legit'
        },
        {
            'subject': 'Monthly newsletter - Tech Updates',
            'body': 'Welcome to our monthly tech newsletter. This month we cover the latest developments in AI, cloud computing, and cybersecurity. Read more about industry trends and best practices.',
            'label': 'legit'
        },
        {
            'subject': 'Project deadline reminder',
            'body': 'This is a friendly reminder that the project deadline is approaching next Friday. Please ensure all deliverables are completed and submitted on time. Contact me if you need any assistance.',
            'label': 'legit'
        },
        {
            'subject': 'Welcome to our service',
            'body': 'Welcome to our platform! We are excited to have you as a new member. Please take a moment to complete your profile and explore the features available to you.',
            'label': 'legit'
        }
    ]
    
    # Create more samples by variations
    all_samples = []
    
    # Add original samples multiple times with slight variations
    for sample in phishing_samples + legit_samples:
        for i in range(10):  # Create 10 variations of each
            all_samples.append(sample.copy())
    
    # Add some variations
    import random
    variations = [
        'Please respond immediately.',
        'This is urgent.',
        'Time sensitive matter.',
        'Action required.',
        'Thank you for your attention.',
        'Best regards,',
        'Please contact us if you have questions.',
        'We appreciate your business.'
    ]
    
    for sample in all_samples[-20:]:  # Add variations to last 20 samples
        sample['body'] += ' ' + random.choice(variations)
    
    df = pd.DataFrame(all_samples)
    return df

def main():
    # Configuration
    data_path = os.getenv('DATA_PATH', '/app/data/synthetic_emails.csv')
    artifacts_path = os.getenv('ARTIFACTS_PATH', '/app/artifacts')
    
    # Create synthetic data if file doesn't exist
    if not Path(data_path).exists():
        logger.info("Creating synthetic dataset...")
        synthetic_df = create_synthetic_data()
        Path(data_path).parent.mkdir(parents=True, exist_ok=True)
        synthetic_df.to_csv(data_path, index=False)
        logger.info(f"Synthetic data saved to {data_path}")
    
    # Train model
    trainer = MLTrainer(data_path, artifacts_path)
    trainer.train()

if __name__ == "__main__":
    main()
