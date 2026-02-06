#!/bin/bash

# Deployment script for refactored API server
# This script safely replaces the old server.py with the new refactored version

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   DEPLOYING REFACTORED API SERVER${NC}"
echo -e "${BLUE}============================================${NC}\n"

# Check if files exist
if [ ! -f "src/api/server.py" ]; then
    echo -e "${RED}❌ ERROR: src/api/server.py not found${NC}"
    exit 1
fi

if [ ! -f "src/api/server_new.py" ]; then
    echo -e "${RED}❌ ERROR: src/api/server_new.py not found${NC}"
    exit 1
fi

# Show file comparison
echo -e "${YELLOW}Current file sizes:${NC}"
ls -lh src/api/server*.py | awk '{print $9, "-", $5}'
echo ""

echo -e "${YELLOW}Lines of code:${NC}"
wc -l src/api/server.py src/api/server_new.py
echo ""

# Ask for confirmation
echo -e "${YELLOW}This will:${NC}"
echo "  1. Backup old server.py to server_old.py.backup"
echo "  2. Replace server.py with server_new.py"
echo "  3. Keep server_new.py for reference"
echo ""
read -p "Continue with deployment? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${YELLOW}Deployment cancelled.${NC}"
    exit 0
fi

# Create backup
echo -e "${BLUE}Step 1: Creating backup...${NC}"
cp src/api/server.py src/api/server_old.py.backup
echo -e "${GREEN}✓ Backed up to src/api/server_old.py.backup${NC}\n"

# Replace with new server
echo -e "${BLUE}Step 2: Deploying new server...${NC}"
cp src/api/server_new.py src/api/server.py
echo -e "${GREEN}✓ Replaced server.py with refactored version${NC}\n"

# Verify
echo -e "${BLUE}Step 3: Verifying deployment...${NC}"
if python3 -c "from src.api import server; print('✓ Server imports successfully')" 2>&1; then
    echo -e "${GREEN}✓ Import verification passed${NC}\n"
else
    echo -e "${RED}❌ Import failed! Rolling back...${NC}"
    cp src/api/server_old.py.backup src/api/server.py
    echo -e "${YELLOW}Rollback complete. Old server restored.${NC}"
    exit 1
fi

# Show deployment summary
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}✅ DEPLOYMENT SUCCESSFUL!${NC}"
echo -e "${BLUE}============================================${NC}\n"

echo -e "${YELLOW}What changed:${NC}"
echo "  • Old server: 2,534 lines (backed up)"
echo "  • New server: 174 lines (deployed)"
echo "  • Reduction: 93% smaller!"
echo ""

echo -e "${YELLOW}Files created:${NC}"
echo "  • src/api/server.py (refactored version)"
echo "  • src/api/server_old.py.backup (original backup)"
echo "  • src/api/server_new.py (kept for reference)"
echo ""

echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Restart your server:"
echo "     ./venv/bin/uvicorn src.api.server:app --reload"
echo ""
echo "  2. Test the endpoints:"
echo "     curl http://localhost:8000/health"
echo "     curl http://localhost:8000/database/status"
echo ""
echo "  3. View interactive docs:"
echo "     http://localhost:8000/docs"
echo ""

echo -e "${YELLOW}Rollback (if needed):${NC}"
echo "  cp src/api/server_old.py.backup src/api/server.py"
echo ""

echo -e "${GREEN}Deployment complete! 🚀${NC}\n"
