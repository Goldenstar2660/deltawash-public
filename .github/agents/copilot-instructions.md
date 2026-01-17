# DeltaWash Pi CV Development Guidelines

Auto-generated from feature plans. Last updated: January 10, 2026

## Active Technologies

### Feature 001: DeltaWash Compliance
- **Language**: Python 3.11
- **Framework**: MediaPipe Hands, OpenCV
- **Platform**: Raspberry Pi 5 (4 GB) with Pi Camera Module 3
- **Testing**: pytest
- **Storage**: Local files (YAML config, per-session logs)

### Feature 002: Hospital Dashboard
- **Backend**: Python 3.11, FastAPI 0.109+, SQLAlchemy 2.0+, Pydantic 2.x
- **Database**: PostgreSQL 16 (with materialized views for aggregates)
- **Frontend**: React 18, TypeScript 5.x, Vite 5, React Query, Recharts
- **Platform**: Docker containers (docker-compose) on localhost
- **Testing**: pytest + httpx (backend), Vitest (frontend), Playwright (smoke)
- **Authentication**: JWT Bearer tokens with server-side RBAC

## Project Structure

```text
# Feature 001: On-Device Detection (existing)
src/deltawash_pi/
├── cli/                # CLI commands for device operations
├── config/            # Configuration loader (YAML)
├── detectors/         # WHO step detectors (step2-step7)
│   ├── base.py       # Detector interface
│   ├── ml.py         # ML model integration
│   └── runner.py     # Detection pipeline
├── interpreter/       # State machine for session management
│   ├── state_machine.py
│   └── session_manager.py
├── feedback/          # ESP8266 LED driver
│   └── esp8266.py
├── logging/           # Session logging and analytics
│   ├── sessions.py   # Per-session records
│   └── aggregates.py # Compliance analytics
└── ml/               # ML models
    ├── cnn_model.pth
    ├── pose_model.pth
    └── pixel_model.pth

# Feature 002: Hospital Dashboard (new)
dashboard/
├── backend/
│   ├── src/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── config.py            # Environment config
│   │   ├── database.py          # SQLAlchemy engine
│   │   ├── dependencies.py      # FastAPI dependencies (auth, DB)
│   │   ├── models/              # SQLAlchemy ORM models
│   │   │   ├── device.py
│   │   │   ├── unit.py
│   │   │   ├── session.py
│   │   │   ├── step.py
│   │   │   ├── heartbeat.py
│   │   │   └── user.py
│   │   ├── schemas/             # Pydantic request/response DTOs
│   │   │   ├── device.py
│   │   │   ├── session.py
│   │   │   ├── analytics.py
│   │   │   └── auth.py
│   │   ├── api/                 # API route handlers
│   │   │   ├── ingestion.py    # POST /events/session, /step, /heartbeat
│   │   │   ├── analytics.py    # GET /analytics/overview, /unit, /device
│   │   │   ├── devices.py      # GET /devices
│   │   │   └── auth.py         # POST /auth/login
│   │   ├── services/            # Business logic
│   │   │   ├── analytics_service.py
│   │   │   ├── demo_data_service.py
│   │   │   └── auth_service.py
│   │   └── scripts/             # Utility scripts
│   │       ├── init_db.py      # Create schema
│   │       ├── seed_demo_data.py  # Generate synthetic data
│   │       └── create_user.py  # User management
│   ├── tests/
│   │   ├── integration/         # API integration tests
│   │   └── unit/                # Service unit tests
│   ├── alembic/                 # Database migrations
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx             # React entry point
│   │   ├── App.tsx              # Root component with routing
│   │   ├── components/          # Reusable UI components
│   │   │   ├── layout/          # Header, Sidebar, Layout
│   │   │   ├── charts/          # Recharts components
│   │   │   ├── filters/         # Date, Unit, Shift filters
│   │   │   └── common/          # MetricCard, DeviceStatusBadge
│   │   ├── pages/               # Page-level components
│   │   │   ├── OverviewPage.tsx
│   │   │   ├── UnitPage.tsx
│   │   │   ├── DevicePage.tsx
│   │   │   └── LoginPage.tsx
│   │   ├── services/            # API client (Axios)
│   │   │   ├── api.ts           # Axios instance with auth
│   │   │   ├── analyticsApi.ts
│   │   │   └── authApi.ts
│   │   ├── hooks/               # React Query hooks
│   │   │   ├── useAnalytics.ts
│   │   │   ├── useDevices.ts
│   │   │   └── useAuth.ts
│   │   ├── context/             # React Context providers
│   │   │   ├── AuthContext.tsx
│   │   │   └── FilterContext.tsx
│   │   ├── types/               # TypeScript types
│   │   └── utils/               # Utility functions
│   ├── tests/
│   │   ├── unit/                # Vitest unit tests
│   │   └── smoke/               # Playwright smoke tests
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── Dockerfile
│
└── dashboard/docker-compose.dashboard.yml  # Orchestrate db + backend + frontend

# Scripts
scripts/
├── reset-demo.sh                # Wipe DB + reseed demo data
└── start-dashboard.sh           # Start docker-compose stack

# Tests
tests/
├── integration/                 # Device integration tests
├── smoke/                       # Device smoke tests
└── unit/                        # Device unit tests
```

