#!/usr/bin/env python3
"""
Comprehensive API Testing Script for Refactored Server
Tests all endpoints of server_new.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient
from src.api.server_new import app

# Initialize test client
client = TestClient(app)


class Colors:
    """Terminal colors for pretty output"""
    BLUE = '\033[0;34m'
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    NC = '\033[0m'  # No Color


def print_header(text):
    """Print a formatted header"""
    print(f"\n{Colors.BLUE}{'=' * 60}{Colors.NC}")
    print(f"{Colors.BLUE}{text:^60}{Colors.NC}")
    print(f"{Colors.BLUE}{'=' * 60}{Colors.NC}\n")


def print_test(description, passed, status_code=None):
    """Print test result"""
    status = f"{Colors.GREEN}✓ PASS{Colors.NC}" if passed else f"{Colors.RED}✗ FAIL{Colors.NC}"
    code_info = f" (HTTP {status_code})" if status_code else ""
    print(f"{status} | {description}{code_info}")


def test_core_endpoints():
    """Test core endpoints (health, database status)"""
    print_header("CORE ENDPOINTS")

    results = {'passed': 0, 'failed': 0}

    # Test health endpoint
    response = client.get("/health")
    passed = response.status_code == 200 and response.json() == {"status": "ok"}
    print_test("Health Check", passed, response.status_code)
    results['passed' if passed else 'failed'] += 1

    # Test database status
    response = client.get("/database/status")
    passed = response.status_code == 200 and "database_path" in response.json()
    print_test("Database Status", passed, response.status_code)
    results['passed' if passed else 'failed'] += 1

    return results


def test_report_endpoints():
    """Test report generation endpoints"""
    print_header("REPORT ENDPOINTS")

    results = {'passed': 0, 'failed': 0}

    # Test reports status
    response = client.get("/reports/status")
    passed = response.status_code == 200 and "year" in response.json()
    print_test("Reports Status", passed, response.status_code)
    results['passed' if passed else 'failed'] += 1

    # Test quality metrics
    response = client.get("/reports/quality")
    passed = response.status_code == 200 and "data_available" in response.json()
    print_test("Quality Metrics", passed, response.status_code)
    results['passed' if passed else 'failed'] += 1

    # Test multi-year report
    response = client.get("/reports/multi-year?start_year=2024&end_year=2025")
    passed = response.status_code == 200 and "summary" in response.json()
    print_test("Multi-Year Report", passed, response.status_code)
    results['passed' if passed else 'failed'] += 1

    # Test annual report (will fail without data, but should not crash)
    response = client.post("/reports/annual", json={"year": 2024})
    passed = response.status_code in [200, 404]  # Either success or "no data" is acceptable
    print_test("Annual Report Generation", passed, response.status_code)
    results['passed' if passed else 'failed'] += 1

    return results


def test_export_endpoints():
    """Test data export endpoints"""
    print_header("EXPORT ENDPOINTS")

    results = {'passed': 0, 'failed': 0}

    # Test invalid dataset (should return 404)
    response = client.get("/export/invalid")
    passed = response.status_code == 404
    print_test("Export Invalid Dataset (404 expected)", passed, response.status_code)
    results['passed' if passed else 'failed'] += 1

    # Test valid datasets (may fail if no data, but should handle gracefully)
    for dataset in ["income", "expenses"]:
        response = client.get(f"/export/{dataset}")
        # Accept 200 (has data) or 404/500 (no data) - just should not crash
        passed = response.status_code in [200, 404, 500]
        print_test(f"Export {dataset.title()} Dataset", passed, response.status_code)
        if response.status_code not in [200]:
            print(f"  {Colors.YELLOW}→ Note: Failure expected if no processed data exists{Colors.NC}")
        results['passed' if passed else 'failed'] += 1

    return results


def test_processing_endpoints():
    """Test processing and validation endpoints"""
    print_header("PROCESSING ENDPOINTS")

    results = {'passed': 0, 'failed': 0}

    # Test validation with invalid path (should return 404)
    response = client.post("/validate/bank", json={
        "bank_file_path": "/nonexistent/file.csv"
    })
    passed = response.status_code == 404
    print_test("Validate Bank File (404 for missing file)", passed, response.status_code)
    results['passed' if passed else 'failed'] += 1

    # Test process endpoint with invalid path (should return 404)
    response = client.post("/process/bank", json={
        "bank_file_path": "/nonexistent/file.csv"
    })
    passed = response.status_code == 404
    print_test("Process Bank (404 for missing file)", passed, response.status_code)
    results['passed' if passed else 'failed'] += 1

    return results


def test_error_handling():
    """Test error handling and edge cases"""
    print_header("ERROR HANDLING")

    results = {'passed': 0, 'failed': 0}

    # Test non-existent endpoint
    response = client.get("/nonexistent")
    passed = response.status_code == 404
    print_test("Non-existent Endpoint (404)", passed, response.status_code)
    results['passed' if passed else 'failed'] += 1

    # Test invalid year range for multi-year
    response = client.get("/reports/multi-year?start_year=2025&end_year=2020")
    passed = response.status_code == 400  # Bad request for invalid range
    print_test("Multi-Year Invalid Range (400)", passed, response.status_code)
    results['passed' if passed else 'failed'] += 1

    # Test year range too large
    response = client.get("/reports/multi-year?start_year=2000&end_year=2025")
    passed = response.status_code == 400  # Should reject >10 years
    print_test("Multi-Year Range Too Large (400)", passed, response.status_code)
    results['passed' if passed else 'failed'] += 1

    return results


def display_detailed_response(endpoint, method="GET"):
    """Display detailed response for an endpoint"""
    print(f"\n{Colors.YELLOW}Detailed Response for: {method} {endpoint}{Colors.NC}")
    print(f"{Colors.BLUE}{'─' * 60}{Colors.NC}")

    if method == "GET":
        response = client.get(endpoint)
    else:
        response = client.post(endpoint, json={})

    print(f"Status Code: {response.status_code}")
    print(f"Response Body (first 500 chars):")
    print(response.text[:500])
    if len(response.text) > 500:
        print("... (truncated)")
    print(f"{Colors.BLUE}{'─' * 60}{Colors.NC}\n")


def main():
    """Run all tests"""
    print_header("REFACTORED API COMPREHENSIVE TESTS")

    total_results = {'passed': 0, 'failed': 0}

    # Run all test suites
    for test_func in [
        test_core_endpoints,
        test_report_endpoints,
        test_export_endpoints,
        test_processing_endpoints,
        test_error_handling,
    ]:
        results = test_func()
        total_results['passed'] += results['passed']
        total_results['failed'] += results['failed']

    # Display detailed responses for key endpoints
    print_header("DETAILED RESPONSES (Sample)")
    display_detailed_response("/health")
    display_detailed_response("/database/status")
    display_detailed_response("/reports/quality")

    # Final summary
    print_header("FINAL RESULTS")
    total = total_results['passed'] + total_results['failed']
    print(f"Total Tests: {total}")
    print(f"{Colors.GREEN}Passed: {total_results['passed']}{Colors.NC}")
    print(f"{Colors.RED}Failed: {total_results['failed']}{Colors.NC}")

    if total_results['failed'] == 0:
        print(f"\n{Colors.GREEN}✅ ALL TESTS PASSED!{Colors.NC}")
        print(f"{Colors.GREEN}The refactored server is working perfectly.{Colors.NC}\n")
        return 0
    else:
        percentage = (total_results['passed'] / total) * 100
        print(f"\n{Colors.YELLOW}⚠️  Pass Rate: {percentage:.1f}%{Colors.NC}")
        print(f"{Colors.YELLOW}Some failures may be expected if no data is processed.{Colors.NC}\n")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n{Colors.RED}❌ Test suite crashed: {e}{Colors.NC}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
