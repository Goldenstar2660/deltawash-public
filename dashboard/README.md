# Hospital Handwashing Compliance Dashboard

## 🎯 Purpose

Real-time analytics dashboard for monitoring handwashing compliance across hospital units and devices. This system tracks WHO's 7-step handwashing protocol compliance, providing actionable insights for hospital administrators to improve hygiene practices and reduce hospital-acquired infections.

## ✨ Key Features

### 📊 Real-time Analytics
- Daily compliance trend visualization
- Average wash time and quality rate metrics
- Device online/offline status monitoring
- Step completion analysis

### 🏥 Multi-level Views
- **Overview Page** - Organization-wide compliance summary
- **Unit Page** - Department-specific analytics with device leaderboards
- **Device Page** - Individual device performance and reliability flags

### 📈 Interactive Filters
- Date range selection (last 7 days by default)
- Unit filtering
- Shift filtering (morning/afternoon/night)
- Quality session filtering

### 🎯 WHO 7-Step Protocol Tracking

The system monitors compliance with WHO's recommended handwashing steps:
1. **Step 2**: Palm to palm
2. **Step 3**: Right palm over left dorsum and vice versa
3. **Step 4**: Palm to palm with fingers interlaced
4. **Step 5**: Backs of fingers to opposing palms with fingers interlocked
5. **Step 6**: Rotational rubbing of thumbs
6. **Step 7**: Rotational rubbing of fingertips

## 🚀 Quick Start

### Access the Dashboard

**Frontend (Dashboard UI):**
```
http://172.20.10.3:5173
```

**Backend API:**
```
http://172.20.10.3:8000
```

**API Documentation:**
```
http://172.20.10.3:8000/docs
```

### Start the Stack

```bash
docker compose -f dashboard/docker-compose.dashboard.yml up -d
```

### Stop the Stack

```bash
docker compose -f dashboard/docker-compose.dashboard.yml down
```

### View Logs

```bash
# All services
docker compose -f dashboard/docker-compose.dashboard.yml logs -f

# Specific service
docker logs deltawash-dashboard-frontend -f
docker logs deltawash-dashboard-backend -f
docker logs deltawash-dashboard-db -f
```

## 💾 Data Overview

The dashboard displays data from:
- **1024 handwashing sessions** across multiple units
- **5 hospital units**: Emergency Room, ICU, Surgery Department, Pediatrics Ward, Cardiology Unit
- **Multiple devices** per unit tracking compliance in real-time

## 🏗️ Technology Stack

### Frontend
- **React** with TypeScript
- **Vite** for fast development
- **React Router** for navigation
- **TanStack Query** for data fetching
- **Recharts** for data visualization
- **Axios** for API communication

### Backend
- **FastAPI** (Python) for REST API
- **PostgreSQL** for data storage
- **SQLAlchemy** for ORM
- **Pydantic** for data validation
- **Uvicorn** for ASGI server

### Infrastructure
- **Docker Compose** for containerized deployment
- **Alembic** for database migrations

## 📊 Key Metrics Explained

- **Compliance Rate**: Percentage of sessions where all 7 WHO steps were completed
- **Quality Rate**: Percentage of sessions that meet minimum duration and quality thresholds
- **Average Wash Time**: Mean duration of handwashing sessions
- **Most Missed Step**: The WHO step with the highest skip/incomplete rate
- **Device Uptime**: Percentage of time devices are online and functioning

## 🎪 Demo Configuration

This is configured for **hackathon demo mode**:
- ✅ Authentication disabled for easy access
- ✅ CORS open to all origins
- ✅ Pre-seeded with realistic hospital data
- ✅ Network access enabled for cross-device viewing

## 🔌 API Endpoints

The REST API is available at `http://172.20.10.3:8000/api/v1/`

### Analytics
- `GET /analytics/overview` - Organization-wide analytics
- `GET /analytics/unit/{unit_id}` - Unit-specific analytics
- `GET /analytics/device/{device_id}` - Device-level analytics

### Resources
- `GET /units` - List all units
- `GET /devices` - List all devices
- `GET /devices/{device_id}` - Device details

### System
- `GET /health` - Health check endpoint
- `GET /docs` - Interactive API documentation (Swagger UI)

## 🛠️ Development

### Directory Structure
- `backend/` - FastAPI backend application
  - `src/` - Source code
  - `alembic/` - Database migrations
  - `tests/` - Backend tests
- `frontend/` - React frontend application
  - `src/` - Source code
  - `public/` - Static assets

### Environment Variables

**Frontend** (`.env` in `frontend/` directory):
```bash
VITE_API_BASE_URL=http://172.20.10.3:8000
```

**Backend** (set in `dashboard/docker-compose.dashboard.yml`):
```bash
DATABASE_URL=postgresql://user:password@db:5432/deltawash_dashboard
CORS_ORIGINS=*  # Allow all origins for demo
```

## 🐛 Troubleshooting

### Dashboard shows "No Data"
1. Check backend logs: `docker logs deltawash-dashboard-backend`
2. Verify database is healthy: `docker ps | grep deltawash-dashboard-db`
3. Ensure backend initialization completed

### API returns 403 Forbidden
- Authentication has been disabled for demo
- If you see 403 errors, restart the backend: `docker compose -f dashboard/docker-compose.dashboard.yml restart backend`

### Frontend shows network errors
1. Check API URL in browser console
2. Verify backend is accessible: `curl http://172.20.10.3:8000/health`
3. Hard refresh browser: `Ctrl+Shift+R` (or `Cmd+Shift+R` on Mac)

### IP Address Changed
If the Pi's IP changes:
1. Get new IP: `hostname -I`
2. Update `.env` file with new IP
3. Restart containers: `docker compose -f dashboard/docker-compose.dashboard.yml restart`

## 📝 License

Part of the DeltaWash Compliance System project.

---

**Built for hackathon demonstration** | Last updated: January 10, 2026



