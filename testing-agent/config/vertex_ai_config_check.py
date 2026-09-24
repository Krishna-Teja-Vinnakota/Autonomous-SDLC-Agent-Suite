"""
Configuration Checker for Vertex AI
Verifies configuration matches credentials file
"""

import json
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.vertex_ai import VertexAIConfig, get_gemini_client


def check_configuration():
    """Check if Vertex AI configuration matches credentials file"""
    print("=" * 60)
    print("Vertex AI Configuration Check")
    print("=" * 60)
    
    # Check for credentials file
    project_root = Path(__file__).parent.parent
    cred_file = project_root / "credentials.json"
    
    if not cred_file.exists():
        print(f"\n[-] Credentials file not found: {cred_file}")
        print("   Please ensure the credentials file is in the project root")
        return False
    
    print(f"\n[+] Credentials file found: {cred_file.name}")
    
    # Read credentials file
    try:
        with open(cred_file, 'r') as f:
            cred_data = json.load(f)
        
        expected_project_id = cred_data.get('project_id')
        print(f"[+] Project ID in credentials: {expected_project_id}")
        
    except Exception as e:
        print(f"\n[-] Error reading credentials file: {e}")
        return False
    
    # Check configuration
    print("\n" + "-" * 60)
    print("Configuration Check")
    print("-" * 60)
    
    config = VertexAIConfig()
    
    # Check project ID
    if config.project_id:
        print(f"[+] Project ID configured: {config.project_id}")
        if config.project_id == expected_project_id:
            print("   [MATCH] Matches credentials file")
        else:
            print(f"   [MISMATCH] Expected: {expected_project_id}")
    else:
        print("[-] Project ID not configured")
        print(f"   Expected: {expected_project_id}")
        print("   Set GOOGLE_CLOUD_PROJECT environment variable")
    
    # Check credentials path
    if config.credentials_path:
        print(f"[+] Credentials path configured: {config.credentials_path}")
        if Path(config.credentials_path).exists():
            print("   [OK] File exists")
        else:
            print("   [-] File not found")
    else:
        print("[!] Credentials path not set")
        print("   Auto-detection will be used")
    
    # Check model
    print(f"[+] Model configured: {config.model_name}")
    if "gemini-2.0-flash" in config.model_name.lower() or "gemini-2.5-pro" in config.model_name.lower():
        print("   [OK] Using Gemini 2.0/2.5 model")
    else:
        print(f"   [!] Using older model: {config.model_name}")
        print("   Consider updating to gemini-2.0-flash or gemini-2.5-pro")
    
    # Check location
    print(f"[+] Location configured: {config.location}")
    
    # Validation
    print("\n" + "-" * 60)
    print("Validation Results")
    print("-" * 60)
    
    if config.is_configured():
        print("[+] Configuration is valid")
        
        # Try to create client
        print("\n" + "-" * 60)
        print("Client Initialization Test")
        print("-" * 60)
        
        try:
            client = get_gemini_client()
            if client and client.is_ready():
                print("[+] Gemini client initialized successfully")
                print(f"   Model: {config.model_name}")
                print(f"   Project: {config.project_id}")
                print(f"   Location: {config.location}")
                return True
            else:
                print("[-] Client initialization failed")
                errors = config.get_validation_errors()
                for error in errors:
                    print(f"   - {error}")
                return False
        except Exception as e:
            print(f"[-] Error initializing client: {e}")
            return False
    else:
        print("[-] Configuration validation failed")
        errors = config.get_validation_errors()
        for error in errors:
            print(f"   - {error}")
        return False


def print_recommendations():
    """Print configuration recommendations"""
    print("\n" + "=" * 60)
    print("Configuration Recommendations")
    print("=" * 60)
    
    project_root = Path(__file__).parent.parent
    cred_file = project_root / "credentials.json"
    
    if cred_file.exists():
        with open(cred_file, 'r') as f:
            cred_data = json.load(f)
        
        project_id = cred_data.get('project_id')
        cred_path = str(cred_file.absolute())
        
        print("\nFor Windows (PowerShell):")
        print(f'$env:GOOGLE_CLOUD_PROJECT="{project_id}"')
        print(f'$env:GOOGLE_APPLICATION_CREDENTIALS="{cred_path}"')
        print('$env:VERTEX_AI_MODEL="gemini-2.0-flash"')
        
        print("\nFor macOS/Linux:")
        print(f'export GOOGLE_CLOUD_PROJECT="{project_id}"')
        print(f'export GOOGLE_APPLICATION_CREDENTIALS="{cred_path}"')
        print('export VERTEX_AI_MODEL="gemini-2.0-flash"')
        
        print("\nOr create a .env file:")
        print(f"GOOGLE_CLOUD_PROJECT={project_id}")
        print(f"GOOGLE_APPLICATION_CREDENTIALS={cred_path}")
        print("VERTEX_AI_MODEL=gemini-2.0-flash")


if __name__ == "__main__":
    success = check_configuration()
    print_recommendations()
    
    if success:
        print("\n" + "=" * 60)
        print("[SUCCESS] Configuration Check Complete - All Good!")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("[WARNING] Configuration Issues Found - See Above")
        print("=" * 60)

