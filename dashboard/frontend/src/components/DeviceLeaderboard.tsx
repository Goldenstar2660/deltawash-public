/**
 * DeviceLeaderboard component.
 * 
 * Displays a ranked table of devices by compliance rate with visual indicators.
 */
import React from 'react';
import { DeviceLeaderboardItem } from '../types/analytics';
import './DeviceLeaderboard.css';

interface DeviceLeaderboardProps {
  devices: DeviceLeaderboardItem[];
  onDeviceClick?: (deviceId: string) => void;
}

export const DeviceLeaderboard: React.FC<DeviceLeaderboardProps> = ({
  devices,
  onDeviceClick,
}) => {
  if (devices.length === 0) {
    return (
      <div className="device-leaderboard empty">
        <p>No device data available for the selected date range.</p>
      </div>
    );
  }

  const getRankBadgeClass = (rank: number): string => {
    if (rank === 1) return 'rank-badge gold';
    if (rank === 2) return 'rank-badge silver';
    if (rank === 3) return 'rank-badge bronze';
    return 'rank-badge';
  };

  const getComplianceClass = (rate: number): string => {
    if (rate >= 95) return 'compliance-excellent';
    if (rate >= 90) return 'compliance-good';
    if (rate >= 80) return 'compliance-fair';
    return 'compliance-poor';
  };

  return (
    <div className="device-leaderboard">
      <h3>Device Performance Leaderboard</h3>
      <table className="leaderboard-table">
        <thead>
          <tr>
            <th className="rank-column">Rank</th>
            <th className="device-column">Device</th>
            <th className="compliance-column">Compliance Rate</th>
            <th className="sessions-column">Sessions</th>
            <th className="compliant-column">Compliant</th>
          </tr>
        </thead>
        <tbody>
          {devices.map((device) => (
            <tr
              key={device.device_id}
              className={onDeviceClick ? 'clickable' : ''}
              onClick={() => onDeviceClick?.(device.device_id)}
            >
              <td className="rank-column">
                <span className={getRankBadgeClass(device.rank)}>
                  {device.rank}
                </span>
              </td>
              <td className="device-column">
                <span className="device-name">{device.device_name}</span>
              </td>
              <td className="compliance-column">
                <div className="compliance-cell">
                  <span className={`compliance-rate ${getComplianceClass(device.compliance_rate)}`}>
                    {device.compliance_rate.toFixed(1)}%
                  </span>
                  <div className="compliance-bar-container">
                    {/* eslint-disable-next-line react/forbid-dom-props */}
                    <div
                      className={`compliance-bar ${getComplianceClass(device.compliance_rate)}`}
                      style={{ width: `${device.compliance_rate}%` }}
                    />
                  </div>
                </div>
              </td>
              <td className="sessions-column">
                {device.total_sessions}
              </td>
              <td className="compliant-column">
                {device.compliant_sessions}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
