# 🧪 Testing Guide for Refactored API Server

This guide shows you how to test the refactored `server_new.py` to ensure it works correctly before deploying.

---

## Quick Start (30 seconds)

```bash
# 1. Start the test server
./venv/bin/uvicorn src.api.server_new:app --host 0.0.0.0 --port 8001 --reload

# 2. In a new terminal, run the test script
./test_refactored_api.sh
```

---

## Method 1: Automated Test Script (Recommended)

### Using Bash Script

```bash
# Make script executable (if not already)
chmod +x test_refactored_api.sh

# Start server on port 8001
./venv/bin/uvicorn src.api.server_new:app --port 8001 --reload &

# Wait a moment for server to start
sleep 3

# Run tests
./test_refactored_api.sh
```

**Expected Output:**
```
============================================
   TESTING REFACTORED API SERVER
============================================

✓ Server is running on port 8001

Running Basic Tests...

✓ PASS | Health Check (HTTP 200)
✓ PASS | Database Status (HTTP 200)
✓ PASS | Reports Status (HTTP 200)
✓ PASS | Quality Metrics (HTTP 200)
✓ PASS | Export Invalid Dataset (404) (HTTP 404)
✓ PASS | Multi-Year Report (HTTP 200)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BASIC TEST RESULTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Passed: 6
Failed: 0

✅ ALL TESTS PASSED!
```

---

## Method 2: Manual Testing with curl

### Start the Server
```bash
# Terminal 1: Start server
./venv/bin/uvicorn src.api.server_new:app --host 0.0.0.0 --port 8001 --reload
```

### Test Endpoints
```bash
# Terminal 2: Run curl commands

# 1. Health Check
curl http://localhost:8001/health
# Expected: {"status":"ok"}

# 2. Database Status (pretty printed)
curl -s http://localhost:8001/database/status | python3 -m json.tool | head -30

# 3. Reports Status
curl -s http://localhost:8001/reports/status | python3 -m json.tool | head -20

# 4. Quality Metrics
curl -s http://localhost:8001/reports/quality | python3 -m json.tool

# 5. Multi-Year Report
curl -s "http://localhost:8001/reports/multi-year?start_year=2024&end_year=2025" | python3 -m json.tool

# 6. Test 404 Handling
curl -s http://localhost:8001/export/invalid
# Expected: {"detail":"Dataset not found."}

# 7. Test File Validation (should return 404 for missing file)
curl -X POST http://localhost:8001/validate/bank \
  -H "Content-Type: application/json" \
  -d '{"bank_file_path":"/nonexistent/file.csv"}'
```

---

## Method 3: Interactive API Documentation

FastAPI provides automatic interactive documentation!

### Swagger UI
1. Start the server: `./venv/bin/uvicorn src.api.server_new:app --port 8001 --reload`
2. Open browser: http://localhost:8001/docs
3. Test any endpoint interactively with the "Try it out" button

### ReDoc
Alternative documentation interface:
- Open browser: http://localhost:8001/redoc

---

## Method 4: Compare with Old Server

Test that both servers return the same results:

```bash
# Terminal 1: Start old server on port 8000
./venv/bin/uvicorn src.api.server:app --port 8000

# Terminal 2: Start new server on port 8001
./venv/bin/uvicorn src.api.server_new:app --port 8001

# Terminal 3: Compare outputs
echo "=== OLD SERVER ==="
curl -s http://localhost:8000/health

echo "=== NEW SERVER ==="
curl -s http://localhost:8001/health

echo "=== OLD DATABASE STATUS ==="
curl -s http://localhost:8000/database/status | python3 -m json.tool | head -20

echo "=== NEW DATABASE STATUS ==="
curl -s http://localhost:8001/database/status | python3 -m json.tool | head -20
```

---

## What to Look For

### ✅ Success Indicators
- All core endpoints return HTTP 200
- Health check returns `{"status":"ok"}`
- Database status includes `database_path` and `exists` fields
- Reports status includes `year` and `artifacts` fields
- Invalid requests return appropriate 404/400 errors
- No server crashes or exceptions

### ⚠️ Expected "Failures"
These are NOT bugs - they're expected when no data is processed:

- **Export endpoints (500 error)**: `GET /export/income` or `/export/expenses`
  - Reason: No database tables exist yet
  - Fix: Process some transactions first

- **Report generation (404 error)**: `POST /reports/annual`
  - Reason: No processed data available
  - Fix: Upload and process bank transactions

---

## Testing with Real Data

To fully test the server with your actual data:

```bash
# 1. Start the new server
./venv/bin/uvicorn src.api.server_new:app --port 8001 --reload

# 2. Upload a CSV file
curl -X POST http://localhost:8001/upload/bank-file \
  -F "file=@data/raw/transaction_report-3.csv"

# 3. Process the file
curl -X POST http://localhost:8001/process/bank \
  -H "Content-Type: application/json" \
  -d '{"year": 2024}'

# 4. Generate reports
curl -X POST http://localhost:8001/reports/annual \
  -H "Content-Type: application/json" \
  -d '{"year": 2024, "save_outputs": true}'

# 5. Export data
curl http://localhost:8001/export/income > income.csv
curl http://localhost:8001/export/expenses > expenses.csv
```

---

## Troubleshooting

### Server won't start
```bash
# Check if port is already in use
lsof -i :8001

# Kill existing process if needed
kill -9 <PID>

# Try a different port
./venv/bin/uvicorn src.api.server_new:app --port 8002
```

### Import errors
```bash
# Make sure slowapi is installed
./venv/bin/pip install slowapi>=0.1.9

# Reinstall all dependencies
./venv/bin/pip install -r requirements.txt
```

### Tests fail
- Check server logs for detailed error messages
- Verify database exists: `ls data/processed/processed.db`
- Ensure you're testing the right port (8001 for new server)

---

## Deployment Checklist

Before replacing the old server with the new one:

- [ ] All core endpoints return HTTP 200
- [ ] Health check works
- [ ] Database status endpoint works
- [ ] Can upload files successfully
- [ ] Can process transactions successfully
- [ ] Can generate reports successfully
- [ ] Error handling works (404s, 400s)
- [ ] No unexpected crashes or exceptions

Once all checks pass:
```bash
# Backup old server
mv src/api/server.py src/api/server_old.py.backup

# Deploy new server
mv src/api/server_new.py src/api/server.py

# Restart on main port
./venv/bin/uvicorn src.api.server:app --reload
```

---

## Quick Reference

| What | Command |
|------|---------|
| Start test server | `./venv/bin/uvicorn src.api.server_new:app --port 8001 --reload` |
| Run automated tests | `./test_refactored_api.sh` |
| Health check | `curl http://localhost:8001/health` |
| API docs | http://localhost:8001/docs |
| Stop server | `Ctrl+C` or `pkill -f "uvicorn.*8001"` |

---

**✨ Pro Tip:** Use the interactive docs at http://localhost:8001/docs to explore and test all endpoints visually!
