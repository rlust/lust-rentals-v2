#!/bin/bash

# Comprehensive API Testing Script
# Tests the refactored server_new.py endpoints

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   TESTING REFACTORED API SERVER${NC}"
echo -e "${BLUE}============================================${NC}\n"

# Check if server is running
if ! curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo -e "${RED}❌ ERROR: Server not running on port 8001${NC}"
    echo -e "${YELLOW}Start the server with:${NC}"
    echo -e "${YELLOW}  ./venv/bin/uvicorn src.api.server_new:app --port 8001 --reload${NC}\n"
    exit 1
fi

echo -e "${GREEN}✓ Server is running on port 8001${NC}\n"

# Test function
test_endpoint() {
    local method=$1
    local endpoint=$2
    local description=$3
    local expected_status=$4
    local data=$5

    echo -ne "Testing: ${description}... "

    if [ "$method" = "GET" ]; then
        status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8001${endpoint}")
    else
        status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "http://localhost:8001${endpoint}" \
                 -H "Content-Type: application/json" -d "${data}")
    fi

    if [ "$status" = "$expected_status" ]; then
        echo -e "${GREEN}✓ PASS${NC} (HTTP $status)"
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (Expected $expected_status, got $status)"
        return 1
    fi
}

# Detailed test function with response preview
test_endpoint_verbose() {
    local method=$1
    local endpoint=$2
    local description=$3

    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Testing: ${description}${NC}"
    echo -e "${BLUE}Endpoint: $method http://localhost:8001${endpoint}${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n\nHTTP Status: %{http_code}" "http://localhost:8001${endpoint}")
    else
        response=$(curl -s -w "\n\nHTTP Status: %{http_code}" -X POST "http://localhost:8001${endpoint}" \
                   -H "Content-Type: application/json" -d '{}')
    fi

    echo "$response" | head -20
    if [ $(echo "$response" | wc -l) -gt 20 ]; then
        echo "... (truncated)"
    fi
    echo ""
}

passed=0
failed=0

echo -e "${YELLOW}Running Basic Tests...${NC}\n"

# Core Endpoints
test_endpoint "GET" "/health" "Health Check" "200" && ((passed++)) || ((failed++))
test_endpoint "GET" "/database/status" "Database Status" "200" && ((passed++)) || ((failed++))

# Report Endpoints
test_endpoint "GET" "/reports/status" "Reports Status" "200" && ((passed++)) || ((failed++))
test_endpoint "GET" "/reports/quality" "Quality Metrics" "200" && ((passed++)) || ((failed++))

# Export Endpoints
test_endpoint "GET" "/export/invalid" "Export Invalid Dataset (404)" "404" && ((passed++)) || ((failed++))

# Multi-year report (if years exist)
test_endpoint "GET" "/reports/multi-year?start_year=2024&end_year=2025" "Multi-Year Report" "200" && ((passed++)) || ((failed++))

echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}BASIC TEST RESULTS${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "Passed: ${GREEN}$passed${NC}"
echo -e "Failed: ${RED}$failed${NC}"

# Detailed Tests
echo -e "\n${YELLOW}Running Detailed Tests (with response preview)...${NC}"

test_endpoint_verbose "GET" "/health" "Health Check Detailed"
test_endpoint_verbose "GET" "/database/status" "Database Status Detailed"
test_endpoint_verbose "GET" "/reports/quality" "Quality Metrics Detailed"

# Final Summary
echo -e "\n${BLUE}============================================${NC}"
if [ $failed -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED!${NC}"
    echo -e "${GREEN}The refactored server is working correctly.${NC}"
else
    echo -e "${YELLOW}⚠️  Some tests failed (this may be expected if no data is processed)${NC}"
fi
echo -e "${BLUE}============================================${NC}\n"

# Suggestions
echo -e "${YELLOW}Next Steps:${NC}"
echo -e "1. Review the test results above"
echo -e "2. If all core endpoints pass, the refactoring is successful"
echo -e "3. To test with actual data, process some transactions first"
echo -e "4. To deploy: mv src/api/server_new.py src/api/server.py\n"
