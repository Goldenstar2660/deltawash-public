"""
Analytics service for calculating dashboard metrics.

Provides functions for overview analytics, unit analytics, and device analytics.
"""
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from sqlalchemy import func, text, and_, or_, Integer, case
from sqlalchemy.orm import Session

from ..models.session import Session as SessionModel
from ..models.device import Device
from ..models.unit import Unit
from ..models.step import Step
from ..schemas.analytics import (
    OverviewResponse,
    ComplianceTrendItem,
    MostMissedStep,
    AverageStepTime,
    DeviceSummary
)


# WHO step names mapping
STEP_NAMES = {
    2: "Palm to palm",
    3: "Right/Left palm over dorsum",
    4: "Palm to palm fingers interlaced",
    5: "Backs of fingers to opposing palms",
    6: "Rotational rubbing of thumbs",
    7: "Rotational rubbing of fingertips"
}

# Shift time ranges (24-hour format)
SHIFT_RANGES = {
    "morning": (time(7, 0), time(15, 0)),      # 7am-3pm
    "afternoon": (time(15, 0), time(23, 0)),   # 3pm-11pm
    "night": (time(23, 0), time(7, 0))          # 11pm-7am (spans midnight)
}


def get_shift_filter(shift: Optional[str]) -> Optional[Tuple[time, time]]:
    """
    Get time range for shift filter.
    
    Args:
        shift: Shift name (morning, afternoon, night) or None
        
    Returns:
        Tuple of (start_time, end_time) or None if no shift specified
    """
    if shift and shift in SHIFT_RANGES:
        return SHIFT_RANGES[shift]
    return None


def apply_shift_filter(query, timestamp_column, shift: Optional[str]):
    """
    Apply shift time filter to query.
    
    Args:
        query: SQLAlchemy query object
        timestamp_column: Column to filter on
        shift: Shift name or None
        
    Returns:
        Modified query with shift filter applied
    """
    shift_range = get_shift_filter(shift)
    if not shift_range:
        return query
    
    start_time, end_time = shift_range
    
    # Handle shift that spans midnight (night shift)
    if start_time > end_time:
        # Night shift: 11pm-7am (time >= 23:00 OR time < 07:00)
        query = query.filter(
            or_(
                func.extract('hour', timestamp_column) >= start_time.hour,
                func.extract('hour', timestamp_column) < end_time.hour
            )
        )
    else:
        # Day/afternoon shift: time >= start AND time < end
        query = query.filter(
            and_(
                func.extract('hour', timestamp_column) >= start_time.hour,
                func.extract('hour', timestamp_column) < end_time.hour
            )
        )
    
    return query


def get_compliance_trend(
    db: Session,
    date_from: date,
    date_to: date,
    unit_id: Optional[str] = None,
    shift: Optional[str] = None,
    exclude_low_quality: bool = False
) -> List[ComplianceTrendItem]:
    """
    Calculate daily compliance trend.
    
    Uses materialized view only when:
    - No shift filter is applied
    - exclude_low_quality is True (MV already excludes low quality)
    
    Falls back to raw sessions query when:
    - Shift filtering is needed
    - exclude_low_quality is False (need to include ALL sessions)
    
    Args:
        db: Database session
        date_from: Start date for trend
        date_to: End date for trend
        unit_id: Filter by unit (optional)
        shift: Filter by shift (optional)
        exclude_low_quality: Exclude low-quality sessions
        
    Returns:
        List of daily compliance data points
    """
    # Use materialized view ONLY when:
    # 1. No shift filter AND
    # 2. Excluding low quality (since MV already excludes low quality)
    use_materialized_view = not shift and exclude_low_quality
    
    if use_materialized_view:
        query = db.execute(text("""
            SELECT 
                date,
                SUM(total_sessions) as total_sessions,
                SUM(compliant_sessions) as compliant_sessions,
                ROUND(100.0 * SUM(compliant_sessions) / NULLIF(SUM(total_sessions), 0), 2) as compliance_rate
            FROM mv_daily_compliance
            WHERE date >= :date_from AND date <= :date_to
            """ + (" AND unit_id = :unit_id" if unit_id else "") + """
            GROUP BY date
            ORDER BY date
        """), {"date_from": date_from, "date_to": date_to, "unit_id": unit_id} if unit_id else {"date_from": date_from, "date_to": date_to})
        
        results = []
        for row in query:
            results.append(ComplianceTrendItem(
                date=row.date,
                total_sessions=row.total_sessions,
                compliant_sessions=row.compliant_sessions,
                compliance_rate=row.compliance_rate or 0.0
            ))
        
        return results
    
    # Query raw sessions table for all other cases
    query = db.query(
        func.date(SessionModel.timestamp).label('date'),
        func.count(SessionModel.id).label('total_sessions'),
        func.count(SessionModel.id).filter(SessionModel.compliant == True).label('compliant_sessions')
    )
    
    # Apply date range filter
    query = query.filter(
        func.date(SessionModel.timestamp) >= date_from,
        func.date(SessionModel.timestamp) <= date_to
    )
    
    # Apply quality filter ONLY if excluding low quality
    if exclude_low_quality:
        query = query.filter(SessionModel.low_quality == False)
    
    # Apply unit filter
    if unit_id:
        query = query.join(Device, SessionModel.device_id == Device.id)
        query = query.filter(Device.unit_id == unit_id)
    
    # Apply shift filter
    query = apply_shift_filter(query, SessionModel.timestamp, shift)
    
    # Group by date and order
    query = query.group_by(func.date(SessionModel.timestamp)).order_by(func.date(SessionModel.timestamp))
    
    results = []
    for row in query:
        total = row.total_sessions
        compliant = row.compliant_sessions
        compliance_rate = (compliant / total * 100) if total > 0 else 0.0
        
        results.append(ComplianceTrendItem(
            date=row.date,
            total_sessions=total,
            compliant_sessions=compliant,
            compliance_rate=round(compliance_rate, 2)
        ))
    
    return results


