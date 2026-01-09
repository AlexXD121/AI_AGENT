#!/bin/bash
# Docker-based test runner for Sovereign-Doc
# Runs tests in Python 3.12 environment to avoid Python 3.14 compatibility issues

set -e

echo "=========================================="
echo "Sovereign-Doc Docker Test Runner"
echo "=========================================="
echo ""

# Build the test image
echo "Building test image with Python 3.12..."
docker build -f tests/Dockerfile.test -t sovereign-test .

echo ""
echo "Running tests in Docker container..."
echo ""

# Run tests with volume mount and network access
# --rm: Remove container after exit
# -v: Mount current directory to /app
# --network host: Allow container to access host network (for Qdrant)
docker run --rm \
    -v "$(pwd):/app" \
    --network host \
    sovereign-test \
    pytest tests/ -v --tb=short

echo ""
echo "=========================================="
echo "Tests completed successfully!"
echo "=========================================="
