/**
 * UnitPage - Unit-scoped analytics page with device leaderboard.
 * 
 * Displays unit-specific compliance trends, device rankings, and performance metrics.
 */
import { useParams, useNavigate } from 'react-router-dom';
import { useFilters } from '../context/FilterContext';
import { useUnitAnalytics } from '../hooks/useAnalytics';
import { MetricCard } from '../components/common/MetricCard';
import { ErrorMessage } from '../components/common/ErrorMessage';
import { Filters } from '../components/filters/Filters';
import { ComplianceTrendChart } from '../components/charts/ComplianceTrendChart';
import { StepBarChart } from '../components/charts/StepBarChart';
import { TimingChart } from '../components/charts/TimingChart';
import { DeviceLeaderboard } from '../components/DeviceLeaderboard';
import './UnitPage.css';
import '../components/charts/Charts.css';

export function UnitPage() {
  const { unitId } = useParams<{ unitId: string }>();
  const navigate = useNavigate();
  const { filters } = useFilters();
  
  // Fetch unit analytics (excluding unitId from filters since it's in the URL)
  const { dateFrom, dateTo, shift, excludeLowQuality } = filters;
  const { data, isLoading, isError, error, refetch } = useUnitAnalytics(
    unitId!,
    { dateFrom, dateTo, shift, excludeLowQuality }
  );

  // Handle device click
  const handleDeviceClick = (deviceId: string) => {
    navigate(`/devices/${deviceId}`);
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="unit-page">
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <span className="loading-text">Loading unit analytics...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="unit-page">
        <ErrorMessage
          message={error?.message || 'Failed to load unit analytics'}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  // Empty state
  if (!data || data.metrics.compliance_trend.length === 0) {
    return (
      <div className="unit-page">
        <header className="page-header">
          <div className="header-content">
            <div className="header-title">
              <button onClick={() => navigate('/')} className="back-link">
                ← Back to Overview
              </button>
              <h1>Unit Analytics</h1>
            </div>
          </div>
        </header>
        <main className="main-content">
          <div className="empty-state">
            <h3>No Data Available</h3>
            <p>No sessions found for this unit in the selected date range.</p>
            <button onClick={() => navigate('/')} className="back-button">
              Back to Overview
            </button>
          </div>
        </main>
      </div>
    );
  }

  const { metrics, device_leaderboard } = data;

  // Calculate summary metrics
  const totalSessions = metrics.compliance_trend.reduce(
    (sum, item) => sum + item.total_sessions,
    0
  );
  const avgCompliance = metrics.compliance_trend.length > 0
    ? metrics.compliance_trend.reduce((sum, item) => sum + item.compliance_rate, 0) / metrics.compliance_trend.length
    : 0;

  return (
    <div className="unit-page">
      <header className="page-header">
        <div className="header-content">
          <div className="header-title">
            <button onClick={() => navigate('/')} className="back-link">
              ← Back to Overview
            </button>
            <h1>{metrics.unit_name} ({metrics.unit_code})</h1>
            <p className="page-subtitle">
              Unit performance with {device_leaderboard.length} device{device_leaderboard.length !== 1 ? 's' : ''}
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
              value={(metrics.average_wash_time_ms / 1000).toFixed(1)}
              unit="sec"
            />
            <MetricCard
              label="Quality Rate"
              value={metrics.quality_rate.toFixed(1)}
              unit="%"
            />
          </div>
        </section>

        {/* Charts Section */}
        <section className="charts-section">
          <ComplianceTrendChart data={metrics.compliance_trend} />
          <StepBarChart
            data={metrics.average_step_times}
            highlightStepId={metrics.most_missed_step?.step_id}
          />
        </section>

        {/* Most Missed Step Alert */}
        {metrics.most_missed_step && (
          <section className="table-section" style={{ marginBottom: 'var(--space-8)' }}>
            <div className="table-header">
              <h2>⚠️ Most Missed Step</h2>
            </div>
            <div style={{ padding: 'var(--space-6)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span className="text-muted" style={{ fontSize: 'var(--text-sm)' }}>Step {metrics.most_missed_step.step_id}</span>
                <p style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--font-medium)', marginTop: 'var(--space-1)' }}>{metrics.most_missed_step.step_name}</p>
              </div>
              <div style={{ textAlign: 'right' }}>
                <span style={{ fontSize: 'var(--text-2xl)', fontWeight: 'var(--font-bold)', color: 'var(--color-danger)', fontFamily: 'var(--font-mono)' }}>{metrics.most_missed_step.miss_rate.toFixed(1)}%</span>
                <p className="text-muted" style={{ fontSize: 'var(--text-sm)' }}>{metrics.most_missed_step.missed_count} misses</p>
              </div>
            </div>
          </section>
        )}

        {/* Timing Chart */}
        <TimingChart data={metrics.average_step_times} />

        {/* Device Leaderboard Section */}
        <section className="leaderboard-section">
          <DeviceLeaderboard
            devices={device_leaderboard}
            onDeviceClick={handleDeviceClick}
          />
        </section>
      </main>
    </div>
  );
}
