#!/bin/bash
# =============================================================================
# AutoBlog AI - Raspberry Pi Deployment Script
# =============================================================================
# 
# This script sets up and deploys AutoBlog AI on a Raspberry Pi.
# Run this on your Raspberry Pi after cloning the repository.
#
# Usage:
#   chmod +x deploy-pi.sh
#   ./deploy-pi.sh
#
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           AutoBlog AI - Raspberry Pi Deployment           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# -----------------------------------------------------------------------------
# Step 1: Check if Docker is installed
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[1/5] Checking Docker installation...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker not found. Installing Docker...${NC}"
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo -e "${GREEN}Docker installed! Please log out and log back in, then run this script again.${NC}"
    exit 0
else
    echo -e "${GREEN}✓ Docker is installed: $(docker --version)${NC}"
fi

# Check if docker compose is available
if ! docker compose version &> /dev/null; then
    echo -e "${RED}Docker Compose not found. Installing...${NC}"
    sudo apt-get update
    sudo apt-get install -y docker-compose-plugin
fi
echo -e "${GREEN}✓ Docker Compose is available${NC}"

# -----------------------------------------------------------------------------
# Step 2: Navigate to backend directory
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[2/5] Setting up project directory...${NC}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/backend"

echo -e "${GREEN}✓ Working directory: $(pwd)${NC}"

# -----------------------------------------------------------------------------
# Step 3: Check/Create .env file
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[3/5] Checking environment configuration...${NC}"

if [ ! -f ".env" ]; then
    echo -e "${RED}.env file not found!${NC}"
    echo -e "${YELLOW}Creating .env from template...${NC}"
    cp .env.example .env
    echo ""
    echo -e "${RED}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  IMPORTANT: Edit .env file before continuing!             ║${NC}"
    echo -e "${RED}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Required settings:"
    echo "  - GEMINI_API_KEY=your-api-key"
    echo "  - EMAIL_ADDRESS=your-bot@gmail.com"
    echo "  - EMAIL_PASSWORD=your-app-password"
    echo "  - EMAIL_ALLOWED_SENDERS=your-email@gmail.com"
    echo ""
    echo "Edit with: nano .env"
    echo "Then run this script again."
    exit 1
else
    echo -e "${GREEN}✓ .env file exists${NC}"
    
    # Validate required keys
    if ! grep -q "GEMINI_API_KEY=." .env || grep -q "GEMINI_API_KEY=your-gemini" .env; then
        echo -e "${RED}⚠ GEMINI_API_KEY not configured in .env${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ GEMINI_API_KEY is set${NC}"
fi

# -----------------------------------------------------------------------------
# Step 4: Build Docker image
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[4/5] Building Docker image (this may take 5-10 minutes on Pi)...${NC}"

docker compose build --no-cache

echo -e "${GREEN}✓ Docker image built successfully${NC}"

# -----------------------------------------------------------------------------
# Step 5: Start the container
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[5/5] Starting AutoBlog AI...${NC}"

# Stop existing container if running
docker compose down 2>/dev/null || true

# Start new container
docker compose up -d

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           AutoBlog AI is now running! 🚀                  ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Service URL:     ${BLUE}http://$(hostname -I | awk '{print $1}'):8000${NC}"
echo -e "Health Check:    ${BLUE}http://$(hostname -I | awk '{print $1}'):8000/health${NC}"
echo -e "API Docs:        ${BLUE}http://$(hostname -I | awk '{print $1}'):8000/docs${NC}"
echo ""
echo "Useful commands:"
echo "  View logs:      docker compose logs -f"
echo "  Stop:           docker compose down"
echo "  Restart:        docker compose restart"
echo "  Status:         docker compose ps"
echo ""
echo -e "${YELLOW}Start email pipeline:${NC}"
echo "  curl -X POST http://localhost:8000/api/email-pipeline/start"
echo ""
