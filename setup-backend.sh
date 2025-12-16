#!/bin/bash
# Setup script for AutoBlog AI Backend
# Creates Python virtual environment and installs dependencies

set -e

echo "🚀 Setting up AutoBlog AI Backend..."

# Navigate to backend directory
cd "$(dirname "$0")/backend"

# Find a compatible Python version (3.10, 3.11, or 3.12)
PYTHON_CMD=""
for cmd in python3.11 python3.12 python3.10 python3; do
    if command -v $cmd &> /dev/null; then
        VERSION=$($cmd --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1-2)
        MAJOR=$(echo $VERSION | cut -d'.' -f1)
        MINOR=$(echo $VERSION | cut -d'.' -f2)
        if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 10 ] && [ "$MINOR" -le 12 ]; then
            PYTHON_CMD=$cmd
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "❌ Error: Python 3.10, 3.11, or 3.12 is required but not found."
    echo "   Please install Python 3.11: brew install python@3.11"
    exit 1
fi

echo "📦 Using $($PYTHON_CMD --version)"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "🔧 Creating virtual environment..."
    $PYTHON_CMD -m venv venv
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Copy .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env from template..."
    cp .env.example .env
    echo "⚠️  Please update backend/.env with your GEMINI_API_KEY"
fi

echo ""
echo "✅ Backend setup complete!"
echo ""
echo "To start the backend server:"
echo "  cd backend"
echo "  source venv/bin/activate"
echo "  uvicorn app.main:app --reload"
echo ""
echo "The API will be available at: http://localhost:8000"
echo "API docs (dev mode): http://localhost:8000/docs"
