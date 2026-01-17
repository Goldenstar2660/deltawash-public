/**
 * DevicePage component.
 * 
 * Displays device health monitoring with operational status, performance metrics,
 * and reliability warnings.
 */
import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useDeviceDetail, useDeviceAnalytics } from '../hooks/useDevices';
import { useFilters } from '../context/FilterContext';
import { DeviceStatusCard } from '../components/DeviceStatusCard';
import { ReliabilityFlags } from '../components/ReliabilityFlags';
import { MetricCard } from '../components/common/MetricCard';
import api from '../services/api';
import './DevicePage.css';

export const DevicePage: React.FC = () => {
  const { deviceId } = useParams<{ deviceId: string }>();
  const navigate = useNavigate();
  const { filters } = useFilters();

  // Convert dates to ISO strings for API
  const dateFrom = filters.dateFrom.toISOString().split('T')[0];
  const dateTo = filters.dateTo.toISOString().split('T')[0];

  const handleSimulate = async (label: string) => {
    try {
      await api.post('/live/update', { label });
    } catch (e) {
      console.error("Failed to update state", e);
    }
  };

  // Fetch device detail
  const {
    data: deviceDetail,
    isLoading: isLoadingDetail,
    error: errorDetail,
  } = useDeviceDetail(deviceId || '');

  // Fetch device analytics
  const {
    data: analytics,
    isLoading: isLoadingAnalytics,
    error: errorAnalytics,
  } = useDeviceAnalytics(deviceId || '', dateFrom, dateTo);

  // Loading state
  if (isLoadingDetail || isLoadingAnalytics) {
    return (
      <div className="device-page">
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <span className="text-secondary">Loading device data...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (errorDetail || errorAnalytics) {
    return (
      <div className="device-page">
        <div className="error-state">
          <h3>Error Loading Device</h3>
          <p>{(errorDetail || errorAnalytics)?.message || 'An error occurred while loading device data'}</p>
        </div>
      </div>
    );
  }

  // No data state
  if (!deviceDetail || !analytics) {
    return (
      <div className="device-page">
        <div className="empty-state">
          <p>Device not found</p>
        </div>
      </div>
    );
  }

  const { performance } = analytics;

  return (
    <div className="device-page">
      {/* Page Header */}
      <header className="page-header">
        <div className="header-content">
          <div className="header-title">
            <button className="back-link" onClick={() => navigate(-1)}>
              ← Back
            </button>
            <h1>{deviceDetail.device_name}</h1>
            <p className="page-subtitle">
              {deviceDetail.unit_name} ({deviceDetail.unit_code})
            </p>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="main-content">
        {/* Device Status Card */}
        <div className="content-section">
          <DeviceStatusCard status={analytics.status} />
        </div>

        {/* Reliability Flags */}
        <div className="content-section">
          <ReliabilityFlags flags={analytics.reliability_flags} />
        </div>

        {/* Live View */}
        <div className="content-section">
          <h2 className="section-title">Live View</h2>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem', background: '#fff', padding: '1rem', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
            <img 
                src={`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/live/stream`}
                alt="Live Wash Visualization"
                style={{ maxWidth: '100%', maxHeight: '400px', border: '1px solid #eee', borderRadius: '4px' }} 
            />
            <div className="simulation-controls" style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', justifyContent: 'center' }}>
                {['palm', 'dorsum', 'thumbs', 'fingertips', 'interlaced', 'interlocked'].map(label => (
                  <button 
                    key={label}
                    onClick={() => handleSimulate(label)}
                    style={{ padding: '0.5rem 1rem', cursor: 'pointer', borderRadius: '4px', border: '1px solid #ccc', background: '#f8f9fa' }}
                  >
                    {label.charAt(0).toUpperCase() + label.slice(1)}
                  </button>
                ))}
                <button 
                  onClick={() => handleSimulate('background')} 
                  style={{ padding: '0.5rem 1rem', cursor: 'pointer', borderRadius: '4px', border: '1px solid #dc3545', background: '#dc3545', color: 'white' }}
                >
                  Reset (Wait 5s)
                </button>
            </div>
            <p style={{ fontSize: '0.8rem', color: '#666' }}>
              Click buttons to simulate detection. Reset clears after 5s of "background".
            </p>
          </div>
        </div>

        {/* Performance Metrics */}
        <div className="content-section">
          <h2 className="section-title">Performance Metrics</h2>
          <div className="metrics-grid">
            <MetricCard
              label="Total Sessions"
              value={performance.total_sessions.toLocaleString()}
              unit=""
            />
            
            <MetricCard
              label="Compliance Rate"
              value={performance.compliance_rate.toFixed(1)}
              unit="%"
            />
            
            <MetricCard
              label="Average Wash Time"
              value={(performance.average_wash_time_ms / 1000).toFixed(1)}
              unit="s"
            />
            
            <MetricCard
              label="Quality Rate"
              value={performance.quality_rate.toFixed(1)}
              unit="%"
            />
          </div>
        </div>

        {/* Most Missed Step */}
        {performance.most_missed_step && (
          <div className="content-section">
            <div className="missed-step-card">
              <h3>Most Missed Step</h3>
              <div className="missed-step-content">
                <div className="missed-step-info">
                  <span className="missed-step-label">Step {performance.most_missed_step.step_id}</span>
                  <span className="missed-step-name">{performance.most_missed_step.step_name}</span>
                </div>
                <div className="missed-step-stats">
                  <div className="miss-rate">
                    {performance.most_missed_step.miss_rate.toFixed(1)}%
                  </div>
                  <div className="miss-count">
                    {performance.most_missed_step.missed_count} times
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Device Details */}
        <div className="content-section">
          <div className="info-card">
            <h3>Device Information</h3>
            <div className="info-grid">
              <div className="info-item">
                <span className="info-label">Device ID</span>
                <span className="info-value mono">{deviceDetail.device_id}</span>
              </div>
              
              <div className="info-item">
                <span className="info-label">Total Sessions (All Time)</span>
                <span className="info-value large">{deviceDetail.total_sessions_all_time.toLocaleString()}</span>
              </div>
              
              <div className="info-item">
                <span className="info-label">Created</span>
                <span className="info-value">{new Date(deviceDetail.created_at).toLocaleString()}</span>
              </div>
              
              <div className="info-item">
                <span className="info-label">Last Updated</span>
                <span className="info-value">{new Date(deviceDetail.updated_at).toLocaleString()}</span>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};
