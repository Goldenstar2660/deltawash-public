"""
Demo data generation service for Hospital Dashboard.

Generates synthetic data to enable dashboard demos without physical devices.
Implements realistic variation in compliance rates, timing distributions, and device status.
"""
import random
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import uuid

import numpy as np
from sqlalchemy.orm import Session

from ..models.unit import Unit
from ..models.device import Device
from ..models.session import Session as SessionModel
from ..models.step import Step
from ..models.heartbeat import Heartbeat


# Unit names and codes for demo data - expanded for variety
DEMO_UNITS = [
    ("Intensive Care Unit", "ICU"),
    ("Emergency Room", "ER"),
    ("Surgery Department", "SURGERY"),
    ("Cardiology Unit", "CARDIO"),
    ("Pediatrics Ward", "PEDS"),
    ("Oncology Unit", "ONCO"),
    ("Neurology Department", "NEURO"),
    ("Orthopedics Ward", "ORTHO"),
]

# Firmware versions for realistic device generation - wider variety
FIRMWARE_VERSIONS = ["v1.0.0", "v1.0.1", "v1.1.0", "v1.1.2", "v1.2.0", "v1.2.3", "v1.3.0", "v1.3.1", "v2.0.0"]

# Step duration ranges (in milliseconds) per WHO step requirements
STEP_DURATION_RANGES = {
    2: (5000, 12000),   # Palm to palm: 5-12s
    3: (6000, 14000),   # Right/left palm over dorsum: 6-14s
    4: (5000, 11000),   # Palm to palm fingers interlaced: 5-11s
    5: (5000, 10000),   # Backs of fingers: 5-10s
    6: (6000, 13000),   # Rotational rubbing thumbs: 6-13s
    7: (5000, 11000),   # Rotational rubbing fingertips: 5-11s
}

# Minimum durations for step completion (in milliseconds)
STEP_MIN_DURATION = {
    2: 5000,
    3: 6000,
    4: 5000,
    5: 5000,
    6: 6000,
    7: 5000,
}

# Shift time ranges (hours) for varied session distribution
# morning: 7-15, afternoon: 15-23, night: 23-7
SHIFT_HOUR_RANGES = {
    "morning": (7, 15),
    "afternoon": (15, 23),
    "night_early": (23, 24),  # 11pm to midnight
    "night_late": (0, 7),      # midnight to 7am
}

# Device behavior profiles for varied compliance patterns
DEVICE_PROFILES = [
    {"name": "high_performer", "compliance_modifier": 0.95, "quality_modifier": 0.98, "offline_modifier": 0.02},
    {"name": "standard", "compliance_modifier": 0.85, "quality_modifier": 0.92, "offline_modifier": 0.08},
    {"name": "low_performer", "compliance_modifier": 0.70, "quality_modifier": 0.80, "offline_modifier": 0.15},
    {"name": "problematic", "compliance_modifier": 0.55, "quality_modifier": 0.70, "offline_modifier": 0.25},
]

# Unit behavior profiles for varied performance across units
UNIT_PROFILES = {
    "ICU": {"compliance_boost": 0.10, "session_multiplier": 1.5},      # High volume, high compliance
    "ER": {"compliance_boost": -0.05, "session_multiplier": 2.0},      # Very high volume, slightly lower compliance
    "SURGERY": {"compliance_boost": 0.15, "session_multiplier": 1.2},  # High compliance, moderate volume
    "CARDIO": {"compliance_boost": 0.08, "session_multiplier": 1.0},   # Good compliance, normal volume
    "PEDS": {"compliance_boost": 0.05, "session_multiplier": 0.8},     # Good compliance, lower volume
    "ONCO": {"compliance_boost": 0.12, "session_multiplier": 0.7},     # High compliance, lower volume
    "NEURO": {"compliance_boost": 0.03, "session_multiplier": 0.9},    # Normal profile
    "ORTHO": {"compliance_boost": -0.02, "session_multiplier": 1.1},   # Slightly lower compliance
}

# === INTERESTING DATA PATTERNS ===
# Training intervention date - compliance improves after this date
TRAINING_INTERVENTION_DAY = 45  # Day 45 of the 90-day period (roughly middle)

# Step 6 (thumbs) is consistently the most missed step
PROBLEMATIC_STEP = 6
PROBLEMATIC_STEP_EXTRA_MISS_RATE = 0.20  # 20% extra miss rate for this step

