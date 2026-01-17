"""
Pydantic schemas for analytics endpoints.

Defines request/response models for overview, unit, and device analytics.
"""
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ComplianceTrendItem(BaseModel):
    """Daily compliance trend data point."""
    date: date
    total_sessions: int = Field(ge=0, description="Total sessions on this date")
    compliant_sessions: int = Field(ge=0, description="Compliant sessions on this date")
    compliance_rate: float = Field(ge=0, le=100, description="Compliance rate percentage")
    
    class Config:
        json_schema_extra = {
            "example": {
                "date": "2026-01-10",
                "total_sessions": 142,
                "compliant_sessions": 127,
                "compliance_rate": 89.4
            }
        }


class MostMissedStep(BaseModel):
    """Most frequently missed WHO step."""
    step_id: int = Field(ge=2, le=7, description="WHO step identifier (2-7)")
    step_name: str = Field(description="Human-readable step name")
    missed_count: int = Field(ge=0, description="Number of times this step was missed")
    miss_rate: float = Field(ge=0, le=100, description="Miss rate percentage")
    
    class Config:
        json_schema_extra = {
            "example": {
                "step_id": 3,
                "step_name": "Right/Left palm over dorsum",
                "missed_count": 45,
                "miss_rate": 8.2
            }
        }


class AverageStepTime(BaseModel):
    """Average duration for a WHO step."""
    step_id: int = Field(ge=2, le=7, description="WHO step identifier (2-7)")
    step_name: str = Field(description="Human-readable step name")
    avg_duration_ms: float = Field(ge=0, description="Average duration in milliseconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "step_id": 2,
                "step_name": "Palm to palm",
                "avg_duration_ms": 8250.5
            }
        }


class DeviceSummary(BaseModel):
    """Summary of device operational status."""
    total_devices: int = Field(ge=0, description="Total number of devices")
    online_devices: int = Field(ge=0, description="Devices online in last hour")
    offline_devices: int = Field(ge=0, description="Devices offline for >1 hour")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_devices": 20,
                "online_devices": 18,
                "offline_devices": 2
            }
        }


class OverviewResponse(BaseModel):
    """Organization-wide analytics overview response."""
    compliance_trend: List[ComplianceTrendItem] = Field(description="Daily compliance trend over date range")
    most_missed_step: Optional[MostMissedStep] = Field(None, description="Most frequently missed step")
    average_wash_time_ms: float = Field(ge=0, description="Average total session duration in milliseconds")
    average_step_times: List[AverageStepTime] = Field(description="Average duration per step")
    quality_rate: float = Field(ge=0, le=100, description="Percentage of non-low-quality sessions")
    device_summary: DeviceSummary = Field(description="Device operational status summary")
    
    class Config:
        json_schema_extra = {
            "example": {
                "compliance_trend": [
                    {"date": "2026-01-10", "total_sessions": 142, "compliant_sessions": 127, "compliance_rate": 89.4}
                ],
                "most_missed_step": {
                    "step_id": 3,
                    "step_name": "Right/Left palm over dorsum",
                    "missed_count": 45,
                    "miss_rate": 8.2
                },
                "average_wash_time_ms": 42350.5,
                "average_step_times": [
                    {"step_id": 2, "step_name": "Palm to palm", "avg_duration_ms": 8250.5}
                ],
                "quality_rate": 93.5,
                "device_summary": {
                    "total_devices": 20,
                    "online_devices": 18,
                    "offline_devices": 2
                }
            }
        }


class DeviceLeaderboardItem(BaseModel):
    """Device performance ranking item for unit leaderboard."""
    rank: int = Field(ge=1, description="Device rank by compliance rate")
    device_id: str = Field(description="Device UUID")
    device_name: str = Field(description="Human-readable device name")
    compliance_rate: float = Field(ge=0, le=100, description="Compliance rate percentage for date range")
    total_sessions: int = Field(ge=0, description="Total sessions recorded in date range")
    compliant_sessions: int = Field(ge=0, description="Compliant sessions in date range")
    
    class Config:
        json_schema_extra = {
            "example": {
                "rank": 1,
                "device_id": "550e8400-e29b-41d4-a716-446655440000",
                "device_name": "ICU-Device-01",
                "compliance_rate": 95.2,
                "total_sessions": 156,
                "compliant_sessions": 148
            }
        }


