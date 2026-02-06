# ⚡ Quick Deploy Guide

## 🚀 Deploy in 3 Steps

```bash
# Step 1: Run deployment script
./deploy_refactored_server.sh

# Step 2: Restart server
./venv/bin/uvicorn src.api.server:app --reload

# Step 3: Verify
curl http://localhost:8000/health
```

---

## 📋 Pre-Deployment Checklist

- ✅ Tests passed: `./test_refactored_api.sh` shows 6/6 PASS
- ✅ Dependencies installed: `./venv/bin/pip install -r requirements.txt`
- ✅ Backup exists: Will be created automatically
- ✅ You understand the changes: Read [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)

---

## 🔄 Rollback (if needed)

```bash
# Restore old server
cp src/api/server_old.py.backup src/api/server.py

# Restart
./venv/bin/uvicorn src.api.server:app --reload
```

---

## 📚 Full Documentation

- **[REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)** - Complete project summary
- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Testing instructions
- **Interactive API Docs**: http://localhost:8000/docs

---

## ✨ What Changes

**Before:**
- 1 file: `server.py` (2,534 lines, 94KB)

**After:**
- 7 files: Modular, organized, testable
- Main file: `server.py` (174 lines, 5.8KB)
- **93% size reduction**
- **3 critical security fixes**
- **15 endpoints tested & working**

---

## 🆘 Need Help?

**Common Issues:**

1. **Import errors** → Run: `./venv/bin/pip install slowapi`
2. **Server won't start** → Check: `lsof -i :8000` (kill if needed)
3. **Tests fail** → Read: `TESTING_GUIDE.md`

**Still stuck?** Check the detailed guides in the repo root.

---

**Ready to deploy? Run: `./deploy_refactored_server.sh`** 🚀
