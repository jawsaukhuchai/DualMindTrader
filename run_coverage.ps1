# run_coverage.ps1
Write-Host "Cleaning old coverage..."
coverage erase

Write-Host "Running pytest with coverage..."
pytest

Write-Host "Generating HTML coverage report..."
coverage html

Write-Host "✅ Coverage HTML report created at htmlcov/index.html"
Start-Process "htmlcov\index.html"