def get_most_missed_step(
    db: Session,
    date_from: date,
    date_to: date,
    unit_id: Optional[str] = None,
    shift: Optional[str] = None,
    exclude_low_quality: bool = False
) -> Optional[MostMissedStep]:
    """
    Find the most frequently missed WHO step.
    
    Args:
        db: Database session
        date_from: Start date for analysis
        date_to: End date for analysis
        unit_id: Filter by unit (optional)
        shift: Filter by shift (optional)
        exclude_low_quality: Exclude low-quality sessions
        
    Returns:
        Most missed step data or None if no data
    """
    # Query step statistics from sessions in date range
    query = db.query(
        Step.step_id,
        func.count(Step.id).label('total_attempts'),
        func.count(case((Step.completed == False, 1))).label('missed_count')
    ).join(SessionModel, Step.session_id == SessionModel.id)
    
    # Apply filters
    query = query.filter(
        func.date(SessionModel.timestamp) >= date_from,
        func.date(SessionModel.timestamp) <= date_to
    )
    
    if exclude_low_quality:
        query = query.filter(SessionModel.low_quality == False)
    
    if unit_id:
        query = query.join(Device, SessionModel.device_id == Device.id)
        query = query.filter(Device.unit_id == unit_id)
    
    # Apply shift filter
    query = apply_shift_filter(query, SessionModel.timestamp, shift)
    
    # Group by step and order by missed count descending
    query = query.group_by(Step.step_id).order_by(func.count(case((Step.completed == False, 1))).desc())
    
    result = query.first()
    
    if not result or result.missed_count == 0:
        return None
    
    total = result.total_attempts
    missed = result.missed_count
    miss_rate = (missed / total * 100) if total > 0 else 0.0
    
    return MostMissedStep(
        step_id=result.step_id,
        step_name=STEP_NAMES.get(result.step_id, f"Step {result.step_id}"),
        missed_count=missed,
        miss_rate=round(miss_rate, 2)
    )


def get_average_wash_time(
    db: Session,
    date_from: date,
    date_to: date,
    unit_id: Optional[str] = None,
    shift: Optional[str] = None,
    exclude_low_quality: bool = False
) -> float:
    """
    Calculate average total session duration.
    
    Args:
        db: Database session
        date_from: Start date for analysis
        date_to: End date for analysis
        unit_id: Filter by unit (optional)
        shift: Filter by shift (optional)
        exclude_low_quality: Exclude low-quality sessions
        
    Returns:
        Average duration in milliseconds
    """
    query = db.query(func.avg(SessionModel.duration_ms))
    
    # Apply filters
    query = query.filter(
        func.date(SessionModel.timestamp) >= date_from,
        func.date(SessionModel.timestamp) <= date_to
    )
    
    if exclude_low_quality:
        query = query.filter(SessionModel.low_quality == False)
    
    if unit_id:
        query = query.join(Device, SessionModel.device_id == Device.id)
        query = query.filter(Device.unit_id == unit_id)
    
    # Apply shift filter
    query = apply_shift_filter(query, SessionModel.timestamp, shift)
    
    result = query.scalar()
    return round(float(result), 2) if result else 0.0


