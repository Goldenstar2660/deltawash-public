# Hospital Dashboard - Quick Start Script
# Run this to start the dashboard from scratch

Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  Hospital Dashboard - Quick Start" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan

# Navigate to project directory
$projectPath = "C:\Users\Derek Chen\Desktop\Derek\Projects\handwash"
Set-Location $projectPath
Write-Host "`n1. Navigated to: $projectPath" -ForegroundColor Yellow

# Stop existing containers
Write-Host "`n2. Stopping existing containers..." -ForegroundColor Yellow
docker compose -f dashboard/docker-compose.dashboard.yml down -v --remove-orphans 2>$null

# Start services
Write-Host "`n3. Starting services (this may take 30-60 seconds)..." -ForegroundColor Yellow
docker compose -f dashboard/docker-compose.dashboard.yml up -d --build

# Wait for initialization
Write-Host "`n4. Waiting for services to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Check service status
Write-Host "`n5. Checking service status..." -ForegroundColor Yellow
docker compose -f dashboard/docker-compose.dashboard.yml ps

# Test API
Write-Host "`n6. Testing API connection..." -ForegroundColor Yellow
try {
    $loginBody = @{
        email = "admin@hospital.com"
        password = "admin123"
    } | ConvertTo-Json
    
    $loginResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/login" `
        -Method Post `
        -Body $loginBody `
        -ContentType "application/json"
    
    $token = $loginResponse.access_token
    $headers = @{ Authorization = "Bearer $token" }
    
    $analytics = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/analytics/overview?date_from=2026-01-10&date_to=2026-01-10" `
        -Method Get `
        -Headers $headers
    
    Write-Host "`n✅ API is working!" -ForegroundColor Green
    Write-Host "   - Quality Rate: $([Math]::Round($analytics.quality_rate, 2))%" -ForegroundColor Green
    Write-Host "   - Total Devices: $($analytics.device_summary.total_devices)" -ForegroundColor Green
    Write-Host "   - Compliance Trend: $($analytics.compliance_trend.Length) days" -ForegroundColor Green
    
} catch {
    Write-Host "`n❌ API test failed: $_" -ForegroundColor Red
    Write-Host "`nCheck logs with:" -ForegroundColor Yellow
    Write-Host "  docker compose -f dashboard/docker-compose.dashboard.yml logs backend" -ForegroundColor Yellow
}

# Test Frontend
Write-Host "`n7. Testing frontend..." -ForegroundColor Yellow
try {
    $frontendTest = Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing
    Write-Host "✅ Frontend is accessible!" -ForegroundColor Green
} catch {
    Write-Host "❌ Frontend test failed: $_" -ForegroundColor Red
}

# Success message
Write-Host "`n===========================================================" -ForegroundColor Cyan
Write-Host "  🎉 Dashboard is ready!" -ForegroundColor Green
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "`n📱 Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "🔌 Backend API: http://localhost:8000" -ForegroundColor White
Write-Host "📚 API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host "`n👤 Login Credentials:" -ForegroundColor White
Write-Host "   Email: admin@hospital.com" -ForegroundColor Gray
Write-Host "   Password: admin123" -ForegroundColor Gray
Write-Host "`n===========================================================" -ForegroundColor Cyan
Write-Host "`nUseful commands:" -ForegroundColor Yellow
Write-Host "  View logs:    docker compose -f dashboard/docker-compose.dashboard.yml logs -f" -ForegroundColor Gray
Write-Host "  Stop:         docker compose -f dashboard/docker-compose.dashboard.yml down" -ForegroundColor Gray
Write-Host "  Restart:      docker compose -f dashboard/docker-compose.dashboard.yml restart" -ForegroundColor Gray
Write-Host "===========================================================" -ForegroundColor Cyan



