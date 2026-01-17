/**
 * React Query hooks for analytics data.
 */
import { useQuery, UseQueryResult } from '@tanstack/react-query';
import { fetchOverviewAnalytics, fetchUnitAnalytics, formatDateForAPI } from '../services/analyticsApi';
import { OverviewResponse, FilterState, UnitResponse } from '../types/analytics';

/**
 * Hook to fetch overview analytics with React Query.
 * 
 * @param filters Current filter state
 * @returns Query result with analytics data
 */
export function useOverviewAnalytics(
  filters: FilterState
): UseQueryResult<OverviewResponse, Error> {
  return useQuery({
    queryKey: [
      'analytics',
      'overview',
      formatDateForAPI(filters.dateFrom),
      formatDateForAPI(filters.dateTo),
      filters.unitId,
      filters.shift,
      filters.excludeLowQuality,
    ],
    queryFn: () =>
      fetchOverviewAnalytics({
        date_from: formatDateForAPI(filters.dateFrom),
        date_to: formatDateForAPI(filters.dateTo),
        unit_id: filters.unitId,
        shift: filters.shift,
        exclude_low_quality: filters.excludeLowQuality,
      }),
    staleTime: 30000, // Consider data fresh for 30 seconds
    retry: 2,
  });
}

/**
 * Hook to fetch unit-scoped analytics with device leaderboard.
 * 
 * @param unitId Unit UUID to fetch analytics for
 * @param filters Current filter state (excluding unitId)
 * @returns Query result with unit analytics data
 */
export function useUnitAnalytics(
  unitId: string,
  filters: Omit<FilterState, 'unitId'>
): UseQueryResult<UnitResponse, Error> {
  return useQuery({
    queryKey: [
      'analytics',
      'unit',
      unitId,
      formatDateForAPI(filters.dateFrom),
      formatDateForAPI(filters.dateTo),
      filters.shift,
      filters.excludeLowQuality,
    ],
    queryFn: () =>
      fetchUnitAnalytics(unitId, {
        date_from: formatDateForAPI(filters.dateFrom),
        date_to: formatDateForAPI(filters.dateTo),
        shift: filters.shift,
        exclude_low_quality: filters.excludeLowQuality,
      }),
    staleTime: 30000, // Consider data fresh for 30 seconds
    retry: 2,
    enabled: !!unitId, // Only fetch if unitId is provided
  });
}

