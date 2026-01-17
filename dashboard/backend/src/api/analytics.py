"""
Analytics API router.

Provides endpoints for overview, unit, and device analytics.
"""
from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.analytics import OverviewResponse, UnitResponse, DeviceResponse
from ..services.analytics_service import get_overview_analytics, get_unit_analytics, get_device_analytics


router = APIRouter(tags=["analytics"])


@router.get("/overview", response_model=OverviewResponse)
def get_overview(
    date_from: date = Query(..., description="Start date for analytics (ISO 8601 format: YYYY-MM-DD)"),
    date_to: date = Query(..., description="End date for analytics (ISO 8601 format: YYYY-MM-DD)"),
    unit_id: Optional[str] = Query(None, description="Filter by unit ID (UUID)"),
    shift: Optional[str] = Query(None, description="Filter by shift (morning, afternoon, night)"),
    exclude_low_quality: bool = Query(False, description="Exclude low-quality sessions from metrics"),
    db: Session = Depends(get_db),
):
    """
    Get organization-wide or unit-scoped compliance analytics overview.
    
    Returns:
    - **compliance_trend**: Daily compliance rates over date range
    - **most_missed_step**: Most frequently missed WHO step
    - **average_wash_time_ms**: Average total session duration
    - **average_step_times**: Average duration per step
    - **quality_rate**: Percentage of non-low-quality sessions
    - **device_summary**: Device online/offline status
    
    Filters:
    - **date_from** / **date_to**: Required date range
    - **unit_id**: Optional unit filter (UUID)
    - **shift**: Optional shift filter (morning: 7am-3pm, afternoon: 3pm-11pm, night: 11pm-7am)
    - **exclude_low_quality**: Exclude sessions flagged as low quality
    
    Authorization:
    - Requires valid JWT token
    - Accessible to all authenticated users
    """
    # Validate date range
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must be before or equal to date_to")
    
    # Validate date range is not too large (prevent performance issues)
    max_range_days = 365
    if (date_to - date_from).days > max_range_days:
        raise HTTPException(
            status_code=400,
            detail=f"Date range too large. Maximum allowed range is {max_range_days} days."
        )
    
    # Validate shift parameter
    valid_shifts = ["morning", "afternoon", "night"]
    if shift and shift not in valid_shifts:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid shift value. Must be one of: {', '.join(valid_shifts)}"
        )
    
    # Get analytics
    try:
        analytics = get_overview_analytics(
            db=db,
            date_from=date_from,
            date_to=date_to,
            unit_id=unit_id,
            shift=shift,
            exclude_low_quality=exclude_low_quality
        )
        return analytics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating analytics: {str(e)}")


@router.get("/unit/{unit_id}", response_model=UnitResponse)
def get_unit_analytics_endpoint(
    unit_id: str,
    date_from: date = Query(..., description="Start date for analytics (ISO 8601 format: YYYY-MM-DD)"),
    date_to: date = Query(..., description="End date for analytics (ISO 8601 format: YYYY-MM-DD)"),
    shift: Optional[str] = Query(None, description="Filter by shift (morning, afternoon, night)"),
    exclude_low_quality: bool = Query(False, description="Exclude low-quality sessions from metrics"),
    db: Session = Depends(get_db),
):
    """
    Get unit-scoped analytics with device leaderboard.
    
    Returns:
    - **metrics**: Unit-scoped performance metrics (compliance trend, missed steps, wash times, quality rate)
    - **device_leaderboard**: Device rankings by compliance rate
    
    Filters:
    - **date_from** / **date_to**: Required date range
    - **shift**: Optional shift filter (morning: 7am-3pm, afternoon: 3pm-11pm, night: 11pm-7am)
    - **exclude_low_quality**: Exclude sessions flagged as low quality
    """
    
    # Validate date range
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must be before or equal to date_to")
    
    # Validate date range is not too large
    max_range_days = 365
    if (date_to - date_from).days > max_range_days:
        raise HTTPException(
            status_code=400,
            detail=f"Date range too large. Maximum allowed range is {max_range_days} days."
        )
    
    # Validate shift parameter
    valid_shifts = ["morning", "afternoon", "night"]
    if shift and shift not in valid_shifts:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid shift value. Must be one of: {', '.join(valid_shifts)}"
        )
    
    # Get unit analytics
    try:
        analytics = get_unit_analytics(
            db=db,
            unit_id=unit_id,
            date_from=date_from,
            date_to=date_to,
            shift=shift,
            exclude_low_quality=exclude_low_quality
        )
        return analytics
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating unit analytics: {str(e)}")


@router.get("/device/{device_id}", response_model=DeviceResponse)
def get_device_analytics_endpoint(
    device_id: str,
    date_from: date = Query(..., description="Start date for analytics (ISO 8601 format: YYYY-MM-DD)"),
    date_to: date = Query(..., description="End date for analytics (ISO 8601 format: YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    """
    Get device-level analytics with operational status, performance, and reliability flags.
    
    Returns:
    - **status**: Device operational status (online/offline, heartbeat metrics, uptime)
    - **performance**: Handwashing performance metrics (compliance rate, wash times, missed steps)
    - **reliability_flags**: Active warnings for offline periods, low heartbeat rate, etc.
    
    Filters:
    - **date_from** / **date_to**: Required date range for performance metrics
    
    Reliability Flags:
    - **Critical**: Device offline >24h, heartbeat rate <50%, no heartbeats in 24h
    - **Warning**: Device offline >1h, heartbeat rate <80%
    - **Info**: Uptime <90% in date range
    
    Authorization:
    - Requires valid JWT token
    - Accessible to all authenticated users
    """
    # Validate date range
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must be before or equal to date_to")
    
    # Validate date range is not too large
    max_range_days = 365
    if (date_to - date_from).days > max_range_days:
        raise HTTPException(
            status_code=400,
            detail=f"Date range too large. Maximum allowed range is {max_range_days} days."
        )
    
    # Get device analytics
    try:
        analytics = get_device_analytics(
            db=db,
            device_id=device_id,
            date_from=date_from,
            date_to=date_to
        )
        return analytics
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating device analytics: {str(e)}")


