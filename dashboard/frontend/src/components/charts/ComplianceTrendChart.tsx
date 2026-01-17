/**
 * ComplianceTrendChart - Line chart showing compliance rate over time.
 */
import { useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { ComplianceTrendItem } from '../../types/analytics';

interface ComplianceTrendChartProps {
  data: ComplianceTrendItem[];
}

export function ComplianceTrendChart({ data }: ComplianceTrendChartProps) {
  // Calculate dynamic Y-axis domain based on data
  const yAxisDomain = useMemo(() => {
    if (data.length === 0) return [0, 100];
    
    const rates = data.map(d => d.compliance_rate);
    const minRate = Math.min(...rates);
    const maxRate = Math.max(...rates);
    
    // Add some padding (5% of range, minimum 2 points)
    const range = maxRate - minRate;
    const padding = Math.max(range * 0.1, 2);
    
    // Round to nice values and ensure we don't go below 0 or above 100
    const yMin = Math.max(0, Math.floor((minRate - padding) / 5) * 5);
    const yMax = Math.min(100, Math.ceil((maxRate + padding) / 5) * 5);
    
    return [yMin, yMax];
  }, [data]);

  return (
    <div className="chart-container">
      <h3 className="chart-title">Compliance Trend</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
          <XAxis 
            dataKey="date" 
            tick={{ fill: '#64748B', fontSize: 12 }}
            axisLine={{ stroke: '#E2E8F0' }}
          />
          <YAxis 
            label={{ value: 'Compliance Rate (%)', angle: -90, position: 'insideLeft', fill: '#64748B', fontSize: 12 }}
            domain={yAxisDomain}
            tick={{ fill: '#64748B', fontSize: 12 }}
            axisLine={{ stroke: '#E2E8F0' }}
            tickFormatter={(value: number) => `${value}%`}
          />
          <Tooltip 
            formatter={(value: number) => [`${value.toFixed(1)}%`, 'Compliance Rate']}
            labelFormatter={(label: string) => `Date: ${label}`}
            contentStyle={{
              backgroundColor: '#FFFFFF',
              border: '1px solid #E2E8F0',
              borderRadius: '8px',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)',
            }}
            labelStyle={{ color: '#1E293B', fontWeight: 600 }}
            itemStyle={{ color: '#64748B' }}
          />
          <Legend 
            wrapperStyle={{ paddingTop: '16px' }}
          />
          <Line 
            type="monotone" 
            dataKey="compliance_rate" 
            name="Compliance Rate"
            stroke="#0066CC" 
            strokeWidth={2.5}
            dot={{ r: 4, fill: '#0066CC', strokeWidth: 2, stroke: '#FFFFFF' }}
            activeDot={{ r: 6, fill: '#0066CC', strokeWidth: 2, stroke: '#FFFFFF' }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
