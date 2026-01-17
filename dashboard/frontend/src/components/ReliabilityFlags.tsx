/**
 * ReliabilityFlags component.
 * 
 * Displays device reliability warnings with severity-based colors.
 * TailAdmin-styled design matching admin dashboard patterns.
 */
import React from 'react';
import { ReliabilityFlag } from '../types/device';

interface ReliabilityFlagsProps {
  flags: ReliabilityFlag[];
}

export const ReliabilityFlags: React.FC<ReliabilityFlagsProps> = ({ flags }) => {
  if (flags.length === 0) {
    return (
      <div className="info-card">
        <h3>Reliability Status</h3>
        <div className="badge badge-success" style={{ marginTop: 'var(--space-4)' }}>
          <span className="status-dot" style={{ background: 'var(--color-success-500)' }}></span>
          All systems operational
        </div>
      </div>
    );
  }

  const getSeverityBadgeClass = (severity: string): string => {
    switch (severity) {
      case 'critical':
        return 'badge-danger';
      case 'warning':
        return 'badge-warning';
      case 'info':
        return 'badge-info';
      default:
        return 'badge-neutral';
    }
  };

  const getSeverityIcon = (severity: string): React.ReactNode => {
    switch (severity) {
      case 'critical':
        return (
          <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
        );
      case 'warning':
        return (
          <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
        );
      case 'info':
        return (
          <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
          </svg>
        );
      default:
        return null;
    }
  };

  return (
    <div className="info-card">
      <h3>Reliability Status</h3>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)', marginTop: 'var(--space-4)' }}>
        {flags.map((flag, index) => (
          <div
            key={index}
            className="error-message"
            style={{
              background: flag.severity === 'critical' ? 'var(--color-error-50)' : 
                         flag.severity === 'warning' ? 'var(--color-warning-50)' : 
                         'var(--color-info-50)',
              borderColor: flag.severity === 'critical' ? 'var(--color-error-100)' : 
                          flag.severity === 'warning' ? 'var(--color-warning-100)' : 
                          'var(--color-info-50)',
              color: flag.severity === 'critical' ? 'var(--color-error-600)' : 
                     flag.severity === 'warning' ? 'var(--color-warning-600)' : 
                     'var(--color-info-500)'
            }}
          >
            <div style={{ flexShrink: 0 }}>
              {getSeverityIcon(flag.severity)}
            </div>
            
            <div style={{ flex: 1 }}>
              <div style={{ marginBottom: 'var(--space-1)' }}>
                <span className={`badge ${getSeverityBadgeClass(flag.severity)}`} style={{ textTransform: 'uppercase' }}>
                  {flag.severity}
                </span>
              </div>
              
              <p style={{ fontSize: 'var(--text-theme-sm)', margin: 0 }}>{flag.message}</p>
              
              {flag.timestamp && (
                <p style={{ fontSize: 'var(--text-theme-xs)', marginTop: 'var(--space-1)', opacity: 0.75 }}>
                  Detected: {new Date(flag.timestamp).toLocaleString()}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