class UnitMetrics(BaseModel):
    """Unit-scoped performance metrics."""
    unit_id: str = Field(description="Unit UUID")
    unit_name: str = Field(description="Human-readable unit name")
    unit_code: str = Field(description="Short unit code")
    compliance_trend: List[ComplianceTrendItem] = Field(description="Daily compliance trend for unit")
    most_missed_step: Optional[MostMissedStep] = Field(None, description="Most frequently missed step in unit")
    average_wash_time_ms: float = Field(ge=0, description="Average session duration in milliseconds")
    average_step_times: List[AverageStepTime] = Field(description="Average duration per step in unit")
    quality_rate: float = Field(ge=0, le=100, description="Percentage of non-low-quality sessions")
    
    class Config:
        json_schema_extra = {
            "example": {
                "unit_id": "660e8400-e29b-41d4-a716-446655440000",
                "unit_name": "Intensive Care Unit",
                "unit_code": "ICU",
                "compliance_trend": [
                    {"date": "2026-01-10", "total_sessions": 42, "compliant_sessions": 39, "compliance_rate": 92.9}
                ],
                "most_missed_step": {
                    "step_id": 5,
                    "step_name": "Backs of fingers",
                    "missed_count": 12,
                    "miss_rate": 7.1
                },
                "average_wash_time_ms": 43500.0,
                "average_step_times": [
                    {"step_id": 2, "step_name": "Palm to palm", "avg_duration_ms": 8500.0}
                ],
                "quality_rate": 94.2
            }
        }


class UnitResponse(BaseModel):
    """Unit analytics response with metrics and device leaderboard."""
    metrics: UnitMetrics = Field(description="Unit-scoped performance metrics")
    device_leaderboard: List[DeviceLeaderboardItem] = Field(description="Device rankings by compliance rate")
    
    class Config:
        json_schema_extra = {
            "example": {
                "metrics": {
                    "unit_id": "660e8400-e29b-41d4-a716-446655440000",
                    "unit_name": "Intensive Care Unit",
                    "unit_code": "ICU",
                    "compliance_trend": [
                        {"date": "2026-01-10", "total_sessions": 42, "compliant_sessions": 39, "compliance_rate": 92.9}
                    ],
                    "most_missed_step": {
                        "step_id": 5,
                        "step_name": "Backs of fingers",
                        "missed_count": 12,
                        "miss_rate": 7.1
                    },
                    "average_wash_time_ms": 43500.0,
                    "average_step_times": [
                        {"step_id": 2, "step_name": "Palm to palm", "avg_duration_ms": 8500.0}
                    ],
                    "quality_rate": 94.2
                },
                "device_leaderboard": [
                    {
                        "rank": 1,
                        "device_id": "550e8400-e29b-41d4-a716-446655440000",
                        "device_name": "ICU-Device-01",
                        "compliance_rate": 95.2,
                        "total_sessions": 156,
                        "compliant_sessions": 148
                    }
                ]
            }
        }


class ReliabilityFlag(BaseModel):
    """Device reliability warning flag."""
    severity: str = Field(description="Warning severity: 'critical', 'warning', 'info'")
    message: str = Field(description="Human-readable warning message")
    timestamp: Optional[datetime] = Field(None, description="When the flag was detected")
    
    class Config:
        json_schema_extra = {
            "example": {
                "severity": "critical",
                "message": "Device offline for more than 1 hour (last seen: 2026-01-10 14:30:00)",
                "timestamp": "2026-01-10T15:45:00"
            }
        }


