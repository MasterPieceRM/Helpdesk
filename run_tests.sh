#!/bin/bash
# Run all tests with coverage

set -e

echo "=========================================="
echo "Running Backend Tests"
echo "=========================================="
cd backend

# Install test dependencies
pip install -r requirements.txt -q
pip install -r requirements-test.txt -q

# Run tests with coverage
python -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html:htmlcov

echo ""
echo "=========================================="
echo "Running Worker Tests"
echo "=========================================="
cd ../worker

# Install test dependencies
pip install -r requirements.txt -q
pip install -r requirements-test.txt -q

# Run tests with coverage
python -m pytest tests/ -v --cov=. --cov-report=term-missing --cov-report=html:htmlcov --cov-config=.coveragerc

echo ""
echo "=========================================="
echo "All tests completed!"
echo "=========================================="
echo "Backend coverage report: backend/htmlcov/index.html"
echo "Worker coverage report: worker/htmlcov/index.html"
