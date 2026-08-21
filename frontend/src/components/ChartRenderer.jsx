import React, { useState } from 'react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend
} from 'recharts';
import { AlertCircle, BarChart3, Table as TableIcon } from 'lucide-react';

const COLORS = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1'];

const ChartRenderer = ({ data, chartSpec }) => {
  const [viewMode, setViewMode] = useState('chart'); // 'chart' or 'table'

  if (!data || data.length === 0) return null;

  // Fallback to table if no spec is provided
  const spec = chartSpec || { chart_type: 'table', title: 'Résultats', warnings: [] };
  const isTableForced = spec.chart_type === 'table';

  const renderTable = () => {
    const keys = Object.keys(data[0]);
    return (
      <div style={{ overflowX: 'auto', marginTop: '16px' }}>
        <table>
          <thead>
            <tr>
              {keys.map((k) => <th key={k}>{k}</th>)}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr key={i}>
                {keys.map((k) => (
                  <td key={k}>
                    {typeof row[k] === 'number' ? row[k].toLocaleString() : String(row[k] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const renderChart = () => {
    const { chart_type, x_field, y_field } = spec;

    if (chart_type === 'metric') {
      const val = data[0][y_field];
      return (
        <div style={{ padding: '24px', backgroundColor: 'var(--background)', borderRadius: '12px', border: '1px solid var(--border)', textAlign: 'center', marginTop: '16px' }}>
          <div style={{ fontSize: '36px', fontWeight: 'bold', color: 'var(--primary-color)' }}>
            {typeof val === 'number' ? val.toLocaleString() : val}
          </div>
          <div style={{ color: 'var(--text-muted)', marginTop: '8px' }}>{y_field}</div>
        </div>
      );
    }

    if (chart_type === 'pie') {
      return (
        <div style={{ width: '100%', height: 380, marginTop: '16px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey={y_field}
                nameKey={x_field}
                cx="50%"
                cy="50%"
                outerRadius={120}
                innerRadius={45}
                paddingAngle={3}
                label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                labelLine={true}
              >
                {data.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px', color: '#f8fafc' }}
                formatter={(value) => Number(value).toLocaleString()}
              />
              <Legend wrapperStyle={{ color: '#94a3b8', fontSize: '13px', paddingTop: '10px' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      );
    }

    if (chart_type === 'line') {
      return (
        <div style={{ width: '100%', height: 380, marginTop: '16px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 50 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey={x_field} stroke="#94a3b8" fontSize={11} angle={-25} textAnchor="end" interval="preserveStartEnd" />
              <YAxis stroke="#94a3b8" fontSize={11} tickFormatter={(v) => v.toLocaleString()} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px', color: '#f8fafc' }}
                formatter={(value) => Number(value).toLocaleString()}
              />
              <Line type="monotone" dataKey={y_field} stroke="#3b82f6" strokeWidth={3} dot={{ r: 4, fill: '#3b82f6' }} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      );
    }

    if (chart_type === 'bar') {
      return (
        <div style={{ width: '100%', height: 380, marginTop: '16px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 50 }}>
              <defs>
                <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={1} />
                  <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.8} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey={x_field} stroke="#94a3b8" fontSize={11} angle={-25} textAnchor="end" interval={0} />
              <YAxis stroke="#94a3b8" fontSize={11} tickFormatter={(v) => v.toLocaleString()} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px', color: '#f8fafc' }}
                formatter={(value) => Number(value).toLocaleString()}
                cursor={{ fill: 'rgba(255,255,255,0.04)' }}
              />
              <Bar dataKey={y_field} fill="url(#barGrad)" radius={[6, 6, 0, 0]} animationDuration={800} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
    }

    return renderTable();
  };

  return (
    <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h4 style={{ margin: 0, color: 'var(--text)' }}>{spec.title}</h4>
          {spec.reason && <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--text-muted)' }}>{spec.reason}</p>}
        </div>
        
        {!isTableForced && (
          <div style={{ display: 'flex', gap: '4px', backgroundColor: 'var(--background)', padding: '4px', borderRadius: '8px', border: '1px solid var(--border)' }}>
            <button
              onClick={() => setViewMode('chart')}
              style={{
                background: viewMode === 'chart' ? 'var(--border)' : 'transparent',
                border: 'none', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text)'
              }}
            >
              <BarChart3 size={16} /> Graphique
            </button>
            <button
              onClick={() => setViewMode('table')}
              style={{
                background: viewMode === 'table' ? 'var(--border)' : 'transparent',
                border: 'none', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text)'
              }}
            >
              <TableIcon size={16} /> Tableau
            </button>
          </div>
        )}
      </div>

      {spec.warnings && spec.warnings.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', backgroundColor: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b', borderRadius: '8px', fontSize: '12px' }}>
          <AlertCircle size={16} />
          <span>{spec.warnings[0]}</span>
        </div>
      )}

      {isTableForced || viewMode === 'table' ? renderTable() : renderChart()}
    </div>
  );
};

export default ChartRenderer;

