"""
Setup script for AutoSDLC Test Agent
Run this to verify installation and setup
"""

import sys
import subprocess
from pathlib import Path


def check_python_version():
    """Check if Python version is 3.9+"""
    print("🔍 Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 9:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} detected")
        return True
    else:
        print(f"❌ Python 3.9+ required, found {version.major}.{version.minor}.{version.micro}")
        return False


def check_git_installed():
    """Check if Git is installed"""
    print("\n🔍 Checking Git installation...")
    try:
        result = subprocess.run(
            ['git', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print(f"✅ {result.stdout.strip()}")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    print("⚠️  Git not found (optional, needed for GitHub repository cloning)")
    return True  # Not critical


def create_directories():
    """Create necessary directories"""
    print("\n📁 Creating workspace directories...")
    directories = [
        Path("workspaces"),
        Path("temp"),
    ]
    
    for directory in directories:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created/verified: {directory}")
        except Exception as e:
            print(f"❌ Failed to create {directory}: {e}")
            return False
    
    return True


def check_requirements():
    """Check if requirements.txt exists"""
    print("\n📦 Checking requirements file...")
    req_file = Path("requirements.txt")
    if req_file.exists():
        print("✅ requirements.txt found")
        return True
    else:
        print("❌ requirements.txt not found")
        return False


def install_dependencies():
    """Install Python dependencies"""
    print("\n📥 Installing dependencies...")
    print("This may take a few minutes...")
    
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            print("✅ Dependencies installed successfully")
            return True
        else:
            print(f"❌ Failed to install dependencies:\n{result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Installation timed out")
        return False
    except Exception as e:
        print(f"❌ Error during installation: {e}")
        return False


def verify_imports():
    """Verify key imports work"""
    print("\n🔍 Verifying imports...")
    
    imports = [
        ('streamlit', 'Streamlit UI framework'),
        ('git', 'GitPython for repository cloning'),
        ('pathlib', 'Path utilities'),
    ]
    
    all_ok = True
    for module, description in imports:
        try:
            __import__(module)
            print(f"✅ {description}")
        except ImportError:
            print(f"❌ {description} - import failed")
            all_ok = False
    
    return all_ok


def check_tools_module():
    """Check if tools module is accessible"""
    print("\n🔧 Checking tools module...")
    
    try:
        from tools import GitTool, UnzipTool, FileIndexer
        print("✅ Tools module loaded successfully")
        print(f"   - GitTool")
        print(f"   - UnzipTool")
        print(f"   - FileIndexer")
        return True
    except Exception as e:
        print(f"❌ Failed to import tools module: {e}")
        return False


def main():
    """Main setup function"""
    print("=" * 60)
    print("🤖 AutoSDLC Test Agent - Setup & Verification")
    print("=" * 60)
    
    checks = [
        ("Python Version", check_python_version),
        ("Git Installation", check_git_installed),
        ("Directory Structure", create_directories),
        ("Requirements File", check_requirements),
    ]
    
    # Run pre-install checks
    print("\n" + "=" * 60)
    print("📋 Pre-Installation Checks")
    print("=" * 60)
    
    all_passed = True
    for name, check in checks:
        if not check():
            all_passed = False
    
    if not all_passed:
        print("\n❌ Some pre-installation checks failed")
        print("Please resolve the issues above before continuing")
        return False
    
    # Install dependencies
    print("\n" + "=" * 60)
    print("📦 Dependency Installation")
    print("=" * 60)
    
    if not install_dependencies():
        print("\n❌ Dependency installation failed")
        return False
    
    # Post-install verification
    print("\n" + "=" * 60)
    print("✅ Post-Installation Verification")
    print("=" * 60)
    
    if not verify_imports():
        print("\n⚠️  Some imports failed - try reinstalling dependencies")
        return False
    
    if not check_tools_module():
        print("\n⚠️  Tools module verification failed")
        return False
    
    # Success!
    print("\n" + "=" * 60)
    print("🎉 Setup Complete!")
    print("=" * 60)
    print("\n✅ All checks passed - system ready to use!")
    print("\n📝 Next Steps:")
    print("   1. Run: streamlit run app.py")
    print("   2. Open http://localhost:8501 in your browser")
    print("   3. Upload a project to begin analysis")
    print("\n📚 Documentation:")
    print("   - README.md for full documentation")
    print("   - QUICKSTART.md for quick start guide")
    print("\n" + "=" * 60)
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

