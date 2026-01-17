/**
 * TimingChart - Bar chart showing average time per step.
 */
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { AverageStepTime } from '../../types/analytics';

interface TimingChartProps {
  data: AverageStepTime[];
}

export function TimingChart({ data }: TimingChartProps) {
  // Transform data for better display
  const chartData = data.map(step => ({
    ...step,
    avg_duration_sec: step.avg_duration_ms / 1000,
    name: `Step ${step.step_id}`,
  }));

  return (
    <div className="chart-container">
      <h3 className="chart-title">Average Time Per Step</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
          <XAxis 
            dataKey="name"
            angle={-45}
            textAnchor="end"
            height={80}
            tick={{ fill: '#64748B', fontSize: 12 }}
            axisLine={{ stroke: '#E2E8F0' }}
          />
          <YAxis 
            label={{ value: 'Duration (seconds)', angle: -90, position: 'insideLeft', fill: '#64748B', fontSize: 12 }}
            tick={{ fill: '#64748B', fontSize: 12 }}
            axisLine={{ stroke: '#E2E8F0' }}
          />
          <Tooltip 
            formatter={(value: number) => [`${value.toFixed(1)}s`, 'Duration']}
            labelFormatter={(label, payload) => {
              if (payload && payload.length > 0) {
                return `${label}: ${payload[0].payload.step_name}`;
              }
              return String(label);
            }}
            contentStyle={{
              backgroundColor: '#FFFFFF',
              border: '1px solid #E2E8F0',
              borderRadius: '8px',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)',
            }}
            labelStyle={{ color: '#1E293B', fontWeight: 600 }}
            itemStyle={{ color: '#64748B' }}
          />
          <Bar 
            dataKey="avg_duration_sec" 
            fill="#059669" 
            name="Duration" 
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