def get_average_step_times(
    db: Session,
    date_from: date,
    date_to: date,
    unit_id: Optional[str] = None,
    shift: Optional[str] = None,
    exclude_low_quality: bool = False
) -> List[AverageStepTime]:
    """
    Calculate average duration per WHO step.
    
    Args:
        db: Database session
        date_from: Start date for analysis
        date_to: End date for analysis
        unit_id: Filter by unit (optional)
        shift: Filter by shift (optional)
        exclude_low_quality: Exclude low-quality sessions
        
    Returns:
        List of average step times
    """
    query = db.query(
        Step.step_id,
        func.avg(Step.duration_ms).label('avg_duration_ms')
    ).join(SessionModel, Step.session_id == SessionModel.id)
    
    # Apply filters
    query = query.filter(
        func.date(SessionModel.timestamp) >= date_from,
        func.date(SessionModel.timestamp) <= date_to
    )
    
    if exclude_low_quality:
        query = query.filter(SessionModel.low_quality == False)
    
    if unit_id:
        query = query.join(Device, SessionModel.device_id == Device.id)
        query = query.filter(Device.unit_id == unit_id)
    
    # Apply shift filter
    query = apply_shift_filter(query, SessionModel.timestamp, shift)
    
    # Group by step and order by step_id
    query = query.group_by(Step.step_id).order_by(Step.step_id)
    
    results = []
    for row in query:
        results.append(AverageStepTime(
            step_id=row.step_id,
            step_name=STEP_NAMES.get(row.step_id, f"Step {row.step_id}"),
            avg_duration_ms=round(float(row.avg_duration_ms), 2) if row.avg_duration_ms else 0.0
        ))
    
    return results


def get_quality_rate(
    db: Session,
    date_from: date,
    date_to: date,
    unit_id: Optional[str] = None,
    shift: Optional[str] = None
) -> float:
    """
    Calculate percentage of non-low-quality sessions.
    
    Args:
        db: Database session
        date_from: Start date for analysis
        date_to: End date for analysis
        unit_id: Filter by unit (optional)
        shift: Filter by shift (optional)
        
    Returns:
        Quality rate percentage (0-100)
    """
    query = db.query(
        func.count(SessionModel.id).label('total'),
        func.count(case((SessionModel.low_quality == False, 1))).label('good_quality')
    )
    
    # Apply filters
    query = query.filter(
        func.date(SessionModel.timestamp) >= date_from,
        func.date(SessionModel.timestamp) <= date_to
    )
    
    if unit_id:
        query = query.join(Device, SessionModel.device_id == Device.id)
        query = query.filter(Device.unit_id == unit_id)
    
    # Apply shift filter
    query = apply_shift_filter(query, SessionModel.timestamp, shift)
    
    result = query.first()
    
    if not result or result.total == 0:
        return 0.0
    
    quality_rate = (result.good_quality / result.total * 100) if result.total > 0 else 0.0
    return round(quality_rate, 2)


def get_device_summary(
    db: Session,
    unit_id: Optional[str] = None
) -> DeviceSummary:
    """
    Get device operational status summary.
    
    Args:
        db: Database session
        unit_id: Filter by unit (optional)
        
    Returns:
        Device summary with online/offline counts
    """
    # Query materialized view for device status
    query = db.execute(text("""
        SELECT 
            COUNT(*) as total_devices,
            COUNT(*) FILTER (WHERE is_offline = FALSE) as online_devices,
            COUNT(*) FILTER (WHERE is_offline = TRUE) as offline_devices
        FROM mv_device_status
        """ + (" WHERE unit_id = :unit_id" if unit_id else "")),
        {"unit_id": unit_id} if unit_id else {}
    )
    
    result = query.first()
    
    if not result:
        return DeviceSummary(
            total_devices=0,
            online_devices=0,
            offline_devices=0
        )
    
    return DeviceSummary(
        total_devices=result.total_devices,
        online_devices=result.online_devices,
        offline_devices=result.offline_devices
    )


