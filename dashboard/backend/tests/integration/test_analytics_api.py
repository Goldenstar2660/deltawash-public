"""
Integration tests for analytics API endpoints.

Tests verify:
- Overview endpoint with various filter combinations
- Date range validation
- Shift filtering
- Unit filtering
- Quality filtering
- Error handling
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.main import app
from src.database import get_db
from src.models.unit import Unit
from src.models.device import Device
from src.models.user import User
from src.models.session import Session as HandwashSession
from src.models.step import Step
from src.services.auth_service import get_password_hash


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Get database session for test setup."""
    db = next(get_db())
    yield db
    db.close()


@pytest.fixture
def test_user(db_session: Session):
    """Create test user for authentication."""
    user = User(
        email="test@analytics.com",
        password_hash=get_password_hash("testpass123"),
        role="org_admin",
        unit_id=None
    )
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(client: TestClient, test_user):
    """Get authentication headers."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@analytics.com", "password": "testpass123"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestAnalyticsOverview:
    """Test suite for analytics overview endpoint."""

    def test_overview_basic(self, client: TestClient, auth_headers: dict):
        """Test basic overview analytics request."""
        date_to = datetime.now()
        date_from = date_to - timedelta(days=7)
        
        response = client.get(
            "/api/v1/analytics/overview",
            params={
                "date_from": date_from.strftime("%Y-%m-%d"),
                "date_to": date_to.strftime("%Y-%m-%d"),
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "compliance_trend" in data
        assert "most_missed_step" in data
        assert "average_wash_time_ms" in data
        assert "average_step_times" in data
        assert "quality_rate" in data
        assert "device_summary" in data
        
        # Verify compliance_trend structure
        if len(data["compliance_trend"]) > 0:
            trend_item = data["compliance_trend"][0]
            assert "date" in trend_item
            assert "total_sessions" in trend_item
            assert "compliant_sessions" in trend_item
            assert "compliance_rate" in trend_item

    def test_overview_with_unit_filter(self, client: TestClient, auth_headers: dict, db_session: Session):
        """Test overview with unit filtering."""
        # Get first unit from database
        unit = db_session.query(Unit).first()
        if not unit:
            pytest.skip("No units available in test database")
        
        date_to = datetime.now()
        date_from = date_to - timedelta(days=7)
        
        response = client.get(
            "/api/v1/analytics/overview",
            params={
                "date_from": date_from.strftime("%Y-%m-%d"),
                "date_to": date_to.strftime("%Y-%m-%d"),
                "unit_id": str(unit.id),
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "compliance_trend" in data

    def test_overview_with_shift_filter(self, client: TestClient, auth_headers: dict):
        """Test overview with shift filtering."""
        date_to = datetime.now()
        date_from = date_to - timedelta(days=7)
        
        for shift in ["morning", "afternoon", "night"]:
            response = client.get(
                "/api/v1/analytics/overview",
                params={
                    "date_from": date_from.strftime("%Y-%m-%d"),
                    "date_to": date_to.strftime("%Y-%m-%d"),
                    "shift": shift,
                },
                headers=auth_headers,
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "compliance_trend" in data

    def test_overview_with_quality_filter(self, client: TestClient, auth_headers: dict):
        """Test overview with low quality exclusion."""
        date_to = datetime.now()
        date_from = date_to - timedelta(days=7)
        
        # Test without quality filter
        response_all = client.get(
            "/api/v1/analytics/overview",
            params={
                "date_from": date_from.strftime("%Y-%m-%d"),
                "date_to": date_to.strftime("%Y-%m-%d"),
            },
            headers=auth_headers,
        )
        
        # Test with quality filter
        response_filtered = client.get(
            "/api/v1/analytics/overview",
            params={
                "date_from": date_from.strftime("%Y-%m-%d"),
                "date_to": date_to.strftime("%Y-%m-%d"),
                "exclude_low_quality": True,
            },
            headers=auth_headers,
        )
        
        assert response_all.status_code == 200
        assert response_filtered.status_code == 200
        
        data_all = response_all.json()
        data_filtered = response_filtered.json()
        
        # Quality rate should be higher when low quality is excluded
        if data_filtered["quality_rate"] > 0:
            assert data_filtered["quality_rate"] >= data_all["quality_rate"]

    def test_overview_combined_filters(self, client: TestClient, auth_headers: dict, db_session: Session):
        """Test overview with multiple filters combined."""
        unit = db_session.query(Unit).first()
        if not unit:
            pytest.skip("No units available in test database")
        
        date_to = datetime.now()
        date_from = date_to - timedelta(days=7)
        
        response = client.get(
            "/api/v1/analytics/overview",
            params={
                "date_from": date_from.strftime("%Y-%m-%d"),
                "date_to": date_to.strftime("%Y-%m-%d"),
                "unit_id": str(unit.id),
                "shift": "morning",
                "exclude_low_quality": True,
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "compliance_trend" in data


class TestAnalyticsValidation:
    """Test suite for analytics validation and error handling."""

    def test_missing_date_from(self, client: TestClient, auth_headers: dict):
        """Test that date_from is required."""
        response = client.get(
            "/api/v1/analytics/overview",
            params={"date_to": datetime.now().strftime("%Y-%m-%d")},
            headers=auth_headers,
        )
        
        assert response.status_code == 422  # Unprocessable Entity

    def test_missing_date_to(self, client: TestClient, auth_headers: dict):
        """Test that date_to is required."""
        response = client.get(
            "/api/v1/analytics/overview",
            params={"date_from": datetime.now().strftime("%Y-%m-%d")},
            headers=auth_headers,
        )
        
        assert response.status_code == 422  # Unprocessable Entity

    def test_date_range_too_large(self, client: TestClient, auth_headers: dict):
        """Test that date range cannot exceed 365 days."""
        date_to = datetime.now()
        date_from = date_to - timedelta(days=366)
        
        response = client.get(
            "/api/v1/analytics/overview",
            params={
                "date_from": date_from.strftime("%Y-%m-%d"),
                "date_to": date_to.strftime("%Y-%m-%d"),
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 400  # Bad Request
        assert "365" in response.json()["detail"].lower()

    def test_invalid_shift(self, client: TestClient, auth_headers: dict):
        """Test that invalid shift values are rejected."""
        date_to = datetime.now()
        date_from = date_to - timedelta(days=7)
        
        response = client.get(
            "/api/v1/analytics/overview",
            params={
                "date_from": date_from.strftime("%Y-%m-%d"),
                "date_to": date_to.strftime("%Y-%m-%d"),
                "shift": "invalid_shift",
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 422  # Unprocessable Entity

    def test_unauthorized_access(self, client: TestClient):
        """Test that authentication is required."""
        date_to = datetime.now()
        date_from = date_to - timedelta(days=7)
        
        response = client.get(
            "/api/v1/analytics/overview",
            params={
                "date_from": date_from.strftime("%Y-%m-%d"),
                "date_to": date_to.strftime("%Y-%m-%d"),
            },
        )
        
        assert response.status_code == 401  # Unauthorized


class TestUnitAnalytics:
    """Test suite for unit analytics endpoint."""

    @pytest.fixture
    def test_unit(self, db_session: Session):
        """Create test unit."""
        unit = Unit(
            unit_name="Test ICU",
            unit_code="TICU",
            hospital_id=None
        )
        db_session.add(unit)
        db_session.flush()
        db_session.refresh(unit)
        return unit

    @pytest.fixture
    def unit_manager_user(self, db_session: Session, test_unit: Unit):
        """Create unit manager user for RBAC testing."""
        user = User(
            email="manager@test.com",
            password_hash=get_password_hash("managerpass123"),
            role="unit_manager",
            unit_id=test_unit.id
        )
        db_session.add(user)
        db_session.flush()
        db_session.refresh(user)
        return user

    @pytest.fixture
    def unit_manager_headers(self, client: TestClient, unit_manager_user):
        """Get authentication headers for unit manager."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "manager@test.com", "password": "managerpass123"}
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    @pytest.fixture
    def different_unit(self, db_session: Session):
        """Create a different unit for RBAC testing."""
        unit = Unit(
            unit_name="Test ER",
            unit_code="TER",
            hospital_id=None
        )
        db_session.add(unit)
        db_session.commit()
        db_session.refresh(unit)
        return unit

    def test_unit_analytics_org_admin(self, client: TestClient, auth_headers: dict, test_unit: Unit):
        """Test that org_admin can access unit analytics."""
        date_to = datetime.now()
        date_from = date_to - timedelta(days=7)
        
        response = client.get(
            f"/api/v1/analytics/unit/{test_unit.id}",
            params={
                "date_from": date_from.strftime("%Y-%m-%d"),
                "date_to": date_to.strftime("%Y-%m-%d"),
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "metrics" in data
        assert "device_leaderboard" in data
        
        # Verify metrics structure
        metrics = data["metrics"]
        assert "unit_id" in metrics
        assert "unit_name" in metrics
        assert "unit_code" in metrics
        assert "compliance_trend" in metrics
        assert "most_missed_step" in metrics
        assert "average_wash_time_ms" in metrics
        assert "average_step_times" in metrics
        assert "quality_rate" in metrics
        
        # Verify unit info matches
        assert metrics["unit_id"] == str(test_unit.id)
        assert metrics["unit_name"] == test_unit.unit_name
        assert metrics["unit_code"] == test_unit.unit_code
        
        # Verify device_leaderboard is a list
        assert isinstance(data["device_leaderboard"], list)

    def test_unit_analytics_unit_manager_matching_unit(
        self, client: TestClient, unit_manager_headers: dict, test_unit: Unit
    ):
        """Test that unit_manager can access their assigned unit."""
        date_to = datetime.now()
        date_from = date_to - timedelta(days=7)
        
        response = client.get(
            f"/api/v1/analytics/unit/{test_unit.id}",
            params={
                "date_from": date_from.strftime("%Y-%m-%d"),
                "date_to": date_to.strftime("%Y-%m-%d"),
            },
            headers=unit_manager_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert "device_leaderboard" in data

    def test_unit_analytics_unit_manager_different_unit(
        self, client: TestClient, unit_manager_headers: dict, different_unit: Unit
    ):
        """Test that unit_manager cannot access a different unit (403 Forbidden)."""
        date_to = datetime.now()
        date_from = date_to - timedelta(days=7)
        
        response = client.get(
            f"/api/v1/analytics/unit/{different_unit.id}",
            params={
                "date_from": date_from.strftime("%Y-%m-%d"),
                "date_to": date_to.strftime("%Y-%m-%d"),
            },
            headers=unit_manager_headers,
        )
        
        assert response.status_code == 403
        assert "access denied" in response.json()["detail"].lower()

    def test_unit_analytics_invalid_unit_id(self, client: TestClient, auth_headers: dict):
        """Test that invalid unit_id returns 404."""
        date_to = datetime.now()
        date_from = date_to - timedelta(days=7)
        
        invalid_unit_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(
            f"/api/v1/analytics/unit/{invalid_unit_id}",
            params={
                "date_from": date_from.strftime("%Y-%m-%d"),
                "date_to": date_to.strftime("%Y-%m-%d"),
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 404

    def test_unit_analytics_with_filters(
        self, client: TestClient, auth_headers: dict, test_unit: Unit
    ):
        """Test unit analytics with shift and quality filters."""
        date_to = datetime.now()
        date_from = date_to - timedelta(days=7)
        
        response = client.get(
            f"/api/v1/analytics/unit/{test_unit.id}",
            params={
                "date_from": date_from.strftime("%Y-%m-%d"),
                "date_to": date_to.strftime("%Y-%m-%d"),
                "shift": "morning",
                "exclude_low_quality": True,
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert "device_leaderboard" in data


class TestDeviceAnalyticsEndpoint:
    """Tests for GET /analytics/device/{device_id} endpoint."""

    def test_device_analytics_success(
        self, client: TestClient, auth_headers: dict, test_device: Device
    ):
        """Test device analytics returns status, performance, and reliability flags."""
        date_to = datetime.now()
        date_from = date_to - timedelta(days=7)
        
        response = client.get(
            f"/api/v1/analytics/device/{test_device.id}",
            params={
                "date_from": date_from.strftime("%Y-%m-%d"),
                "date_to": date_to.strftime("%Y-%m-%d"),
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "status" in data
        assert "performance" in data
        assert "reliability_flags" in data
        
        # Check status fields
        status = data["status"]
        assert status["device_id"] == str(test_device.id)
        assert status["device_name"] == test_device.device_name
        assert "unit_id" in status
        assert "unit_name" in status
        assert "is_online" in status
        assert "last_seen" in status
        assert "heartbeats_24h" in status
        assert "expected_heartbeats_24h" in status
        assert status["expected_heartbeats_24h"] == 288  # 24 hours * 12 per hour
        assert "heartbeat_rate" in status
        assert "uptime_percentage" in status
        assert "firmware_version" in status
        assert "installation_date" in status
        
        # Check performance fields
        performance = data["performance"]
        assert "total_sessions" in performance
        assert "compliant_sessions" in performance
        assert "compliance_rate" in performance
        assert "average_wash_time_ms" in performance
        assert "low_quality_sessions" in performance
        assert "quality_rate" in performance
        assert "most_missed_step" in performance
        
        # Check reliability_flags is a list
        assert isinstance(data["reliability_flags"], list)

    def test_device_analytics_invalid_device_id(
        self, client: TestClient, auth_headers: dict
    ):
        """Test device analytics with invalid device_id returns 404."""
        date_to = datetime.now()
        date_from = date_to - timedelta(days=7)
        
        invalid_device_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(
            f"/api/v1/analytics/device/{invalid_device_id}",
            params={
                "date_from": date_from.strftime("%Y-%m-%d"),
                "date_to": date_to.strftime("%Y-%m-%d"),
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_device_analytics_invalid_date_range(
        self, client: TestClient, auth_headers: dict, test_device: Device
    ):
        """Test device analytics with date_from > date_to returns 400."""
        date_to = datetime.now()
        date_from = date_to + timedelta(days=7)  # Invalid: future date
        
        response = client.get(
            f"/api/v1/analytics/device/{test_device.id}",
            params={
                "date_from": date_from.strftime("%Y-%m-%d"),
                "date_to": date_to.strftime("%Y-%m-%d"),
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 400
        assert "date_from must be before" in response.json()["detail"].lower()

    def test_device_analytics_date_range_too_large(
        self, client: TestClient, auth_headers: dict, test_device: Device
    ):
        """Test device analytics with date range > 365 days returns 400."""
        date_to = datetime.now()
        date_from = date_to - timedelta(days=400)  # > 365 days
        
        response = client.get(
            f"/api/v1/analytics/device/{test_device.id}",
            params={
                "date_from": date_from.strftime("%Y-%m-%d"),
                "date_to": date_to.strftime("%Y-%m-%d"),
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 400
        assert "date range too large" in response.json()["detail"].lower()

    def test_device_analytics_unauthorized(
        self, client: TestClient, test_device: Device
    ):
        """Test device analytics without auth token returns 401."""
        date_to = datetime.now()
        date_from = date_to - timedelta(days=7)
        
        response = client.get(
            f"/api/v1/analytics/device/{test_device.id}",
            params={
                "date_from": date_from.strftime("%Y-%m-%d"),
                "date_to": date_to.strftime("%Y-%m-%d"),
            },
        )
        
        assert response.status_code == 401


