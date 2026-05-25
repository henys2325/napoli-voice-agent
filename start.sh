#!/bin/bash
# ============================================================
# Napoli Pizzeria Voice AI Agent — Server Startup Script
# ============================================================

echo "🍕 Starting Napoli Pizzeria Voice AI Agent..."
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Please install Python 3.11+"
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt -q

# Create data directory
mkdir -p data

# Check .env
if [ ! -f .env ]; then
    echo "❌ .env file not found. Copy .env.example and fill in your credentials."
    exit 1
fi

# Start server
echo ""
echo "🚀 Starting FastAPI server on port 8000..."
echo "   Dashboard: http://localhost:8000"
echo "   API docs:  http://localhost:8000/docs"
echo "   Health:    http://localhost:8000/health"
echo ""
echo "   Press Ctrl+C to stop"
echo ""

cd backend && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
