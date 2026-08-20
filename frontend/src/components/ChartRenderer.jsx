import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts';

const ChartRenderer = ({ data, intent, dimensions, metric }) => {
  if (!data || data.length === 0) return null;

  // Simple Table Renderer
  if (intent !== 'CHART_GENERATION' || !dimensions || dimensions.length === 0) {
    const keys = Object.keys(data[0]);
    return (
      <div style={{ overflowX: 'auto' }}>
        <table>
          <thead>
            <tr>
              {keys.map((k) => <th key={k}>{k}</th>)}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr key={i}>
                {keys.map((k) => <td key={k}>{row[k]}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  // Chart Renderer
  const xKey = dimensions[0];
  const yKey = metric || Object.keys(data[0]).find(k => k !== xKey) || 'value';

  return (
    <div style={{ width: '100%', height: 300, marginTop: '20px' }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
          <XAxis dataKey={xKey} stroke="#94a3b8" fontSize={12} />
          <YAxis stroke="#94a3b8" fontSize={12} />
          <Tooltip 
            contentStyle={{ backgroundColor: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }} 
            itemStyle={{ color: '#f8fafc' }}
          />
          <Bar dataKey={yKey} fill="#3b82f6" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default ChartRenderer;