## Commands

### Feature 001: On-Device Detection

```bash
# Run detection pipeline
python -m deltawash_pi.cli.capture

# Run demo mode (replay recordings)
python -m deltawash_pi.cli.demo

# Test LED feedback
python -m deltawash_pi.cli.led_test

# ROI calibration
python -m deltawash_pi.cli.roi_calibrate

# Run tests
pytest tests/unit/
pytest tests/integration/
pytest tests/smoke/
```

### Feature 002: Hospital Dashboard

```bash
# Start dashboard stack (one command)
docker-compose -f dashboard/docker-compose.dashboard.yml up --build

# Reset demo data
./scripts/reset-demo.sh

# Generate custom demo data
docker-compose -f dashboard/docker-compose.dashboard.yml run --rm backend \
  python -m src.scripts.seed_demo_data --devices 25 --days 14 --seed 99

# Create dashboard user
docker-compose -f dashboard/docker-compose.dashboard.yml exec backend \
  python -m src.scripts.create_user --email user@demo.com --password demo1234 --role org_admin

# Run backend tests
docker-compose -f dashboard/docker-compose.dashboard.yml exec backend \
  pytest tests/integration/ -v

# Run frontend tests
docker-compose -f dashboard/docker-compose.dashboard.yml exec frontend \
  npm run test

# Refresh materialized views
docker-compose -f dashboard/docker-compose.dashboard.yml exec backend \
  python -m src.scripts.refresh_views

# Access database
docker-compose -f dashboard/docker-compose.dashboard.yml exec db \
  psql -U dashboard -d dashboard_db

# Stop services (keep data)
docker-compose -f dashboard/docker-compose.dashboard.yml down

# Stop services (wipe data)
docker-compose -f dashboard/docker-compose.dashboard.yml down -v
```

## Code Style

### Python (Backend & Device)

- **Style**: PEP 8 with 100 character line limit
- **Type Hints**: Required for all function signatures
- **Docstrings**: Required for public functions and classes (Google style)
- **Imports**: Sort with `isort` (stdlib → third-party → local)
- **Formatting**: Use `black` with default settings
- **Linting**: `flake8` for style violations, `mypy` for type checking

**Example**:
```python
from typing import Optional
from pydantic import BaseModel

class SessionSchema(BaseModel):
    """Session data transfer object for API responses."""
    
    device_id: str
    timestamp: str
    duration_ms: int
    compliant: bool
    
    def calculate_compliance_rate(self, total_sessions: int) -> float:
        """Calculate compliance rate as percentage.
        
        Args:
            total_sessions: Total number of sessions for comparison
            
        Returns:
            Compliance rate as percentage (0.0-100.0)
        """
        return (self.compliant / total_sessions) * 100.0
```

### TypeScript (Frontend)

- **Style**: Airbnb TypeScript style guide
- **Type Safety**: Strict mode enabled, no `any` types
- **Component Style**: Functional components with hooks (no class components)
- **Props**: Use interfaces for component props
- **Formatting**: Prettier with 2-space indentation
- **Linting**: ESLint with TypeScript rules

**Example**:
```typescript
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchAnalytics } from '../services/analyticsApi';

interface AnalyticsProps {
  dateFrom: string;
  dateTo: string;
  unitId?: string;
}

export const AnalyticsChart: React.FC<AnalyticsProps> = ({ dateFrom, dateTo, unitId }) => {
  const { data, isLoading, error } = useQuery({
    queryKey: ['analytics', dateFrom, dateTo, unitId],
    queryFn: () => fetchAnalytics({ dateFrom, dateTo, unitId }),
  });

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;
  
  return <div>{/* Render chart with data */}</div>;
};
```

### SQL (Database Migrations)

