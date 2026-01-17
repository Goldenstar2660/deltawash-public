# Hospital Dashboard - Complete Startup Guide

## Quick Start (5 Commands)

Run these commands in PowerShell from the project root directory:

```powershell
# 1. Navigate to project directory
cd "C:\Users\Derek Chen\Desktop\Derek\Projects\handwash"

# 2. Stop any existing containers and clean up
docker compose -f dashboard/docker-compose.dashboard.yml down -v --remove-orphans

# 3. Build and start all services (database, backend, frontend)
docker compose -f dashboard/docker-compose.dashboard.yml up -d --build

# 4. Wait 30 seconds for initialization (database migrations, demo data seeding)
Start-Sleep -Seconds 30

# 5. Check logs to verify everything started
docker compose -f dashboard/docker-compose.dashboard.yml logs --tail=50
```

## Access the Dashboard

Once containers are running:
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### Login Credentials
- **Email**: `admin@hospital.com`
- **Password**: `admin123`

## Troubleshooting

### If you get "database does not exist" error:

```powershell
# Stop everything and remove volumes
docker compose -f dashboard/docker-compose.dashboard.yml down -v

# Rebuild from scratch
docker compose -f dashboard/docker-compose.dashboard.yml up -d --build

# Wait for initialization
Start-Sleep -Seconds 30

# Check backend logs
docker compose -f dashboard/docker-compose.dashboard.yml logs backend
```

### If you get 403 Forbidden error:

This usually means the demo user wasn't created. Check backend logs:

```powershell
docker compose -f dashboard/docker-compose.dashboard.yml logs backend | Select-String "Creating user"
```

If you don't see "Creating user", manually create the admin user:

```powershell
docker compose -f dashboard/docker-compose.dashboard.yml exec backend python src/scripts/create_user.py --email admin@hospital.com --password admin123 --role org_admin
```

### Check if services are running:

```powershell
docker compose -f dashboard/docker-compose.dashboard.yml ps
```

You should see 3 services:
- `deltawash-dashboard-db` (healthy)
- `deltawash-dashboard-backend` (running)
- `deltawash-dashboard-frontend` (running)

### View logs for specific service:

```powershell
# Database logs
docker compose -f dashboard/docker-compose.dashboard.yml logs db

# Backend logs
docker compose -f dashboard/docker-compose.dashboard.yml logs backend

# Frontend logs
docker compose -f dashboard/docker-compose.dashboard.yml logs frontend
```

### Restart a single service:

```powershell
docker compose -f dashboard/docker-compose.dashboard.yml restart backend
```

### Access container shell:

```powershell
# Backend shell
docker compose -f dashboard/docker-compose.dashboard.yml exec backend bash

# Database shell
docker compose -f dashboard/docker-compose.dashboard.yml exec db psql -U dashboard_user -d deltawash_dashboard
```

## Complete Cleanup and Rebuild

If everything is broken, start completely fresh:

```powershell
# 1. Stop all containers
docker compose -f dashboard/docker-compose.dashboard.yml down -v --remove-orphans

# 2. Remove all dashboard images
docker images | Select-String "dashboard" | ForEach-Object { docker rmi -f ($_ -split '\s+')[2] }

# 3. Clean up Docker system
docker system prune -f

# 4. Rebuild everything
docker compose -f dashboard/docker-compose.dashboard.yml up -d --build

# 5. Wait for initialization
Start-Sleep -Seconds 45

# 6. Test the API
$loginBody = @{email="admin@hospital.com";password="admin123"} | ConvertTo-Json
$loginResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
$token = $loginResponse.access_token
Write-Host "✓ Backend is working! Token: $($token.Substring(0,20))..."
```

## Verify Data is Seeded

Check if demo data was loaded:

```powershell
# Check session count
docker compose -f dashboard/docker-compose.dashboard.yml exec db psql -U dashboard_user -d deltawash_dashboard -c "SELECT COUNT(*) FROM sessions;"

# Should show 1024 sessions
```

Expected demo data:
- **5 units**: ICU, Emergency Room, Surgery, Cardiology, Pediatrics
- **20 devices**: 4 devices per unit
- **1024 sessions**: ~7 days of data
- **6144 steps**: 6 steps per session
- **40320 heartbeats**: One every 5 minutes per device

## Test API Manually

```powershell
# Login and get token
$loginBody = @{
    email = "admin@hospital.com"
    password = "admin123"
} | ConvertTo-Json

$loginResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/login" -Method POST -ContentType "application/json" -Body $loginBody
$token = $loginResponse.access_token

# Get analytics
$headers = @{
    Authorization = "Bearer $token"
}

$analytics = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/analytics/overview?date_from=2026-01-10&date_to=2026-01-10" -Method GET -Headers $headers

# Display results
Write-Host "Average Wash Time: $($analytics.average_wash_time_ms)ms"
Write-Host "Quality Rate: $($analytics.quality_rate)%"
Write-Host "Total Devices: $($analytics.device_summary.total_devices)"
```

## Development Workflow

### For backend changes:
```powershell
# Backend has hot-reload enabled, changes auto-apply
# Just edit files in dashboard/backend/src/

# If you need to restart:
docker compose -f dashboard/docker-compose.dashboard.yml restart backend
```

### For frontend changes:
```powershell
# Frontend has hot-reload (Vite), changes auto-apply
# Just edit files in dashboard/frontend/src/

# If you need to restart:
docker compose -f dashboard/docker-compose.dashboard.yml restart frontend
```

### Run database migrations:
```powershell
docker compose -f dashboard/docker-compose.dashboard.yml exec backend alembic upgrade head
```

### Refresh materialized views:
```powershell
docker compose -f dashboard/docker-compose.dashboard.yml exec backend python src/scripts/refresh_views.py
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                       Docker Network                         │
│                                                              │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────┐  │
│  │   Frontend   │─────▶│   Backend    │─────▶│    DB    │  │
│  │  React + TS  │      │   FastAPI    │      │PostgreSQL│  │
│  │  Port 5173   │      │   Port 8000  │      │Port 5432 │  │
│  └──────────────┘      └──────────────┘      └──────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
         │                      │                      │
         │                      │                      │
         ▼                      ▼                      ▼
   User Browser          OpenAPI Docs          Persistent Data
  localhost:5173        localhost:8000/docs        Volume
```

## Environment Variables

The docker-compose file uses these defaults:
- `POSTGRES_DB`: deltawash_dashboard
- `POSTGRES_USER`: dashboard_user  
- `POSTGRES_PASSWORD`: dashboard_password
- `JWT_SECRET`: your-secret-key-change-in-production
- `CORS_ORIGINS`: http://localhost:5173,http://localhost:3000

To override, create a `.env` file in the project root.

## Next Steps

After successful startup:
1. Login at http://localhost:5173
2. Explore the compliance overview dashboard
3. Check out the API docs at http://localhost:8000/docs
4. Review the Phase 5 summary at `specs/002-hospital-dashboard/PHASE5_SUMMARY.md`



