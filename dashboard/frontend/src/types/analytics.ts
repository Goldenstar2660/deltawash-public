/**
 * Analytics API types.
 * 
 * Matches backend Pydantic schemas for type safety across frontend/backend.
 */

export interface ComplianceTrendItem {
  date: string; // ISO date string: YYYY-MM-DD
  total_sessions: number;
  compliant_sessions: number;
  compliance_rate: number; // 0-100
}

export interface MostMissedStep {
  step_id: number; // 2-7
  step_name: string;
  missed_count: number;
  miss_rate: number; // 0-100
}

export interface AverageStepTime {
  step_id: number; // 2-7
  step_name: string;
  avg_duration_ms: number;
}

export interface DeviceSummary {
  total_devices: number;
  online_devices: number;
  offline_devices: number;
}

export interface OverviewResponse {
  compliance_trend: ComplianceTrendItem[];
  most_missed_step: MostMissedStep | null;
  average_wash_time_ms: number;
  average_step_times: AverageStepTime[];
  quality_rate: number; // 0-100
  device_summary: DeviceSummary;
}

/**
 * Query parameters for analytics endpoints.
 */
export interface AnalyticsQueryParams {
  date_from: string; // ISO date: YYYY-MM-DD
  date_to: string; // ISO date: YYYY-MM-DD
  unit_id?: string; // UUID
  shift?: 'morning' | 'afternoon' | 'night';
  exclude_low_quality?: boolean;
}

/**
 * Filter state for dashboard.
 */
export interface FilterState {
  dateFrom: Date;
  dateTo: Date;
  unitId?: string;
  shift?: 'morning' | 'afternoon' | 'night';
  excludeLowQuality: boolean;
}

/**
 * Device leaderboard item for unit analytics.
 */
export interface DeviceLeaderboardItem {
  rank: number;
  device_id: string; // UUID
  device_name: string;
  compliance_rate: number; // 0-100
  total_sessions: number;
  compliant_sessions: number;
}

/**
 * Unit-scoped performance metrics.
 */
export interface UnitMetrics {
  unit_id: string; // UUID
  unit_name: string;
  unit_code: string;
  compliance_trend: ComplianceTrendItem[];
  most_missed_step: MostMissedStep | null;
  average_wash_time_ms: number;
  average_step_times: AverageStepTime[];
  quality_rate: number; // 0-100
}

/**
 * Unit analytics response with metrics and device leaderboard.
 */
export interface UnitResponse {
  metrics: UnitMetrics;
  device_leaderboard: DeviceLeaderboardItem[];
}

