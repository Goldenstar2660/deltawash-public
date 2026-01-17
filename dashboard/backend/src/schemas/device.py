"""
Pydantic schemas for device endpoints.

Defines request/response models for device listing, detail, and heartbeat ingestion.
"""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class DeviceListItem(BaseModel):
    """Device list item with basic info and status."""
    device_id: str = Field(description="Device UUID")
    device_name: str = Field(description="Human-readable device name")
    unit_id: str = Field(description="Unit UUID where device is installed")
    unit_name: str = Field(description="Unit name")
    firmware_version: str = Field(description="Current firmware version")
    installation_date: date = Field(description="Date device was installed")
    is_online: bool = Field(description="True if heartbeat received in last hour")
    last_seen: Optional[datetime] = Field(None, description="Timestamp of last heartbeat")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "device_id": "550e8400-e29b-41d4-a716-446655440000",
                "device_name": "ICU-Device-01",
                "unit_id": "660e8400-e29b-41d4-a716-446655440000",
                "unit_name": "Intensive Care Unit",
                "firmware_version": "v2.1.0",
                "installation_date": "2026-01-10",
                "is_online": True,
                "last_seen": "2026-01-10T15:30:00"
            }
        }


class DeviceDetail(BaseModel):
    """Detailed device information."""
    device_id: str = Field(description="Device UUID")
    device_name: str = Field(description="Human-readable device name")
    unit_id: str = Field(description="Unit UUID where device is installed")
    unit_name: str = Field(description="Unit name")
    unit_code: str = Field(description="Short unit code")
    firmware_version: str = Field(description="Current firmware version")
    installation_date: date = Field(description="Date device was installed")
    created_at: datetime = Field(description="Timestamp when device was added to database")
    updated_at: datetime = Field(description="Timestamp when device was last updated")
    is_online: bool = Field(description="True if heartbeat received in last hour")
    last_seen: Optional[datetime] = Field(None, description="Timestamp of last heartbeat")
    total_sessions_all_time: int = Field(ge=0, description="Total sessions recorded by this device")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "device_id": "550e8400-e29b-41d4-a716-446655440000",
                "device_name": "ICU-Device-01",
                "unit_id": "660e8400-e29b-41d4-a716-446655440000",
                "unit_name": "Intensive Care Unit",
                "unit_code": "ICU",
                "firmware_version": "v2.1.0",
                "installation_date": "2026-01-10",
                "created_at": "2026-01-10T10:00:00",
                "updated_at": "2026-01-10T15:30:00",
                "is_online": True,
                "last_seen": "2026-01-10T15:30:00",
                "total_sessions_all_time": 1847
            }
        }


class HeartbeatEventRequest(BaseModel):
    """Request payload for device heartbeat ingestion."""
    device_id: str = Field(description="Device UUID sending heartbeat")
    timestamp: datetime = Field(description="Heartbeat timestamp (UTC)")
    firmware_version: str = Field(description="Current firmware version")
    online_status: bool = Field(default=True, description="Device online status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "device_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2026-01-10T15:30:00Z",
                "firmware_version": "v2.1.0",
                "online_status": True
            }
        }


class HeartbeatResponse(BaseModel):
    """Response after heartbeat ingestion."""
    id: str = Field(description="Heartbeat record UUID")
    device_id: str = Field(description="Device UUID")
    timestamp: datetime = Field(description="Heartbeat timestamp")
    firmware_version: str = Field(description="Firmware version")
    online_status: bool = Field(description="Online status")
    created_at: datetime = Field(description="When record was created in database")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "770e8400-e29b-41d4-a716-446655440000",
                "device_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2026-01-10T15:30:00Z",
                "firmware_version": "v2.1.0",
                "online_status": True,
                "created_at": "2026-01-10T15:30:05Z"
            }
        }
