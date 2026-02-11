"""
Configuration management for Developer Agent
Handles MongoDB and other service connections
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

class DatabaseConfig:
    """MongoDB configuration and connection management"""
    
    def __init__(self):
        self.mongodb_uri = os.getenv('MONGODB_URI')
        if not self.mongodb_uri:
            raise ValueError("MONGODB_URI not found in .env file")
        
        self.client = MongoClient(self.mongodb_uri)
        self.db = self.client['SDLC']  # Database name
        self.tracking_collection = self.db['tracking']  # Collection name
        
    def get_tracking_collection(self):
        """Get the tracking collection for file changes"""
        return self.tracking_collection
    
    def test_connection(self) -> bool:
        """Test MongoDB connection"""
        try:
            self.client.admin.command('ping')
            print("✅ MongoDB connection successful")
            return True
        except Exception as e:
            print(f"❌ MongoDB connection failed: {e}")
            return False
    
    def close_connection(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()

# Global instance
db_config = DatabaseConfig()















