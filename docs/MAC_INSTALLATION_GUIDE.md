# Mac Installation Guide - Lust Rentals Tax Reporting System

This guide will walk you through installing and running the Lust Rentals Tax Reporting application on macOS.

## Quick Command Reference

Copy and paste these commands in your Mac Terminal to get up and running quickly:

```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.11
brew install python@3.11

# Install Git (if needed)
brew install git

# Verify Python installation
python3 --version

# Clone the repository (replace with actual repository URL)
cd ~/Documents
git clone https://github.com/rlust/lust-rentals-tax-reporting.git
cd lust-rentals-tax-reporting

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Set up data directories
export LUST_DATA_DIR="$(pwd)/data"
mkdir -p "$LUST_DATA_DIR/raw"
mkdir -p "$LUST_DATA_DIR/processed"
mkdir -p "$LUST_DATA_DIR/overrides"
mkdir -p "$LUST_DATA_DIR/reports"

# Create environment configuration (optional)
cat > .env << 'EOF'
LUST_DATA_DIR=./data
LUST_LOG_LEVEL=INFO
EOF

# Run tests to verify installation
pytest

# Start the web application
python3 -m uvicorn src.api.server:app --reload

# Open browser to: http://localhost:8000/review
```

**That's it!** Your application should now be running. Continue reading below for detailed explanations of each step.

---

## Prerequisites

### 1. Install Homebrew (if not already installed)

Homebrew is the package manager for macOS. Open Terminal and run:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2. Install Python 3

This application requires Python 3.8 or higher. Install it using Homebrew:

```bash
brew install python@3.11
```

Verify the installation:

```bash
python3 --version
```

You should see something like `Python 3.11.x` or higher.

### 3. Install Git (if not already installed)

```bash
brew install git
```

## Installation Steps

### Step 1: Clone the Repository

Open Terminal and navigate to where you want to install the application:

```bash
cd ~/Documents  # or your preferred location
git clone <repository-url>
cd lust-rentals-tax-reporting
```

> **Note:** Replace `<repository-url>` with the actual GitHub repository URL.

### Step 2: Create a Python Virtual Environment

A virtual environment keeps the project dependencies isolated from your system Python:

```bash
python3 -m venv venv
```

### Step 3: Activate the Virtual Environment

```bash
source venv/bin/activate
```

You should see `(venv)` appear at the beginning of your terminal prompt, indicating the virtual environment is active.

### Step 4: Install Dependencies

Install all required Python packages:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This will install all necessary packages including FastAPI, pandas, matplotlib, and others.

### Step 5: Set Up Data Directories

Create the required data directories:

```bash
export LUST_DATA_DIR="$(pwd)/data"
mkdir -p "$LUST_DATA_DIR/raw"
mkdir -p "$LUST_DATA_DIR/processed"
mkdir -p "$LUST_DATA_DIR/overrides"
mkdir -p "$LUST_DATA_DIR/reports"
```

### Step 6: (Optional) Create Environment Configuration

Create a `.env` file for configuration:

```bash
cat > .env << 'EOF'
LUST_DATA_DIR=./data
LUST_LOG_LEVEL=INFO
EOF
```

## Running the Application

### Option 1: Using the Web Interface (Recommended)

1. **Start the FastAPI server:**

   ```bash
   python3 -m uvicorn src.api.server:app --reload
   ```

   You should see output like:
   ```
   INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
   INFO:     Started reloader process
   ```

2. **Access the web interface:**

   Open your web browser and navigate to:
   ```
   http://localhost:8000/review
   ```

   This will open the review dashboard where you can:
   - Process bank data
   - Generate reports
   - Review and override classifications
   - Download processed datasets

3. **Stop the server:**

   Press `CTRL+C` in the terminal where the server is running.

### Option 2: Using the Command Line Interface

The application also provides CLI commands for processing data and generating reports.

#### Process Bank Transactions

```bash
python -m src.cli.app process-bank --year 2025
```

#### Generate Tax Reports

```bash
python -m src.cli.app generate-reports --year 2025
```

## Preparing Your Data