- **Style**: Lowercase keywords, uppercase table/column names
- **Naming**: Snake_case for tables and columns
- **Migrations**: Alembic for version control
- **Indexes**: Add indexes for foreign keys and filter columns
- **Materialized Views**: Use `CONCURRENTLY` for refresh

**Example**:
```sql
-- Alembic migration: create sessions table
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_ms INTEGER NOT NULL CHECK (duration_ms >= 5000 AND duration_ms <= 120000),
    compliant BOOLEAN NOT NULL,
    low_quality BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sessions_device_timestamp ON sessions(device_id, timestamp DESC);
```

## Recent Changes

### Feature 002: Hospital Dashboard (002-hospital-dashboard)
**Status**: In Planning  
**Added**:
- Web-based analytics dashboard for multi-device compliance monitoring
- Python FastAPI backend with PostgreSQL database
- React TypeScript frontend with Vite bundler
- Docker Compose configuration for local development
- Synthetic demo data generation (20+ devices, 7+ days, 500+ sessions)
- JWT authentication with RBAC (4 user roles: org_admin, analyst, unit_manager, technician)
- Three dashboard views: Overview, Unit Drilldown, Device Health
- Materialized views for <200ms p95 query performance
- Flexible filtering: date range, unit/device, shift/time-of-day, quality toggle
- HTTP event ingestion API for live device data
- One-command demo reset script

### Feature 001: DeltaWash Compliance (001-handwash-compliance)
**Status**: Implemented  
**Added**:
- WHO hand-rubbing step detection (steps 2-7) using MediaPipe Hands
- Real-time feedback via ESP8266 LED controller
- State machine-based session interpreter
- Per-session logging with config versioning
- Demo mode with recorded landmark playback
- Smoke tests for camera pipeline and LED communication
- Configuration-driven timing thresholds and completion criteria

## Constitution Alignment

**Core Principles** (from [.specify/memory/constitution.md](../../.specify/memory/constitution.md)):

1. **Spec-Driven Scope Discipline**: All code changes must reference a spec section (001-handwash-compliance or 002-hospital-dashboard)
2. **Modular Architecture**: Dashboard is separate from device detection logic; device code in `src/deltawash_pi/` remains unchanged except minimal HTTP client addition
3. **Fail-Safe Operation**: Dashboard HTTP posting fails gracefully; WiFi failures must not crash device detection
4. **Observability**: All sessions include device ID, timestamp, config version for traceability
5. **Privacy**: No video storage (default), no staff identity tracking, no cloud services
6. **Demo Readiness**: Deterministic demo mode with synthetic data; dashboard enables DeltaHacks demo with single physical device

## Dashboard-Specific Guidelines

### Data Ingestion
- Device event POSTs must validate with Pydantic schemas before DB insertion
- Heartbeat frequency: default 5 minutes (configurable per device)
- Session duration: 5-120 seconds (enforced at DB level)
- Quality flags: binary (low_quality vs normal) for MVP

### Analytics Queries
- Query materialized views (not base tables) for <200ms p95 performance
- Refresh materialized views after bulk data ingestion
- Apply filters (date range, unit, quality) as WHERE clauses on materialized views
- Use React Query for frontend data fetching (30s `staleTime` for analytics)

### Authentication
- JWT expiration: 24 hours
- Password hashing: bcrypt with 12 rounds
- Role enforcement: Server-side checks in FastAPI dependencies
- Unit managers can only access their assigned unit data

### Demo Data
- Deterministic seed (default: 42) for reproducible demos
- Realistic distributions: 15% miss rate, ±30% timing variance, 8% device downtime
- Validation: Assert totals meet minimums (500+ sessions, 20+ devices, 7+ days)

## Testing Strategy

### Device (Feature 001)
- **Unit Tests**: Detector signal logic with recorded/synthetic landmark sequences
- **Integration Tests**: State machine progression, timing accumulation, ESP8266 messaging
- **Smoke Tests**: Live camera + MediaPipe pipeline validation

### Dashboard (Feature 002)
- **Backend Integration**: API endpoints with real test DB (pytest + httpx)
- **Backend Unit**: Service logic with mock data (pytest)
- **Frontend Unit**: Utility functions (Vitest)
- **Frontend Smoke**: Critical user flows (Playwright)

**Priority**: Integration tests > Unit tests > Smoke tests (defer smoke if time-constrained)

<!-- MANUAL ADDITIONS START -->
<!-- Add project-specific notes, workarounds, or exceptions here -->
<!-- MANUAL ADDITIONS END -->

