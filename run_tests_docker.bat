# Optimized Docker Test Runner (Windows)
# Uses BuildKit for faster builds with layer caching

# Enable Docker BuildKit for performance
$env:DOCKER_BUILDKIT=1

Write-Host "Building optimized test image (with layer caching)..." -ForegroundColor Cyan
docker build -f tests/Dockerfile.test -t sovereign-test .

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker build failed!" -ForegroundColor Red
    exit 1
}

Write-Host "`nRunning tests..." -ForegroundColor Cyan
docker run --rm -v "${PWD}:/app" --network host sovereign-test pytest tests/ -v

Write-Host "`nTests complete!" -ForegroundColor Green
