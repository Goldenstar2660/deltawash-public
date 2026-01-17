"""
Devices API router.

Provides endpoints for listing devices and retrieving device details.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from ..database import get_db
from ..models.device import Device
from ..models.unit import Unit
from ..models.heartbeat import Heartbeat
from ..models.session import Session as SessionModel
from ..schemas.device import DeviceListItem, DeviceDetail


router = APIRouter(tags=["devices"])


@router.get("/", response_model=List[DeviceListItem])
def list_devices(
    db: Session = Depends(get_db),
):
    """
    List all devices with basic information and online status.
    
    Returns:
    - List of devices with device_id, device_name, unit info, firmware_version, 
      installation_date, is_online, last_seen
    
    Online Status:
    - **is_online**: True if heartbeat received within last hour
    - **last_seen**: Timestamp of most recent heartbeat
    """
    # Query all devices with their units
    devices_query = db.query(Device, Unit)\
        .join(Unit, Device.unit_id == Unit.id)\
        .all()
    
    # Build response with online status
    device_list = []
    current_time = datetime.now(timezone.utc)
    
    for device, unit in devices_query:
        # Get last heartbeat for this device
        last_heartbeat = db.query(Heartbeat)\
            .filter(Heartbeat.device_id == device.id)\
            .order_by(Heartbeat.timestamp.desc())\
            .first()
        
        last_seen = last_heartbeat.timestamp if last_heartbeat else None
        
        # Device is online if heartbeat within last hour
        is_online = False
        if last_seen:
            # Ensure last_seen is timezone-aware
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            time_since_last_seen = current_time - last_seen
            is_online = time_since_last_seen.total_seconds() < 3600  # 1 hour
        
        device_list.append(DeviceListItem(
            device_id=str(device.id),
            device_name=device.device_name,
            unit_id=str(unit.id),
            unit_name=unit.unit_name,
            firmware_version=device.firmware_version,
            installation_date=device.installation_date.date() if device.installation_date else None,
            is_online=is_online,
            last_seen=last_seen
        ))
    
    return device_list


@router.get("/{device_id}", response_model=DeviceDetail)
def get_device_detail(
    device_id: str,
    db: Session = Depends(get_db),
):
    """
    Get detailed information for a specific device.
    
    Returns:
    - Device details including unit info, firmware, installation date, 
      created/updated timestamps, online status, and total sessions all-time
    """
    # Query device with unit information
    result = db.query(Device, Unit)\
        .join(Unit, Device.unit_id == Unit.id)\
        .filter(Device.id == device_id)\
        .first()
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    device, unit = result
    
    # Get last heartbeat
    last_heartbeat = db.query(Heartbeat)\
        .filter(Heartbeat.device_id == device.id)\
        .order_by(Heartbeat.timestamp.desc())\
        .first()
    
    last_seen = last_heartbeat.timestamp if last_heartbeat else None
    
    # Device is online if heartbeat within last hour
    is_online = False
    if last_seen:
        # Ensure last_seen is timezone-aware
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        time_since_last_seen = datetime.now(timezone.utc) - last_seen
        is_online = time_since_last_seen.total_seconds() < 3600  # 1 hour
    
    # Get total sessions all-time for this device
    total_sessions = db.query(func.count(SessionModel.id))\
        .filter(SessionModel.device_id == device.id)\
        .scalar() or 0
    
    return DeviceDetail(
        device_id=str(device.id),
        device_name=device.device_name,
        unit_id=str(unit.id),
        unit_name=unit.unit_name,
        unit_code=unit.unit_code,
        firmware_version=device.firmware_version,
        installation_date=device.installation_date.date() if device.installation_date else None,
        created_at=device.created_at,
        updated_at=device.updated_at,
        is_online=is_online,
        last_seen=last_seen,
        total_sessions_all_time=total_sessions
    )
