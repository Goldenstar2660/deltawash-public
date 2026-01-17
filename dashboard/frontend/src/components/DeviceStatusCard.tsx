/**
 * DeviceStatusCard component.
 * 
 * Displays device operational status including online status, heartbeat metrics,
 * and uptime percentage. TailAdmin-styled design.
 */
import React from 'react';
import { DeviceStatus } from '../types/device';

interface DeviceStatusCardProps {
  status: DeviceStatus;
}

export const DeviceStatusCard: React.FC<DeviceStatusCardProps> = ({ status }) => {
  const formatDateTime = (dateTime?: string): string => {
    if (!dateTime) return 'Never';
    const date = new Date(dateTime);
    return date.toLocaleString();
  };

  const getStatusBadgeClass = (isOnline: boolean): string => {
    return isOnline 
      ? 'badge-success' 
      : 'badge-danger';
  };

  const getHeartbeatRateColor = (rate: number): string => {
    if (rate >= 90) return 'text-success';
    if (rate >= 80) return 'text-warning';
    return 'text-danger';
  };

  const getUptimeColor = (percentage: number): string => {
    if (percentage >= 95) return 'text-success';
    if (percentage >= 90) return 'text-warning';
    return 'text-danger';
  };

  return (
    <div className="info-card">
      <h3>Device Status</h3>
      
      <div className="info-grid">
        {/* Device Info */}
        <div className="info-item">
          <span className="info-label">Device Name</span>
          <span className="info-value large">{status.device_name}</span>
        </div>
        
        <div className="info-item">
          <span className="info-label">Unit</span>
          <span className="info-value large">{status.unit_name}</span>
        </div>
        
        {/* Online Status */}
        <div className="info-item">
          <span className="info-label">Status</span>
          <span className={`badge ${getStatusBadgeClass(status.is_online)}`}>
            {status.is_online ? 'Online' : 'Offline'}
          </span>
        </div>
        
        <div className="info-item">
          <span className="info-label">Last Seen</span>
          <span className="info-value">{formatDateTime(status.last_seen)}</span>
        </div>
        
        {/* Heartbeat Metrics */}
        <div className="info-item">
          <span className="info-label">Heartbeats (24h)</span>
          <span className="info-value large">
            {status.heartbeats_24h} / {status.expected_heartbeats_24h}
          </span>
        </div>
        
        <div className="info-item">
          <span className="info-label">Heartbeat Rate</span>
          <span className={`info-value large ${getHeartbeatRateColor(status.heartbeat_rate)}`}>
            {status.heartbeat_rate.toFixed(1)}%
          </span>
        </div>
        
        {/* Uptime */}
        <div className="info-item">
          <span className="info-label">Uptime</span>
          <span className={`info-value large ${getUptimeColor(status.uptime_percentage)}`}>
            {status.uptime_percentage.toFixed(1)}%
          </span>
        </div>
        
        {/* Firmware */}
        <div className="info-item">
          <span className="info-label">Firmware Version</span>
          <span className="info-value mono">{status.firmware_version}</span>
        </div>
        
        {/* Installation Date */}
        <div className="info-item">
          <span className="info-label">Installation Date</span>
          <span className="info-value">{new Date(status.installation_date).toLocaleDateString()}</span>
        </div>
      </div>
    </div>
  );
};