# Night shift performance penalty
NIGHT_SHIFT_COMPLIANCE_PENALTY = 0.10  # 10% lower compliance
NIGHT_SHIFT_DURATION_PENALTY = 0.85    # 15% shorter wash times

# One problematic device per unit for device reliability story
PROBLEMATIC_DEVICE_EXTRA_OFFLINE = 0.15  # Extra offline rate


def set_seed(seed: int) -> None:
    """
    Set deterministic seed for reproducible data generation.
    
    Args:
        seed: Integer seed value for random number generators
    """
    random.seed(seed)
    np.random.seed(seed)


def generate_units(db: Session, num_units: int = 8) -> List[Tuple[uuid.UUID, str]]:
    """
    Generate hospital units with realistic names and codes.
    
    Args:
        db: Database session
        num_units: Number of units to create (default: 8, max: len(DEMO_UNITS))
        
    Returns:
        List of tuples (unit_id, unit_code) for further processing
    """
    unit_data = []
    units_to_create = DEMO_UNITS[:min(num_units, len(DEMO_UNITS))]
    
    for unit_name, unit_code in units_to_create:
        unit_id = uuid.UUID(int=random.getrandbits(128))
        unit = Unit(
            id=unit_id,
            unit_name=unit_name,
            unit_code=unit_code,
            hospital_id=None,  # Single hospital MVP
            created_at=datetime.utcnow()
        )
        db.add(unit)
        unit_data.append((unit_id, unit_code))
    
    db.commit()
    return unit_data


