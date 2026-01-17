/**
 * TypeScript types for device analytics and device data.
 * 
 * Matches backend Pydantic schemas for device endpoints.
 */

export interface ReliabilityFlag {
  severity: 'critical' | 'warning' | 'info';
  message: string;
  timestamp?: string;
}

export interface DeviceStatus {
  device_id: string;
  device_name: string;
  unit_id: string;
  unit_name: string;
  is_online: boolean;
  last_seen?: string;
  heartbeats_24h: number;
  expected_heartbeats_24h: number;
  heartbeat_rate: number;
  uptime_percentage: number;
  firmware_version: string;
  installation_date: string;
}

export interface MostMissedStep {
  step_id: number;
  step_name: string;
  missed_count: number;
  miss_rate: number;
}

export interface DevicePerformance {
  total_sessions: number;
  compliant_sessions: number;
  compliance_rate: number;
  average_wash_time_ms: number;
  low_quality_sessions: number;
  quality_rate: number;
  most_missed_step?: MostMissedStep;
}

export interface DeviceResponse {
  status: DeviceStatus;
  performance: DevicePerformance;
  reliability_flags: ReliabilityFlag[];
}

export interface DeviceListItem {
  device_id: string;
  device_name: string;
  unit_id: string;
  unit_name: string;
  firmware_version: string;
  installation_date: string;
  is_online: boolean;
  last_seen?: string;
}

export interface DeviceDetail {
  device_id: string;
  device_name: string;
  unit_id: string;
  unit_name: string;
  unit_code: string;
  firmware_version: string;
  installation_date: string;
  created_at: string;
  updated_at: string;
  is_online: boolean;
  last_seen?: string;
  total_sessions_all_time: number;
}
