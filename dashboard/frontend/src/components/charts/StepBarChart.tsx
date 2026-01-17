/**
 * StepBarChart - Bar chart showing most missed steps.
 */
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';
import { AverageStepTime } from '../../types/analytics';

interface StepBarChartProps {
  data: AverageStepTime[];
  highlightStepId?: number;
}

// Design system chart colors
const COLORS = ['#0066CC', '#059669', '#D97706', '#0891B2', '#7C3AED', '#DC2626'];

export function StepBarChart({ data, highlightStepId }: StepBarChartProps) {
  return (
    <div className="chart-container">
      <h3 className="chart-title">Step Performance</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
          <XAxis 
            dataKey="step_id" 
            label={{ value: 'WHO Step', position: 'insideBottom', offset: -5, fill: '#64748B', fontSize: 12 }}
            tick={{ fill: '#64748B', fontSize: 12 }}
            axisLine={{ stroke: '#E2E8F0' }}
          />
          <YAxis 
            label={{ value: 'Avg Duration (sec)', angle: -90, position: 'insideLeft', fill: '#64748B', fontSize: 12 }}
            tick={{ fill: '#64748B', fontSize: 12 }}
            axisLine={{ stroke: '#E2E8F0' }}
          />
          <Tooltip 
            formatter={(value: number) => [`${(value / 1000).toFixed(1)}s`, 'Duration']}
            labelFormatter={(label) => `Step ${label}`}
            contentStyle={{
              backgroundColor: '#FFFFFF',
              border: '1px solid #E2E8F0',
              borderRadius: '8px',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)',
            }}
            labelStyle={{ color: '#1E293B', fontWeight: 600 }}
            itemStyle={{ color: '#64748B' }}
          />
          <Legend wrapperStyle={{ paddingTop: '16px' }} />
          <Bar 
            dataKey="avg_duration_ms" 
            name="Average Duration"
            radius={[4, 4, 0, 0]}
          >
            {data.map((entry, index) => (
              <Cell 
                key={`cell-${index}`} 
                fill={entry.step_id === highlightStepId ? '#DC2626' : COLORS[index % COLORS.length]} 
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
