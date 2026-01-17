/**
 * Analytics API client.
 * 
 * Provides functions for fetching analytics data from the backend.
 */
import api from './api';
import { OverviewResponse, AnalyticsQueryParams, UnitResponse } from '../types/analytics';

/**
 * Fetch organization-wide or unit-scoped analytics overview.
 * 
 * @param params Query parameters for filtering analytics
 * @returns Promise with analytics data
 */
export async function fetchOverviewAnalytics(
  params: AnalyticsQueryParams
): Promise<OverviewResponse> {
  const response = await api.get<OverviewResponse>('/analytics/overview', {
    params: {
      date_from: params.date_from,
      date_to: params.date_to,
      unit_id: params.unit_id,
      shift: params.shift,
      exclude_low_quality: params.exclude_low_quality,
    },
  });
  
  return response.data;
}

/**
 * Helper to convert Date objects to ISO date strings (YYYY-MM-DD).
 */
export function formatDateForAPI(date: Date): string {
  return date.toISOString().split('T')[0];
}

/**
 * Fetch unit-scoped analytics with device leaderboard.
 * 
 * @param unitId Unit UUID to fetch analytics for
 * @param params Query parameters for filtering analytics
 * @returns Promise with unit analytics data
 */
export async function fetchUnitAnalytics(
  unitId: string,
  params: Omit<AnalyticsQueryParams, 'unit_id'>
): Promise<UnitResponse> {
  const response = await api.get<UnitResponse>(`/analytics/unit/${unitId}`, {
    params: {
      date_from: params.date_from,
      date_to: params.date_to,
      shift: params.shift,
      exclude_low_quality: params.exclude_low_quality,
    },
  });
  
  return response.data;
}

