#!/bin/bash
# Test script for university email setup

set -e  # Exit on error

echo "=========================================="
echo "Email Management Tool - Setup Test"
echo "=========================================="
echo ""

# Check if in correct directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: Not in project directory"
    echo "Run: cd ~/personal-projects/AI-email-management-tool"
    exit 1
fi

# Activate venv
if [ ! -d "venv" ]; then
    echo "❌ Error: Virtual environment not found"
    echo "Run: python3 -m venv venv"
    exit 1
fi

source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Check .env file
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found"
    echo "Run: cp .env.example .env"
    echo "Then edit .env and add your ANTHROPIC_API_KEY"
    exit 1
fi

# Check if API key is set
if grep -q "your-key-here" .env; then
    echo "⚠️  Warning: API key not set in .env file"
    echo "Edit .env and replace 'your-key-here' with your actual Anthropic API key"
    echo ""
    read -p "Press Enter after you've updated the API key..."
fi

echo "✓ .env file exists"
echo ""

# Test basic imports
echo "Testing Python imports..."
python -c "import anthropic; print('✓ Anthropic SDK imported')"
python -c "import click; print('✓ Click imported')"
python -c "import rich; print('✓ Rich imported')"
python -c "from google_auth_oauthlib.flow import InstalledAppFlow; print('✓ Google Auth imported')"
echo ""

# Test profile creation
echo "Creating 'uni' profile..."
python main.py profile create uni --description "University of Plovdiv Email" --provider gmail 2>/dev/null || echo "⚠️  Profile might already exist"
echo "✓ Profile created"
echo ""

# Check credentials file
if [ ! -f "credentials_uni.json" ]; then
    echo "⚠️  Warning: credentials_uni.json not found"
    echo ""
    echo "To get Gmail API credentials:"
    echo "1. Go to https://console.cloud.google.com/"
    echo "2. Create/select a project"
    echo "3. Enable Gmail API"
    echo "4. Create OAuth 2.0 Desktop credentials"
    echo "5. Download as 'credentials_uni.json'"
    echo ""
    echo "See SETUP_GMAIL.md for detailed instructions"
    echo ""
    read -p "Press Enter after you've downloaded credentials_uni.json..."
fi

if [ -f "credentials_uni.json" ]; then
    echo "✓ credentials_uni.json found"
    echo ""

    echo "Ready to authenticate! This will:"
    echo "  1. Open a browser window"
    echo "  2. Ask you to sign in with stu2001321037@uni-plovdiv.bg"
    echo "  3. Ask for permission to access your Gmail"
    echo ""
    read -p "Press Enter to start authentication..."

    python main.py --profile uni setup --provider gmail

    echo ""
    echo "=========================================="
    echo "✓ Setup complete!"
    echo "=========================================="
    echo ""
    echo "Try these commands:"
    echo "  python main.py --profile uni fetch --limit 10"
    echo "  python main.py --profile uni inbox"
    echo "  python main.py --profile uni stats"
else
    echo ""
    echo "❌ Cannot proceed without credentials_uni.json"
    echo "Follow the instructions above to get it"
    exit 1
fi
