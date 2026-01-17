"""
Integration tests for device endpoints.

Tests GET /devices and GET /devices/{device_id} endpoints.
"""
import pytest
from datetime import datetime, timedelta, date
from fastapi.testclient import TestClient

from ...main import app
from ...database import get_db, SessionLocal
from ...models.device import Device
from ...models.unit import Unit
from ...models.heartbeat import Heartbeat
from ...models.session import Session as SessionModel
from ...models.user import User
from ...services.auth_service import get_password_hash


client = TestClient(app)


@pytest.fixture
def db():
    """Database session fixture."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def auth_token(db):
    """Create test user and return JWT token."""
    # Create test user
    test_user = User(
        email="test@hospital.com",
        password_hash=get_password_hash("testpass123"),
        role="analyst",
        unit_id=None
    )
    db.add(test_user)
    db.commit()
    
    # Login to get token
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@hospital.com", "password": "testpass123"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    
    yield token
    
    # Cleanup
    db.delete(test_user)
    db.commit()


@pytest.fixture
def test_device_with_heartbeats(db):
    """Create test device with heartbeats."""
    # Create unit
    unit = Unit(
        unit_name="Test ICU",
        unit_code="TICU",
        hospital_id="test-hospital-001"
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)
    
    # Create device
    device = Device(
        unit_id=unit.id,
        device_name="Test-Device-01",
        firmware_version="v2.0.0",
        installation_date=date(2026, 1, 10)
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    
    # Create recent heartbeat (online)
    recent_heartbeat = Heartbeat(
        device_id=device.id,
        timestamp=datetime.utcnow() - timedelta(minutes=10),
        firmware_version="v2.0.0",
        online_status=True
    )
    db.add(recent_heartbeat)
    
    # Create some sessions
    for i in range(5):
        session = SessionModel(
            device_id=device.id,
            timestamp=datetime.utcnow() - timedelta(hours=i),
            duration_ms=42000,
            compliant=True,
            low_quality=False,
            missed_steps=[],
            config_version="v1.0"
        )
        db.add(session)
    
    db.commit()
    
    yield {"device": device, "unit": unit}
    
    # Cleanup
    db.query(SessionModel).filter(SessionModel.device_id == device.id).delete()
    db.query(Heartbeat).filter(Heartbeat.device_id == device.id).delete()
    db.delete(device)
    db.delete(unit)
    db.commit()


def test_list_devices_success(auth_token, test_device_with_heartbeats):
    """Test GET /devices returns device list with online status."""
    response = client.get(
        "/api/v1/devices/",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 200
    devices = response.json()
    assert isinstance(devices, list)
    assert len(devices) >= 1
    
    # Check device structure
    device = next((d for d in devices if d["device_name"] == "Test-Device-01"), None)
    assert device is not None
    assert "device_id" in device
    assert "device_name" in device
    assert device["device_name"] == "Test-Device-01"
    assert "unit_id" in device
    assert "unit_name" in device
    assert device["unit_name"] == "Test ICU"
    assert "firmware_version" in device
    assert device["firmware_version"] == "v2.0.0"
    assert "installation_date" in device
    assert "is_online" in device
    assert device["is_online"] is True  # Recent heartbeat
    assert "last_seen" in device
    assert device["last_seen"] is not None


def test_list_devices_unauthorized():
    """Test GET /devices without auth token returns 401."""
    response = client.get("/api/v1/devices/")
    assert response.status_code == 401


def test_get_device_detail_success(auth_token, test_device_with_heartbeats):
    """Test GET /devices/{device_id} returns detailed device info."""
    device_id = str(test_device_with_heartbeats["device"].id)
    
    response = client.get(
        f"/api/v1/devices/{device_id}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 200
    device = response.json()
    
    # Check all fields
    assert device["device_id"] == device_id
    assert device["device_name"] == "Test-Device-01"
    assert device["unit_name"] == "Test ICU"
    assert device["unit_code"] == "TICU"
    assert device["firmware_version"] == "v2.0.0"
    assert device["installation_date"] == "2026-01-10"
    assert "created_at" in device
    assert "updated_at" in device
    assert device["is_online"] is True
    assert device["last_seen"] is not None
    assert device["total_sessions_all_time"] == 5


def test_get_device_detail_not_found(auth_token):
    """Test GET /devices/{device_id} with invalid ID returns 404."""
    response = client.get(
        "/api/v1/devices/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_device_detail_unauthorized():
    """Test GET /devices/{device_id} without auth token returns 401."""
    response = client.get("/api/v1/devices/some-device-id")
    assert response.status_code == 401