def get_overview_analytics(
    db: Session,
    date_from: date,
    date_to: date,
    unit_id: Optional[str] = None,
    shift: Optional[str] = None,
    exclude_low_quality: bool = False
) -> OverviewResponse:
    """
    Get comprehensive overview analytics for organization or unit.
    
    Args:
        db: Database session
        date_from: Start date for analysis
        date_to: End date for analysis
        unit_id: Filter by unit (optional)
        shift: Filter by shift (optional)
        exclude_low_quality: Exclude low-quality sessions
        
    Returns:
        Complete overview analytics response
    """
    # Calculate all metrics
    compliance_trend = get_compliance_trend(db, date_from, date_to, unit_id, shift, exclude_low_quality)
    most_missed_step = get_most_missed_step(db, date_from, date_to, unit_id, shift, exclude_low_quality)
    average_wash_time_ms = get_average_wash_time(db, date_from, date_to, unit_id, shift, exclude_low_quality)
    average_step_times = get_average_step_times(db, date_from, date_to, unit_id, shift, exclude_low_quality)
    quality_rate = get_quality_rate(db, date_from, date_to, unit_id, shift)
    device_summary = get_device_summary(db, unit_id)
    
    return OverviewResponse(
        compliance_trend=compliance_trend,
        most_missed_step=most_missed_step,
        average_wash_time_ms=average_wash_time_ms,
        average_step_times=average_step_times,
        quality_rate=quality_rate,
        device_summary=device_summary
    )


def get_device_leaderboard(
    db: Session,
    unit_id: str,
    date_from: date,
    date_to: date,
    shift: Optional[str] = None,
    exclude_low_quality: bool = False
) -> List[Dict]:
    """
    Calculate device performance leaderboard for a unit.
    
    Args:
        db: Database session
        unit_id: Unit to analyze
        date_from: Start date for analysis
        date_to: End date for analysis
        shift: Filter by shift (optional)
        exclude_low_quality: Exclude low-quality sessions
        
    Returns:
        List of devices with rank, compliance rate, and session counts
    """
    # Build base query from sessions table joined with devices
    query = db.query(
        Device.id.label('device_id'),
        Device.device_name,
        func.count(SessionModel.id).label('total_sessions'),
        func.count(SessionModel.id).filter(SessionModel.compliant == True).label('compliant_sessions'),
        (func.count(SessionModel.id).filter(SessionModel.compliant == True).cast(Integer) * 100.0 / 
         func.nullif(func.count(SessionModel.id), 0)).label('compliance_rate')
    ).join(
        SessionModel, SessionModel.device_id == Device.id
    ).filter(
        Device.unit_id == unit_id,
        func.date(SessionModel.timestamp) >= date_from,
        func.date(SessionModel.timestamp) <= date_to
    )
    
    # Apply quality filter
    if exclude_low_quality:
        query = query.filter(SessionModel.low_quality == False)
    
    # Apply shift filter
    query = apply_shift_filter(query, SessionModel.timestamp, shift)
    
    # Group by device and order by compliance rate descending
    query = query.group_by(Device.id, Device.device_name).order_by(
        func.coalesce((func.count(SessionModel.id).filter(SessionModel.compliant == True).cast(Integer) * 100.0 / 
                      func.nullif(func.count(SessionModel.id), 0)), 0).desc()
    )
    
    results = query.all()
    
    # Add rank using Python enumeration
    leaderboard = []
    for rank, row in enumerate(results, start=1):
        leaderboard.append({
            "rank": rank,
            "device_id": str(row.device_id),
            "device_name": row.device_name,
            "compliance_rate": round(row.compliance_rate or 0.0, 2),
            "total_sessions": row.total_sessions,
            "compliant_sessions": row.compliant_sessions
        })
    
    return leaderboard


