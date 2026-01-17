/**
 * OverviewPage - Main dashboard page showing organization-wide analytics.
 * 
 * Displays compliance trends, device status, step analysis, and quality metrics.
 */
import { useFilters } from '../context/FilterContext';
import { useOverviewAnalytics } from '../hooks/useAnalytics';
import { MetricCard } from '../components/common/MetricCard';
import { DeviceStatusBadge } from '../components/common/DeviceStatusBadge';
import { ErrorMessage } from '../components/common/ErrorMessage';
import { Filters } from '../components/filters/Filters';
import { ComplianceTrendChart } from '../components/charts/ComplianceTrendChart';
import { StepBarChart } from '../components/charts/StepBarChart';
import { TimingChart } from '../components/charts/TimingChart';
import './OverviewPage.css';
import '../components/charts/Charts.css';

export function OverviewPage() {
  const { filters } = useFilters();
  const { data, isLoading, isError, error, refetch } = useOverviewAnalytics(filters);

  // Loading state
  if (isLoading) {
    return (
      <div className="overview-page">
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <span className="loading-text">Loading analytics data...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="overview-page">
        <ErrorMessage
          message={error?.message || 'Failed to load analytics data'}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  // Empty state
  if (!data || data.compliance_trend.length === 0) {
    return (
      <div className="overview-page">
        <header className="page-header">
          <div className="header-content">
            <div className="header-title">
              <h1>DeltaWash Compliance Dashboard</h1>
              <p className="page-subtitle">Real-time handwashing compliance monitoring</p>
            </div>
          </div>
        </header>
        <main className="main-content">
          <Filters />
          <div className="card" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
            <h3 style={{ marginBottom: '0.5rem' }}>No Data Available</h3>
            <p className="text-secondary">No sessions found for the selected date range and filters.</p>
          </div>
        </main>
      </div>
    );
  }

  // Calculate summary metrics
  const totalSessions = data.compliance_trend.reduce(
    (sum, item) => sum + item.total_sessions,
    0
  );
  const avgCompliance = data.compliance_trend.length > 0
    ? data.compliance_trend.reduce((sum, item) => sum + item.compliance_rate, 0) / data.compliance_trend.length
    : 0;

  return (
    <div className="overview-page">
      <header className="page-header">
        <div className="header-content">
          <div className="header-title">
            <h1>DeltaWash Compliance Dashboard</h1>
            <p className="page-subtitle">
              Monitoring handwashing compliance across {data.device_summary.total_devices} devices
            </p>
          </div>
        </div>
      </header>

      <main className="main-content">
        {/* Filters Section */}
        <Filters />

        {/* Key Metrics Row */}
        <section className="metrics-section">
          <div className="metrics-grid">
            <MetricCard
              label="Average Compliance"
              value={avgCompliance.toFixed(1)}
              unit="%"
            />
            <MetricCard
              label="Total Sessions"
              value={totalSessions.toLocaleString()}
            />
            <MetricCard
              label="Avg Wash Time"
              value={(data.average_wash_time_ms / 1000).toFixed(1)}
              unit="sec"
            />
            <MetricCard
              label="Quality Rate"
              value={data.quality_rate.toFixed(1)}
              unit="%"
            />
          </div>
        </section>

        {/* Device Status */}
        <section className="table-section">
          <div className="table-header">
            <h2>Device Status</h2>
          </div>
          <div style={{ padding: 'var(--space-6)', display: 'flex', gap: 'var(--space-8)', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
              <span style={{ fontSize: 'var(--text-3xl)', fontWeight: 'var(--font-bold)', fontFamily: 'var(--font-mono)' }}>{data.device_summary.total_devices}</span>
              <span className="text-secondary">Total Devices</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
              <DeviceStatusBadge isOnline={true} />
              <span style={{ fontSize: 'var(--text-2xl)', fontWeight: 'var(--font-semibold)', fontFamily: 'var(--font-mono)' }}>{data.device_summary.online_devices}</span>
              <span className="text-secondary">Online</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
              <DeviceStatusBadge isOnline={false} />
              <span style={{ fontSize: 'var(--text-2xl)', fontWeight: 'var(--font-semibold)', fontFamily: 'var(--font-mono)' }}>{data.device_summary.offline_devices}</span>
              <span className="text-secondary">Offline</span>
            </div>
          </div>
        </section>

        {/* Charts Row */}
        <section className="charts-section">
          <ComplianceTrendChart data={data.compliance_trend} />
          <StepBarChart 
            data={data.average_step_times} 
            highlightStepId={data.most_missed_step?.step_id}
          />
        </section>

        {/* Most Missed Step Alert */}
        {data.most_missed_step && (
          <section className="table-section" style={{ marginBottom: 'var(--space-8)' }}>
            <div className="table-header">
              <h2>⚠️ Most Missed Step</h2>
            </div>
            <div style={{ padding: 'var(--space-6)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span className="text-muted" style={{ fontSize: 'var(--text-sm)' }}>Step {data.most_missed_step.step_id}</span>
                <p style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--font-medium)', marginTop: 'var(--space-1)' }}>{data.most_missed_step.step_name}</p>
              </div>
              <div style={{ textAlign: 'right' }}>
                <span style={{ fontSize: 'var(--text-2xl)', fontWeight: 'var(--font-bold)', color: 'var(--color-danger)', fontFamily: 'var(--font-mono)' }}>{data.most_missed_step.miss_rate.toFixed(1)}%</span>
                <p className="text-muted" style={{ fontSize: 'var(--text-sm)' }}>{data.most_missed_step.missed_count} misses</p>
              </div>
            </div>
          </section>
        )}

        {/* Timing Chart */}
        <TimingChart data={data.average_step_times} />

        {/* Average Step Times Table */}
        <section className="table-section" style={{ marginTop: 'var(--space-8)' }}>
          <div className="table-header">
            <h2>Average Step Times</h2>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Step</th>
                <th>Name</th>
                <th style={{ textAlign: 'right' }}>Avg Duration</th>
              </tr>
            </thead>
            <tbody>
              {data.average_step_times.map((step) => (
                <tr key={step.step_id}>
                  <td style={{ fontFamily: 'var(--font-mono)', width: '80px' }}>{step.step_id}</td>
                  <td>{step.step_name}</td>
                  <td className="numeric">{(step.avg_duration_ms / 1000).toFixed(1)}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>
    </div>
  );
}
