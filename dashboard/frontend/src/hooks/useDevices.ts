/**
 * React Query hooks for device data.
 * 
 * Provides hooks for fetching device lists, device details, and device analytics.
 */
import { useQuery, UseQueryResult } from '@tanstack/react-query';
import { fetchDevices, fetchDeviceDetail, fetchDeviceAnalytics } from '../services/devicesApi';
import { DeviceListItem, DeviceDetail, DeviceResponse } from '../types/device';

/**
 * Hook to fetch all devices.
 * 
 * Refetches every 60 seconds to keep online status current.
 */
export const useDevices = (): UseQueryResult<DeviceListItem[], Error> => {
  return useQuery({
    queryKey: ['devices'],
    queryFn: fetchDevices,
    staleTime: 60000, // 60 seconds
    refetchInterval: 60000, // Refresh every 60 seconds for online status
  });
};

/**
 * Hook to fetch device detail.
 */
export const useDeviceDetail = (deviceId: string): UseQueryResult<DeviceDetail, Error> => {
  return useQuery({
    queryKey: ['device', deviceId],
    queryFn: () => fetchDeviceDetail(deviceId),
    staleTime: 60000, // 60 seconds
    enabled: !!deviceId,
  });
};

/**
 * Hook to fetch device analytics.
 */
export const useDeviceAnalytics = (
  deviceId: string,
  dateFrom: string,
  dateTo: string
): UseQueryResult<DeviceResponse, Error> => {
  return useQuery({
    queryKey: ['device-analytics', deviceId, dateFrom, dateTo],
    queryFn: () => fetchDeviceAnalytics(deviceId, dateFrom, dateTo),
    staleTime: 30000, // 30 seconds
    enabled: !!deviceId && !!dateFrom && !!dateTo,
  });
};
