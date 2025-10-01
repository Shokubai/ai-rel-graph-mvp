#!/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}=== Testing Project Setup ===${NC}\n"

# Test 1: Check if Docker is running
echo -n "1. Docker daemon: "
if docker info > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Docker is not running${NC}"
    exit 1
fi

# Test 2: Check if services are running
echo -n "2. Docker services: "
RUNNING=$(docker-compose ps --services --filter "status=running" | wc -l)
if [ "$RUNNING" -ge 4 ]; then
    echo -e "${GREEN}✓ ($RUNNING services running)${NC}"
else
    echo -e "${YELLOW}⚠ Only $RUNNING services running (expected 5)${NC}"
fi

# Test 3: PostgreSQL health
echo -n "3. PostgreSQL: "
if docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Not ready${NC}"
fi

# Test 4: Redis health
echo -n "4. Redis: "
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Not responding${NC}"
fi

# Test 5: Backend API health
echo -n "5. Backend API: "
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health)
if [ "$RESPONSE" = "200" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ HTTP $RESPONSE${NC}"
fi

# Test 6: Backend API docs
echo -n "6. API Docs: "
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/docs)
if [ "$RESPONSE" = "200" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ HTTP $RESPONSE${NC}"
fi

# Test 7: Frontend
echo -n "7. Frontend (Nginx): "
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80)
if [ "$RESPONSE" = "200" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ HTTP $RESPONSE${NC}"
fi

# Test 8: Database connection from backend
echo -n "8. Database connection: "
if docker-compose exec -T backend python -c "from app.core.database import engine; engine.connect()" > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Cannot connect${NC}"
fi

echo -e "\n${CYAN}=== Summary ===${NC}"
echo -e "If all tests pass, your setup is complete!"
echo -e "\nService URLs:"
echo -e "  Frontend:    ${GREEN}http://127.0.0.1${NC}"
echo -e "  Backend API: ${GREEN}http://127.0.0.1:8000${NC}"
echo -e "  API Docs:    ${GREEN}http://127.0.0.1:8000/docs${NC}"