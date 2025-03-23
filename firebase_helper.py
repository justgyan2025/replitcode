import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class FirebaseHelper:
    def __init__(self):
        self.initialize_firebase()
        self.db = firestore.client()
    
    def initialize_firebase(self):
        """Initialize Firebase Admin SDK if not already initialized"""
        if firebase_admin._apps:
            return

        # Check if service account key file exists
        service_account_key_path = 'service-account-key.json'
        
        if os.path.exists(service_account_key_path):
            # Use service account key file
            cred = credentials.Certificate(service_account_key_path)
        else:
            # Create service account key file from environment variables
            try:
                service_account_info = os.getenv('FIREBASE_SERVICE_ACCOUNT')
                if service_account_info:
                    service_account_dict = json.loads(service_account_info)
                    with open(service_account_key_path, 'w') as f:
                        json.dump(service_account_dict, f)
                    cred = credentials.Certificate(service_account_key_path)
                else:
                    # Fall back to application default credentials
                    cred = credentials.ApplicationDefault()
            except Exception as e:
                print(f"Error setting up Firebase credentials: {e}")
                # Fall back to application default credentials
                cred = credentials.ApplicationDefault()
        
        # Initialize the app
        firebase_admin.initialize_app(cred, {
            'projectId': os.getenv('FIREBASE_PROJECT_ID'),
        })
    
    def get_user_stocks(self, user_email):
        """Get stocks for a user from Firestore"""
        stocks_ref = self.db.collection('users').document(user_email).collection('stocks')
        return [doc.to_dict() for doc in stocks_ref.stream()]
    
    def add_stock(self, user_email, symbol, data=None):
        """Add a stock to a user's portfolio"""
        if data is None:
            data = {}
        
        stocks_ref = self.db.collection('users').document(user_email).collection('stocks')
        data.update({
            'symbol': symbol,
            'added_at': firestore.SERVER_TIMESTAMP
        })
        stocks_ref.document(symbol).set(data)
    
    def get_user_mutual_funds(self, user_email):
        """Get mutual funds for a user from Firestore"""
        funds_ref = self.db.collection('users').document(user_email).collection('mutual_funds')
        return [doc.to_dict() for doc in funds_ref.stream()]
    
    def add_mutual_fund(self, user_email, scheme_code, data=None):
        """Add a mutual fund to a user's portfolio"""
        if data is None:
            data = {}
        
        funds_ref = self.db.collection('users').document(user_email).collection('mutual_funds')
        data.update({
            'scheme_code': scheme_code,
            'added_at': firestore.SERVER_TIMESTAMP
        })
        funds_ref.document(scheme_code).set(data)
    
    def get_user_policies(self, user_email):
        """Get insurance policies for a user from Firestore"""
        policies_ref = self.db.collection('users').document(user_email).collection('policies')
        return [doc.to_dict() for doc in policies_ref.stream()]
    
    def add_policy(self, user_email, policy_id, policy_data):
        """Add an insurance policy to a user's portfolio"""
        policies_ref = self.db.collection('users').document(user_email).collection('policies')
        policy_data.update({
            'added_at': firestore.SERVER_TIMESTAMP
        })
        policies_ref.document(policy_id).set(policy_data)

# Singleton instance
firebase_helper = FirebaseHelper() 