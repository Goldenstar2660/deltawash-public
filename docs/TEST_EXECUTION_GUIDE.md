# Test Execution Guide

## Overview
This guide explains how to run the tests for the Hospital Dashboard project.

## Current Test Status

### Test Infrastructure Issues
The integration tests have been written but currently cannot run successfully due to test database isolation issues:

1. **Database State Problem**: The tests are using the production database instead of an isolated test database, causing:
   - Duplicate key violations when test fixtures try to create users/units
   - Test data pollution between test runs
   - Tests cannot be run repeatedly without manual cleanup

2. **Root Cause**: The `conftest.py` transaction-based isolation strategy doesn't work properly because:
   - The test database shares the same PostgreSQL instance as production
   - Need a separate test database (e.g., `deltawash_dashboard_test`)
   - The current approach tries to rollback transactions, but data persists across test runs

## Tests Written (Phase 6 Implementation)

### Backend Integration Tests
Location: `dashboard/backend/tests/integration/test_analytics_api.py`

**Test Classes:**
1. `TestAnalyticsOverview` (5 tests) - Overview endpoint with various filters
2. `TestAnalyticsValidation` (5 tests) - Input validation and unauthorized access
3. `TestUnitAnalytics` (5 tests) - Unit-scoped analytics with RBAC

**Total**: 15 integration tests covering:
- GET /api/v1/analytics/overview with filters
- GET /api/v1/analytics/unit/{unit_id} with filters
- RBAC enforcement (org_admin, analyst, unit_manager)
- Input validation (date ranges, invalid parameters)
- Device leaderboard calculation

## How to Run Tests (Once Fixed)

### Backend Tests

**From outside the container:**
```powershell
cd "c:\Users\Derek Chen\Desktop\Derek\Projects\handwash"
docker compose -f dashboard/docker-compose.dashboard.yml exec backend pytest tests/integration/ -v
```

**From inside the container:**
```bash
docker compose -f dashboard/docker-compose.dashboard.yml exec backend bash
pytest tests/integration/ -v
```

**Run specific test class:**
```powershell
docker compose -f dashboard/docker-compose.dashboard.yml exec backend pytest tests/integration/test_analytics_api.py::TestUnitAnalytics -v
```

**Run single test:**
```powershell
docker compose -f dashboard/docker-compose.dashboard.yml exec backend pytest tests/integration/test_analytics_api.py::TestUnitAnalytics::test_unit_analytics_org_admin -v
```

### Frontend Tests
Frontend tests have not been created yet. To add them, you would typically:

```bash
cd dashboard/frontend
npm test
```

## Required Fixes for Tests to Run

### 1. Create Separate Test Database

Update `dashboard/docker-compose.dashboard.yml` to create a test database:

```yaml
services:
  db:
    environment:
      - POSTGRES_USER=dashboard_user
      - POSTGRES_PASSWORD=dashboard_password
      - POSTGRES_DB=deltawash_dashboard
      # Add test database initialization
```

Or create manually:
```sql
CREATE DATABASE deltawash_dashboard_test;
GRANT ALL PRIVILEGES ON DATABASE deltawash_dashboard_test TO dashboard_user;
```

### 2. Update Test Configuration

Update `dashboard/backend/tests/conftest.py`:

```python
# Use separate test database
TEST_DATABASE_URL = "postgresql://dashboard_user:dashboard_password@db:5432/deltawash_dashboard_test"
```

### 3. Clean Database Between Runs

Option A: Drop and recreate test database before each run
```python
@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    # Drop all tables
    Base.metadata.drop_all(bind=test_engine)
    # Create all tables fresh
    Base.metadata.create_all(bind=test_engine)
    yield
```

Option B: Use pytest-postgresql plugin for automatic test database management

## Test Coverage

### Implemented Tests:
- ✅ Unit analytics endpoint with RBAC
- ✅ Device leaderboard calculation
- ✅ Filter combinations (date, shift, unit, quality)
- ✅ Input validation
- ✅ Unauthorized access handling

### Not Yet Tested:
- ⏳ Frontend components (DeviceLeaderboard, UnitPage)
- ⏳ Frontend hooks (useUnitAnalytics)
- ⏳ React Router navigation
- ⏳ End-to-end user flows
- ⏳ Performance/load testing

## Test Execution Best Practices

1. **Always use the test database** - Never run tests against production
2. **Clean between runs** - Ensure tests start with clean state
3. **Run in isolation** - Use transaction rollback or database recreation
4. **Check coverage** - Aim for >80% code coverage:
   ```bash
   pytest --cov=src --cov-report=html tests/integration/
   ```

## Debugging Failed Tests

**View detailed error output:**
```powershell
docker compose -f dashboard/docker-compose.dashboard.yml exec backend pytest tests/integration/ -v --tb=long
```

**Stop on first failure:**
```powershell
docker compose -f dashboard/docker-compose.dashboard.yml exec backend pytest tests/integration/ -x
```

**Run with print statements:**
```powershell
docker compose -f dashboard/docker-compose.dashboard.yml exec backend pytest tests/integration/ -s
```

## Next Steps

1. **Fix database isolation** - Create separate test database
2. **Clean test data** - Implement proper teardown in conftest.py
3. **Run all tests** - Verify all 15 tests pass
4. **Add frontend tests** - Write tests for React components
5. **Set up CI/CD** - Automate test execution on pull requests



