/**
 * Devices API client.
 * 
 * Provides functions to fetch device data from the backend.
 */
import api from './api';
import { DeviceListItem, DeviceDetail, DeviceResponse } from '../types/device';

/**
 * Fetch all devices with basic info and online status.
 */
export const fetchDevices = async (): Promise<DeviceListItem[]> => {
  const response = await api.get<DeviceListItem[]>('/devices/');
  return response.data;
};

/**
 * Fetch detailed information for a specific device.
 */
export const fetchDeviceDetail = async (deviceId: string): Promise<DeviceDetail> => {
  const response = await api.get<DeviceDetail>(`/devices/${deviceId}`);
  return response.data;
};

/**
 * Fetch device analytics with status, performance, and reliability flags.
 */
export const fetchDeviceAnalytics = async (
  deviceId: string,
  dateFrom: string,
  dateTo: string
): Promise<DeviceResponse> => {
  const response = await api.get<DeviceResponse>(`/analytics/device/${deviceId}`, {
    params: {
      date_from: dateFrom,
      date_to: dateTo,
    },
  });
  return response.data;
};