def get_unit_analytics(
    db: Session,
    unit_id: str,
    date_from: date,
    date_to: date,
    shift: Optional[str] = None,
    exclude_low_quality: bool = False
):
    """
    Get comprehensive analytics for a specific unit.
    
    Args:
        db: Database session
        unit_id: Unit to analyze
        date_from: Start date for analysis
        date_to: End date for analysis
        shift: Filter by shift (optional)
        exclude_low_quality: Exclude low-quality sessions
        
    Returns:
        Unit analytics with metrics and device leaderboard
    """
    from ..schemas.analytics import UnitResponse, UnitMetrics, DeviceLeaderboardItem
    
    # Get unit information
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise ValueError(f"Unit {unit_id} not found")
    
    # Calculate unit-scoped metrics (reusing overview functions with unit_id filter)
    compliance_trend = get_compliance_trend(db, date_from, date_to, unit_id, shift, exclude_low_quality)
    most_missed_step = get_most_missed_step(db, date_from, date_to, unit_id, shift, exclude_low_quality)
    average_wash_time_ms = get_average_wash_time(db, date_from, date_to, unit_id, shift, exclude_low_quality)
    average_step_times = get_average_step_times(db, date_from, date_to, unit_id, shift, exclude_low_quality)
    quality_rate = get_quality_rate(db, date_from, date_to, unit_id, shift)
    
    # Get device leaderboard
    device_leaderboard_data = get_device_leaderboard(db, unit_id, date_from, date_to, shift, exclude_low_quality)
    
    # Build response
    metrics = UnitMetrics(
        unit_id=str(unit.id),
        unit_name=unit.unit_name,
        unit_code=unit.unit_code,
        compliance_trend=compliance_trend,
        most_missed_step=most_missed_step,
        average_wash_time_ms=average_wash_time_ms,
        average_step_times=average_step_times,
        quality_rate=quality_rate
    )
    
    device_leaderboard = [
        DeviceLeaderboardItem(**item)
        for item in device_leaderboard_data
    ]
    
    return UnitResponse(
        metrics=metrics,
        device_leaderboard=device_leaderboard
    )


