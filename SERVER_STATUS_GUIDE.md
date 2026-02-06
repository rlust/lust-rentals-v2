# Server Status & Readiness Guide

## Quick Status Check

### Is the server running?
```bash
curl -s http://localhost:8000/health
```
Expected: `{"status":"ok"}`

### Start the server:
```bash
python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000 &
```

## GUI Visual Indicators

### ✅ Server Ready (What you SHOULD see):
- Open: http://localhost:8000/review
- Database Status shows: **⚠️** (yellow warning icon)
- Message: "Database tables exist but contain no data. Please process transactions."
- Upload section is visible and functional
- No 404 errors

### ❌ Server NOT Running (What you should NOT see):
- Database Status shows: **❌** (red X icon)
- Message: "Error loading database status - HTTP 404: Not Found"
- Upload fails with "Not Found" error

## How to Upload CSV

1. Refresh browser: http://localhost:8000/review
2. Verify you see **⚠️** icon (not ❌)
3. Click "Choose File" and select Park National Bank CSV
4. Click "📤 Upload File"
5. Enter tax year (2024 or 2025)
6. Click "▶️ Run Processor"

After processing, status changes from ⚠️ to ✅

## Troubleshooting

### Server stops unexpectedly:
```bash
# Start in background with nohup
nohup python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &

# Check logs
tail -f /tmp/uvicorn.log
```

### Dependencies missing:
```bash
pip install -r requirements.txt
pip install cffi cryptography
```
