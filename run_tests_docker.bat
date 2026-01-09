@echo off
REM Docker-based test runner for Sovereign-Doc (Windows)
REM Runs tests in Python 3.12 environment to avoid Python 3.14 compatibility issues

echo ==========================================
echo Sovereign-Doc Docker Test Runner
echo ==========================================
echo.

REM Build the test image
echo Building test image with Python 3.12...
docker build -f tests/Dockerfile.test -t sovereign-test .

echo.
echo Running tests in Docker container...
echo.

REM Run tests with volume mount and network access
REM --rm: Remove container after exit
REM -v: Mount current directory to /app
REM --network host: Allow container to access host network (for Qdrant)
docker run --rm -v "%cd%:/app" --network host sovereign-test pytest tests/ -v --tb=short

echo.
echo ==========================================
echo Tests completed successfully!
echo ==========================================