class DeviceStatus(BaseModel):
    """Device operational status metrics."""
    device_id: str = Field(description="Device UUID")
    device_name: str = Field(description="Human-readable device name")
    unit_id: str = Field(description="Unit UUID where device is installed")
    unit_name: str = Field(description="Unit name")
    is_online: bool = Field(description="True if heartbeat received in last hour")
    last_seen: Optional[datetime] = Field(None, description="Timestamp of last heartbeat")
    heartbeats_24h: int = Field(ge=0, description="Number of heartbeats in last 24 hours")
    expected_heartbeats_24h: int = Field(ge=0, description="Expected heartbeats (288 = 24h * 12 per hour)")
    heartbeat_rate: float = Field(ge=0, le=100, description="Percentage of expected heartbeats received")
    uptime_percentage: float = Field(ge=0, le=100, description="Uptime percentage in date range")
    firmware_version: str = Field(description="Current firmware version")
    installation_date: date = Field(description="Date device was installed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "device_id": "550e8400-e29b-41d4-a716-446655440000",
                "device_name": "ICU-Device-01",
                "unit_id": "660e8400-e29b-41d4-a716-446655440000",
                "unit_name": "Intensive Care Unit",
                "is_online": True,
                "last_seen": "2026-01-10T15:30:00",
                "heartbeats_24h": 275,
                "expected_heartbeats_24h": 288,
                "heartbeat_rate": 95.5,
                "uptime_percentage": 98.2,
                "firmware_version": "v2.1.0",
                "installation_date": "2026-01-10"
            }
        }


class DevicePerformance(BaseModel):
    """Device handwashing performance metrics."""
    total_sessions: int = Field(ge=0, description="Total sessions recorded in date range")
    compliant_sessions: int = Field(ge=0, description="Compliant sessions in date range")
    compliance_rate: float = Field(ge=0, le=100, description="Compliance rate percentage")
    average_wash_time_ms: float = Field(ge=0, description="Average session duration")
    low_quality_sessions: int = Field(ge=0, description="Number of low-quality flagged sessions")
    quality_rate: float = Field(ge=0, le=100, description="Percentage of non-low-quality sessions")
    most_missed_step: Optional[MostMissedStep] = Field(None, description="Most frequently missed step")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_sessions": 156,
                "compliant_sessions": 148,
                "compliance_rate": 94.9,
                "average_wash_time_ms": 42850.5,
                "low_quality_sessions": 8,
                "quality_rate": 94.9,
                "most_missed_step": {
                    "step_id": 4,
                    "step_name": "Interlaced fingers",
                    "missed_count": 8,
                    "miss_rate": 5.1
                }
            }
        }


class DeviceResponse(BaseModel):
    """Device analytics response with status, performance, and reliability flags."""
    status: DeviceStatus = Field(description="Device operational status")
    performance: DevicePerformance = Field(description="Device handwashing performance metrics")
    reliability_flags: List[ReliabilityFlag] = Field(default=[], description="Active reliability warnings")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": {
                    "device_id": "550e8400-e29b-41d4-a716-446655440000",
                    "device_name": "ICU-Device-01",
                    "unit_id": "660e8400-e29b-41d4-a716-446655440000",
                    "unit_name": "Intensive Care Unit",
                    "is_online": True,
                    "last_seen": "2026-01-10T15:30:00",
                    "heartbeats_24h": 275,
                    "expected_heartbeats_24h": 288,
                    "heartbeat_rate": 95.5,
                    "uptime_percentage": 98.2,
                    "firmware_version": "v2.1.0",
                    "installation_date": "2026-01-10"
                },
                "performance": {
                    "total_sessions": 156,
                    "compliant_sessions": 148,
                    "compliance_rate": 94.9,
                    "average_wash_time_ms": 42850.5,
                    "low_quality_sessions": 8,
                    "quality_rate": 94.9,
                    "most_missed_step": {
                        "step_id": 4,
                        "step_name": "Interlaced fingers",
                        "missed_count": 8,
                        "miss_rate": 5.1
                    }
                },
                "reliability_flags": [
                    {
                        "severity": "warning",
                        "message": "Heartbeat rate below 80% (95.5%)",
                        "timestamp": "2026-01-10T15:45:00"
                    }
                ]
            }
        }