def generate_devices(
    db: Session,
    unit_data: List[Tuple[uuid.UUID, str]],
    num_devices: int = 30
) -> List[Dict]:
    """
    Generate devices distributed across units with realistic names, firmware versions,
    and behavior profiles for varied performance.
    
    Args:
        db: Database session
        unit_data: List of tuples (unit_id, unit_code) to distribute devices across
        num_devices: Total number of devices to create
        
    Returns:
        List of device dictionaries with id, unit_id, unit_code, and profile
    """
    device_data = []
    devices_per_unit = num_devices // len(unit_data)
    remaining_devices = num_devices % len(unit_data)
    
    for idx, (unit_id, unit_code) in enumerate(unit_data):
        # Distribute remaining devices to first units
        count = devices_per_unit + (1 if idx < remaining_devices else 0)
        
        for device_num in range(1, count + 1):
            device_id = uuid.UUID(int=random.getrandbits(128))
            device_name = f"Device-{idx + 1:02d}-{device_num:02d}"
            
            # Assign firmware version with weighted distribution (newer versions more common)
            firmware_weights = [0.02, 0.03, 0.05, 0.08, 0.12, 0.15, 0.20, 0.20, 0.15]
            firmware_version = random.choices(FIRMWARE_VERSIONS, weights=firmware_weights)[0]
            
            # Installation date spread over 2 years for variety
            installation_date = datetime.utcnow() - timedelta(days=random.randint(30, 730))
            
            # First device in each unit is "problematic" for the device reliability story
            is_problematic_device = (device_num == 1)
            
            if is_problematic_device:
                device_profile = {"name": "problematic_hw", "compliance_modifier": 0.80, "quality_modifier": 0.75, "offline_modifier": 0.20}
            else:
                # Assign device profile with weighted distribution
                profile_weights = [0.25, 0.55, 0.15, 0.05]
                device_profile = random.choices(DEVICE_PROFILES, weights=profile_weights)[0]
            
            device = Device(
                id=device_id,
                unit_id=unit_id,
                device_name=device_name,
                firmware_version=firmware_version,
                installation_date=installation_date,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(device)
            device_data.append({
                "id": device_id,
                "unit_id": unit_id,
                "unit_code": unit_code,
                "profile": device_profile,
                "is_problematic": is_problematic_device
            })
    
    db.commit()
    return device_data


def generate_sessions(
    db: Session,
    device_data: List[Dict],
    start_date: datetime,
    num_days: int,
    sessions_per_day: int,
    miss_rate: float = 0.15,
    low_quality_rate: float = 0.08
) -> List[Dict]:
    """
    Generate handwashing sessions with configurable compliance rates, quality flags,
    and varied distribution across shifts and time periods.
    
    Implements interesting data patterns:
    1. Training intervention - compliance improves after day 45
    2. Night shift underperformance
    3. Step 6 (thumbs) consistently most missed
    4. Unit-specific performance variations
    
    Args:
        db: Database session
        device_data: List of device dicts with id, unit_id, unit_code, and profile
        start_date: Start date for session generation
        num_days: Number of days to generate sessions for
        sessions_per_day: Average sessions per device per day
        miss_rate: Base probability of missing steps (default: 0.15)
        low_quality_rate: Base probability of low-quality flag (default: 0.08)
        
    Returns:
        List of session dictionaries for bulk insert
    """
    sessions = []
    config_version = "demo_v1_abc123"
    
    # Shift distribution weights (morning busiest, night quietest)
    shift_weights = {
        "morning": 0.45,      # 7am-3pm: busiest shift
        "afternoon": 0.35,    # 3pm-11pm: moderately busy
        "night": 0.20,        # 11pm-7am: quietest shift
    }
    
    # Weekday vs weekend patterns (less activity on weekends)
    weekend_activity_modifier = 0.6
    
    for day in range(num_days):
        current_date = start_date + timedelta(days=day)
        day_of_week = current_date.weekday()
        is_weekend = day_of_week >= 5
        
        # === PATTERN 1: Training intervention effect ===
        # After day 45, compliance improves by 10-15%
        post_training = day >= TRAINING_INTERVENTION_DAY
        training_boost = 0.0
        if post_training:
            # Gradual improvement over 2 weeks after training
            if day < TRAINING_INTERVENTION_DAY + 14:
                days_since_training = day - TRAINING_INTERVENTION_DAY
                training_boost = 0.12 * (days_since_training / 14)  # Gradual ramp-up
            else:
                training_boost = 0.12  # Full effect after 2 weeks
        
        for device_info in device_data:
            device_id = device_info["id"]
            unit_code = device_info["unit_code"]
            device_profile = device_info["profile"]
            is_problematic_device = device_info.get("is_problematic", False)
            
            # Get unit-specific modifiers
            unit_profile = UNIT_PROFILES.get(unit_code, {"compliance_boost": 0, "session_multiplier": 1.0})
            
            # Calculate adjusted sessions for this device on this day
            base_sessions = sessions_per_day * unit_profile["session_multiplier"]
            if is_weekend:
                base_sessions *= weekend_activity_modifier
            
            # Problematic devices have fewer sessions (more incomplete)
            if is_problematic_device:
                base_sessions *= 0.7
            
            # Add daily variation ±40%
            daily_sessions = int(base_sessions * np.random.uniform(0.6, 1.4))
            daily_sessions = max(1, daily_sessions)  # At least 1 session per day
            
            # Distribute sessions across shifts based on weights
            for _ in range(daily_sessions):
                # Select shift based on weights
                shift_choice = random.choices(
                    list(shift_weights.keys()),
                    weights=list(shift_weights.values())
                )[0]
                
                # Generate timestamp within the shift
                if shift_choice == "morning":
                    hour = random.randint(7, 14)
                elif shift_choice == "afternoon":
                    hour = random.randint(15, 22)
                else:  # night
                    if random.random() < 0.3:
                        hour = random.randint(23, 23)  # Before midnight
                    else:
                        hour = random.randint(0, 6)    # After midnight
                
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                timestamp = current_date.replace(hour=hour, minute=minute, second=second)
                
                # === Calculate effective compliance ===
                device_compliance = device_profile["compliance_modifier"]
                unit_compliance_boost = unit_profile["compliance_boost"]
                
                effective_compliance = device_compliance + unit_compliance_boost + training_boost
                
                # === PATTERN 2: Night shift penalty ===
                is_night_shift = shift_choice == "night"
                if is_night_shift:
                    effective_compliance -= NIGHT_SHIFT_COMPLIANCE_PENALTY
                
                # ICU and Surgery respond better to training
                if post_training and unit_code in ["ICU", "SURGERY"]:
                    effective_compliance += 0.05
                
                effective_compliance = min(0.98, max(0.40, effective_compliance))
                effective_miss_rate = 1.0 - effective_compliance
                
                # Determine if session misses steps
                has_missed_steps = random.random() < effective_miss_rate
                missed_steps = []
                if has_missed_steps:
                    # === PATTERN 3: Step 6 (thumbs) is most commonly missed ===
                    base_step_weights = {
                        2: 0.10, 3: 0.12, 4: 0.10,
                        5: 0.18, 6: 0.30, 7: 0.20  # Step 6 has highest weight
                    }
                    num_missed = random.choices([1, 2, 3], weights=[0.55, 0.35, 0.10])[0]
                    available_steps = list(range(2, 8))
                    
                    for _ in range(num_missed):
                        if not available_steps:
                            break
                        weights = [base_step_weights[s] for s in available_steps]
                        total_weight = sum(weights)
                        weights = [w / total_weight for w in weights]
                        step = random.choices(available_steps, weights=weights)[0]
                        missed_steps.append(step)
                        available_steps.remove(step)
                
                # Low quality flag
                effective_quality_rate = device_profile["quality_modifier"]
                if is_problematic_device:
                    effective_quality_rate *= 0.8
                low_quality = random.random() > effective_quality_rate
                
                compliant = not has_missed_steps
                duration_ms = random.randint(30000, 60000)  # Placeholder
                
                session = {
                    "id": uuid.UUID(int=random.getrandbits(128)),
                    "device_id": device_id,
                    "timestamp": timestamp,
                    "duration_ms": duration_ms,
                    "compliant": compliant,
                    "low_quality": low_quality,
                    "missed_steps": missed_steps,
                    "config_version": config_version,
                    "created_at": datetime.utcnow(),
                    "_is_night_shift": is_night_shift,
                    "_post_training": post_training,
                }
                sessions.append(session)
    
    return sessions


def generate_steps(
    db: Session,
    sessions: List[Dict],
    miss_rate: float = 0.15
) -> List[Dict]:
    """
    Generate WHO handwashing steps for each session with realistic durations.
    
    Implements patterns:
    - Night shift has shorter durations
    - Post-training has slightly longer, more thorough washes
    
    Args:
        db: Database session
        sessions: List of session dictionaries
        miss_rate: Probability of missing steps (used for completion flags)
        
    Returns:
        List of step dictionaries for bulk insert, and updated sessions list
    """
    steps = []
    
    for session in sessions:
        total_duration = 0
        missed_steps = session["missed_steps"]
        is_night_shift = session.get("_is_night_shift", False)
        post_training = session.get("_post_training", False)
        
        # Duration modifier based on shift and training
        duration_modifier = 1.0
        if is_night_shift:
            duration_modifier *= NIGHT_SHIFT_DURATION_PENALTY  # Shorter washes at night
        if post_training:
            duration_modifier *= 1.10  # Slightly longer washes after training
        
        # Generate steps 2-7 (WHO steps)
        for step_id in range(2, 8):
            step_missed = step_id in missed_steps
            
            # Determine duration based on whether step was completed
            if step_missed:
                # Missed steps have shorter duration (below threshold)
                min_duration = 1000
                max_duration = STEP_MIN_DURATION[step_id] - 1000
                duration_ms = random.randint(min_duration, max(min_duration, max_duration))
                completed = False
            else:
                # Completed steps have duration in normal range
                min_duration, max_duration = STEP_DURATION_RANGES[step_id]
                base_duration = random.randint(min_duration, max_duration)
                duration_ms = int(base_duration * duration_modifier)
                completed = True
            
            total_duration += duration_ms
            
            # Generate confidence score (0.7-1.0 for completed, 0.3-0.7 for missed)
            if completed:
                confidence_score = np.random.uniform(0.7, 1.0)
            else:
                confidence_score = np.random.uniform(0.3, 0.7)
            
            step = {
                "id": uuid.UUID(int=random.getrandbits(128)),
                "session_id": session["id"],
                "step_id": step_id,
                "duration_ms": duration_ms,
                "completed": completed,
                "confidence_score": round(confidence_score, 3),
                "created_at": datetime.utcnow()
            }
            steps.append(step)
        
        # Update session duration with actual total
        session["duration_ms"] = total_duration
        
        # Clean up internal flags before insert
        session.pop("_is_night_shift", None)
        session.pop("_post_training", None)
    
    return steps


def generate_heartbeats(
    db: Session,
    device_data: List[Dict],
    start_date: datetime,
    num_days: int,
    offline_rate: float = 0.08
) -> List[Dict]:
    """
    Generate device heartbeats for demo purposes.
    
    Only generates heartbeats for the last 7 days to keep data volume manageable.
    This is sufficient to demonstrate device health monitoring features.
    
    Args:
        db: Database session
        device_data: List of device dicts with id and profile
        start_date: Start date (ignored - we only generate recent heartbeats)
        num_days: Number of days (ignored - we only generate last 7 days)
        offline_rate: Base probability of device being offline (default: 0.08)
        
    Returns:
        List of heartbeat dictionaries for bulk insert
    """
    heartbeats = []
    # Only generate heartbeats for last 7 days - sufficient for demo
    heartbeat_days = 7
    heartbeat_interval = timedelta(minutes=30)  # 30-minute intervals instead of 5
    heartbeat_start = datetime.utcnow() - timedelta(days=heartbeat_days)
    
    for device_info in device_data:
        device_id = device_info["id"]
        device_profile = device_info["profile"]
        
        # Use device profile's offline modifier
        effective_offline_rate = device_profile["offline_modifier"]
        
        current_time = heartbeat_start
        end_time = datetime.utcnow()
        
        # Determine firmware version for this device
        firmware_version = random.choice(FIRMWARE_VERSIONS)
        
        # Track if device is in an offline period
        in_offline_period = False
        offline_period_end = None
        
        while current_time < end_time:
            # Check if we should start an offline period
            if not in_offline_period and random.random() < effective_offline_rate * 0.05:
                # Start offline period (varies by device profile)
                offline_duration_hours = random.randint(1, 4) if device_profile["name"] == "problematic" else random.randint(1, 2)
                in_offline_period = True
                offline_period_end = current_time + timedelta(hours=offline_duration_hours)
            
            # Check if offline period has ended
            if in_offline_period and current_time >= offline_period_end:
                in_offline_period = False
                offline_period_end = None
            
            online_status = not in_offline_period
            
            heartbeat = {
                "id": uuid.UUID(int=random.getrandbits(128)),
                "device_id": device_id,
                "timestamp": current_time,
                "firmware_version": firmware_version,
                "online_status": online_status,
                "created_at": datetime.utcnow()
            }
            heartbeats.append(heartbeat)
            
            current_time += heartbeat_interval
    
    return heartbeats


def validate_generated_data(
    num_devices: int,
    num_sessions: int,
    num_days: int
) -> None:
    """
    Validate that generated data meets minimum requirements.
    
    Args:
        num_devices: Number of devices created
        num_sessions: Number of sessions created
        num_days: Number of days of data generated
        
    Raises:
        AssertionError: If data does not meet minimum requirements
    """
    assert num_devices >= 10, f"Insufficient devices: {num_devices} < 10"
    assert num_sessions >= 100, f"Insufficient sessions: {num_sessions} < 100"
    assert num_days >= 7, f"Insufficient days: {num_days} < 7"


def generate_synthetic_data(
    db: Session,
    num_devices: int = 20,
    num_days: int = 90,
    sessions_per_day: int = 8,
    miss_rate: float = 0.15,
    low_quality_rate: float = 0.08,
    offline_rate: float = 0.08,
    seed: int = 42
) -> Dict[str, int]:
    """
    Generate complete synthetic dataset for dashboard demo.
    
    Args:
        db: Database session
        num_devices: Number of devices to create (default: 30)
        num_days: Number of days of historical data (default: 365)
        sessions_per_day: Average sessions per device per day (default: 8)
        miss_rate: Probability of missing steps (default: 0.15)
        low_quality_rate: Probability of low-quality sessions (default: 0.08)
        offline_rate: Probability of device being offline (default: 0.08)
        seed: Random seed for reproducibility (default: 42)
        
    Returns:
        Dictionary with counts of created entities
    """
    # Set deterministic seed
    set_seed(seed)
    
    # Calculate start date (num_days ago from now)
    start_date = datetime.utcnow() - timedelta(days=num_days)
    
    # Generate units (up to 8 units)
    unit_data = generate_units(db, num_units=8)
    
    # Generate devices
    device_data = generate_devices(db, unit_data, num_devices)
    
    # Generate sessions
    sessions = generate_sessions(
        db, device_data, start_date, num_days, sessions_per_day,
        miss_rate, low_quality_rate
    )
    
    # Generate steps for sessions (also updates session durations)
    steps = generate_steps(db, sessions, miss_rate)
    
    # Generate heartbeats
    heartbeats = generate_heartbeats(db, device_data, start_date, num_days, offline_rate)
    
    # Validate data meets requirements
    validate_generated_data(len(device_data), len(sessions), num_days)
    
    # Return summary
    return {
        "units_created": len(unit_data),
        "devices_created": len(device_data),
        "sessions_created": len(sessions),
        "steps_created": len(steps),
        "heartbeats_created": len(heartbeats),
        "date_range_start": start_date,
        "date_range_end": datetime.utcnow()
    }
