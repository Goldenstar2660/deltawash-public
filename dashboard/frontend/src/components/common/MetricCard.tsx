/**
 * MetricCard component for displaying key metrics.
 * TailAdmin-style design with icon headers and clean typography.
 */
import React from 'react';

interface MetricCardProps {
  label: string;
  value: string | number;
  unit?: string;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  icon?: React.ReactNode;
}

export function MetricCard({ label, value, unit, trend, icon }: MetricCardProps) {
  return (
    <div className="metric-card">
      {/* Icon Header - TailAdmin Style */}
      <div className="metric-header">
        {icon ? icon : (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" fill="currentColor"/>
          </svg>
        )}
      </div>
      {/* Label */}
      <p className="metric-label">{label}</p>
      {/* Value with Unit */}
      <div className="metric-value">
        <span className="value">{value}</span>
        {unit && <span className="unit">{unit}</span>}
      </div>
      {/* Optional Trend Badge */}
      {trend && (
        <div className={`metric-trend ${trend.isPositive ? 'positive' : 'negative'}`}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
            {trend.isPositive ? (
              <path d="M6 2.5L10 6.5H7V9.5H5V6.5H2L6 2.5Z" fill="currentColor"/>
            ) : (
              <path d="M6 9.5L2 5.5H5V2.5H7V5.5H10L6 9.5Z" fill="currentColor"/>
            )}
          </svg>
          <span>{Math.abs(trend.value).toFixed(1)}%</span>
        </div>
      )}
    </div>
  );
}