### 1. Bank Transaction Data

Place your Park National Bank transaction report in the `data/raw/` directory:

```bash
cp ~/Downloads/transaction_report-3.csv ./data/raw/
```

### 2. Deposit Mapping File

If you have a deposit mapping file, place it in `data/raw/`:

```bash
cp ~/Downloads/deposit_amount_map.csv ./data/raw/
```

## Testing the Installation

Run the test suite to verify everything is working correctly:

```bash
pytest
```

All tests should pass. If you see any failures, ensure all dependencies were installed correctly.

## Quick Start Workflow

Here's a typical workflow to process your tax data:

1. **Activate the virtual environment** (if not already active):
   ```bash
   source venv/bin/activate
   ```

2. **Place your data files** in `data/raw/`

3. **Start the web server**:
   ```bash
   python3 -m uvicorn src.api.server:app --reload
   ```

4. **Open the browser** to `http://localhost:8000/review`

5. **Use the Pipeline & Reports controls** to:
   - Process bank data
   - Review income/expense classifications
   - Make manual overrides as needed
   - Generate annual summary PDF and Schedule E CSV
   - Download reports

## Alternative: Using Docker

If you prefer to use Docker instead of installing Python locally:

### 1. Install Docker Desktop for Mac

Download and install from: https://www.docker.com/products/docker-desktop/

### 2. Build the Docker Image

```bash
docker build -t lust-rentals-tax-reporting .
```

### 3. Run the Application

```bash
docker run \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e LUST_LOG_LEVEL=INFO \
  lust-rentals-tax-reporting
```

### 4. Access the Application

Open your browser to `http://localhost:8000/review`

## Troubleshooting

### Virtual Environment Issues

If you get "command not found" errors after activating the virtual environment:

```bash
deactivate
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Permission Errors

If you encounter permission errors with data directories:

```bash
chmod -R 755 data/
```

### Port Already in Use

If port 8000 is already in use, you can specify a different port:

```bash
python3 -m uvicorn src.api.server:app --reload --port 8001
```

Then access the app at `http://localhost:8001/review`

### Python Version Issues

Ensure you're using Python 3.8 or higher:

```bash
python3 --version
```

If your version is too old, install a newer version:

```bash
brew install python@3.11
```

## Common Terminal Commands for Daily Use

Here are the commands you'll use regularly when working with the application:

### Starting Your Work Session

```bash
# Navigate to the project directory
cd ~/Documents/lust-rentals-tax-reporting

# Activate the virtual environment
source venv/bin/activate

# Start the web server
python3 -m uvicorn src.api.server:app --reload
```

### Processing Data via CLI

```bash
# Make sure virtual environment is active first
source venv/bin/activate

# Process bank transactions for specific year
python -m src.cli.app process-bank --year 2025

# Generate tax reports
python -m src.cli.app generate-reports --year 2025

# Run tests
pytest
```

### Managing Data Files

```bash
# Copy bank transaction file to raw data folder
cp ~/Downloads/transaction_report-3.csv ./data/raw/

# Copy deposit mapping file
cp ~/Downloads/deposit_amount_map.csv ./data/raw/

# View processed files
ls -lh data/processed/

# View generated reports
ls -lh data/reports/
```

### Updating the Application

```bash
# Pull latest changes from git
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Update dependencies
pip install --upgrade -r requirements.txt

# Run tests to verify everything works
pytest
```

### Ending Your Work Session

```bash
# Stop the web server (if running)
# Press CTRL+C in the terminal where the server is running

# Deactivate virtual environment
deactivate
```

## Next Steps

After installation:

1. Review the main [README.md](../README.md) for detailed usage instructions
2. Place your bank transaction files in `data/raw/`
3. Start the web server and begin processing your data
4. Generate your tax reports

## Getting Help

- Check the main README.md for detailed documentation
- Review the test files in `tests/` for usage examples
- Check the API documentation at `http://localhost:8000/docs` when the server is running

## Deactivating the Virtual Environment

When you're done working with the application:

```bash
deactivate
```

This returns you to your system's default Python environment.