def get_device_analytics(
    db: Session,
    device_id: str,
    date_from: date,
    date_to: date
):
    """
    Get comprehensive analytics for a specific device.
    
    Args:
        db: Database session
        device_id: Device UUID to analyze
        date_from: Start date for analysis
        date_to: End date for analysis
        
    Returns:
        Device analytics with status, performance, and reliability flags
    """
    from ..schemas.analytics import (
        DeviceResponse,
        DeviceStatus,
        DevicePerformance,
        ReliabilityFlag
    )
    from ..models.heartbeat import Heartbeat
    
    # Get device and unit information
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise ValueError(f"Device {device_id} not found")
    
    unit = db.query(Unit).filter(Unit.id == device.unit_id).first()
    if not unit:
        raise ValueError(f"Unit {device.unit_id} not found")
    
    # === Device Status Calculation ===
    
    # Get last heartbeat
    last_heartbeat = db.query(Heartbeat)\
        .filter(Heartbeat.device_id == device_id)\
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
    
    # Count heartbeats in last 24 hours
    heartbeats_24h_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    heartbeats_24h = db.query(func.count(Heartbeat.id))\
        .filter(Heartbeat.device_id == device_id)\
        .filter(Heartbeat.timestamp >= heartbeats_24h_ago)\
        .scalar() or 0
    
    # Expected heartbeats: 288 (24 hours * 12 per hour at 5-minute intervals)
    expected_heartbeats_24h = 288
    heartbeat_rate = (heartbeats_24h / expected_heartbeats_24h * 100) if expected_heartbeats_24h > 0 else 0
    
    # Calculate uptime percentage in date range
    date_from_dt = datetime.combine(date_from, time.min)
    date_to_dt = datetime.combine(date_to, time.max)
    
    total_expected_heartbeats = db.query(func.count(Heartbeat.id))\
        .filter(Heartbeat.device_id == device_id)\
        .filter(Heartbeat.timestamp >= date_from_dt)\
        .filter(Heartbeat.timestamp <= date_to_dt)\
        .filter(Heartbeat.online_status == True)\
        .scalar() or 0
    
    # Calculate expected heartbeats for date range (12 per hour)
    hours_in_range = (date_to_dt - date_from_dt).total_seconds() / 3600
    expected_heartbeats_range = int(hours_in_range * 12)
    uptime_percentage = (total_expected_heartbeats / expected_heartbeats_range * 100) if expected_heartbeats_range > 0 else 0
    
    device_status = DeviceStatus(
        device_id=str(device.id),
        device_name=device.device_name,
        unit_id=str(unit.id),
        unit_name=unit.unit_name,
        is_online=is_online,
        last_seen=last_seen,
        heartbeats_24h=heartbeats_24h,
        expected_heartbeats_24h=expected_heartbeats_24h,
        heartbeat_rate=round(heartbeat_rate, 1),
        uptime_percentage=round(uptime_percentage, 1),
        firmware_version=device.firmware_version,
        installation_date=device.installation_date.date() if device.installation_date else None
    )
    
    # === Device Performance Calculation ===
    
    # Query sessions for the device in date range
    sessions_query = db.query(SessionModel)\
        .filter(SessionModel.device_id == device_id)\
        .filter(SessionModel.timestamp >= date_from_dt)\
        .filter(SessionModel.timestamp <= date_to_dt)
    
    total_sessions = sessions_query.count()
    compliant_sessions = sessions_query.filter(SessionModel.compliant == True).count()
    compliance_rate = (compliant_sessions / total_sessions * 100) if total_sessions > 0 else 0
    
    # Average wash time
    avg_wash_time = sessions_query\
        .with_entities(func.avg(SessionModel.duration_ms))\
        .scalar() or 0
    
    # Quality rate
    low_quality_sessions = sessions_query.filter(SessionModel.low_quality == True).count()
    quality_sessions = total_sessions - low_quality_sessions
    quality_rate = (quality_sessions / total_sessions * 100) if total_sessions > 0 else 0
    
    # Most missed step for this device
    most_missed_step = None
    if total_sessions > 0:
        # Query steps joined with sessions for this device
        step_stats = db.query(
            Step.step_id,
            func.count(Step.id).label('total_attempts'),
            func.sum(case((Step.completed == False, 1), else_=0)).label('missed_count')
        )\
        .join(SessionModel, Step.session_id == SessionModel.id)\
        .filter(SessionModel.device_id == device_id)\
        .filter(SessionModel.timestamp >= date_from_dt)\
        .filter(SessionModel.timestamp <= date_to_dt)\
        .group_by(Step.step_id)\
        .all()
        
        # Find step with highest miss count
        max_missed_step = None
        max_missed_count = 0
        
        for row in step_stats:
            missed_count = row.missed_count or 0
            if missed_count > max_missed_count:
                max_missed_count = missed_count
                max_missed_step = row.step_id
                total_attempts = row.total_attempts
        
        if max_missed_step:
            miss_rate = (max_missed_count / total_attempts * 100) if total_attempts > 0 else 0
            most_missed_step = MostMissedStep(
                step_id=max_missed_step,
                step_name=STEP_NAMES.get(max_missed_step, f"Step {max_missed_step}"),
                missed_count=max_missed_count,
                miss_rate=round(miss_rate, 1)
            )
    
    device_performance = DevicePerformance(
        total_sessions=total_sessions,
        compliant_sessions=compliant_sessions,
        compliance_rate=round(compliance_rate, 1),
        average_wash_time_ms=round(avg_wash_time, 1),
        low_quality_sessions=low_quality_sessions,
        quality_rate=round(quality_rate, 1),
        most_missed_step=most_missed_step
    )
    
    # === Reliability Flags Detection ===
    
    reliability_flags = []
    current_time = datetime.now(timezone.utc)
    
    # Flag 1: Offline period (last_seen > 1 hour)
    if not is_online and last_seen:
        time_offline = current_time - last_seen
        hours_offline = time_offline.total_seconds() / 3600
        
        if hours_offline >= 24:
            reliability_flags.append(ReliabilityFlag(
                severity="critical",
                message=f"Device offline for more than 24 hours (last seen: {last_seen.strftime('%Y-%m-%d %H:%M:%S')})",
                timestamp=current_time
            ))
        elif hours_offline >= 1:
            reliability_flags.append(ReliabilityFlag(
                severity="warning",
                message=f"Device offline for {int(hours_offline)} hour(s) (last seen: {last_seen.strftime('%Y-%m-%d %H:%M:%S')})",
                timestamp=current_time
            ))
    
    # Flag 2: Low heartbeat rate (<80% expected)
    if heartbeat_rate < 80:
        if heartbeat_rate < 50:
            reliability_flags.append(ReliabilityFlag(
                severity="critical",
                message=f"Critical heartbeat rate: {heartbeat_rate:.1f}% (expected 100%)",
                timestamp=current_time
            ))
        else:
            reliability_flags.append(ReliabilityFlag(
                severity="warning",
                message=f"Low heartbeat rate: {heartbeat_rate:.1f}% (expected 100%)",
                timestamp=current_time
            ))
    
    # Flag 3: No heartbeat data at all
    if heartbeats_24h == 0:
        reliability_flags.append(ReliabilityFlag(
            severity="critical",
            message="No heartbeats received in last 24 hours",
            timestamp=current_time
        ))
    
    # Flag 4: Low uptime in date range
    if uptime_percentage < 90 and total_expected_heartbeats > 0:
        reliability_flags.append(ReliabilityFlag(
            severity="info",
            message=f"Uptime in date range: {uptime_percentage:.1f}% (expected >90%)",
            timestamp=current_time
        ))
    
    return DeviceResponse(
        status=device_status,
        performance=device_performance,
        reliability_flags=reliability_flags
    )


