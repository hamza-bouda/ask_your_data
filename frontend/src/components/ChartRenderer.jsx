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
  Legend,
  AreaChart,
  Area,
  ScatterChart,
  Scatter,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis
} from 'recharts';
import { AlertCircle, BarChart3, Table as TableIcon } from 'lucide-react';

const COLORS = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1'];

const ChartRenderer = ({ data, chartSpec }) => {
  const [viewMode, setViewMode] = useState('chart'); // 'chart' or 'table'
  const [selectedChartType, setSelectedChartType] = useState(null);

  if (!data || data.length === 0) return null;

  // Fallback to table if no spec is provided
  const generatedSpec = chartSpec || { chart_type: 'table', title: 'Résultats', warnings: [] };
  const spec = selectedChartType ? { ...generatedSpec, chart_type: selectedChartType } : generatedSpec;
  const isTableForced = spec.chart_type === 'table';
  const canChooseChart = Boolean(generatedSpec.x_field && generatedSpec.y_field);

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

    if (chart_type === 'pie' || chart_type === 'donut') {
      const pieData = data.length > 12
        ? [
            ...[...data]
              .sort((a, b) => Number(b[y_field] ?? 0) - Number(a[y_field] ?? 0))
              .slice(0, 11),
            {
              [x_field]: 'Autres',
              [y_field]: [...data]
                .sort((a, b) => Number(b[y_field] ?? 0) - Number(a[y_field] ?? 0))
                .slice(11)
                .reduce((total, row) => total + Number(row[y_field] ?? 0), 0),
            },
          ]
        : data;
      return (
        <div style={{ width: '100%', height: 380, marginTop: '16px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={pieData}
                dataKey={y_field}
                nameKey={x_field}
                cx="50%"
                cy="50%"
                outerRadius={120}
                innerRadius={chart_type === 'donut' ? 70 : 0}
                paddingAngle={3}
                label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                labelLine={pieData.length <= 12}
              >
                {pieData.map((_, i) => (
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

    if (chart_type === 'area') {
      return (
        <div style={{ width: '100%', height: 380, marginTop: '16px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 50 }}>
              <defs>
                <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.7} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey={x_field} stroke="#94a3b8" fontSize={11} angle={-25} textAnchor="end" interval="preserveStartEnd" />
              <YAxis stroke="#94a3b8" fontSize={11} tickFormatter={(v) => v.toLocaleString()} />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px', color: '#f8fafc' }} />
              <Area type="monotone" dataKey={y_field} stroke="#3b82f6" fill="url(#areaGrad)" strokeWidth={3} />
            </AreaChart>
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

    if (chart_type === 'horizontal_bar') {
      return (
        <div style={{ width: '100%', height: Math.max(380, data.length * 38), marginTop: '16px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical" margin={{ top: 10, right: 20, left: 90, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis type="number" stroke="#94a3b8" fontSize={11} />
              <YAxis type="category" dataKey={x_field} stroke="#94a3b8" fontSize={11} width={85} />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px', color: '#f8fafc' }} />
              <Bar dataKey={y_field} fill="#3b82f6" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
    }

    if (chart_type === 'scatter') {
      return (
        <div style={{ width: '100%', height: 380, marginTop: '16px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis type="number" dataKey={x_field} name={x_field} stroke="#94a3b8" />
              <YAxis type="number" dataKey={y_field} name={y_field} stroke="#94a3b8" />
              <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ backgroundColor: '#1e293b', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px', color: '#f8fafc' }} />
              <Scatter data={data} fill="#8b5cf6" />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      );
    }

    if (chart_type === 'radar') {
      return (
        <div style={{ width: '100%', height: 380, marginTop: '16px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={data}>
              <PolarGrid stroke="rgba(255,255,255,0.15)" />
              <PolarAngleAxis dataKey={x_field} stroke="#94a3b8" fontSize={11} />
              <PolarRadiusAxis stroke="#94a3b8" fontSize={11} />
              <Radar name={y_field} dataKey={y_field} stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.55} />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px', color: '#f8fafc' }} />
            </RadarChart>
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
        
        {(!isTableForced || canChooseChart) && (
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
            {canChooseChart && (
              <select
                aria-label="Type de graphique"
                value={selectedChartType || generatedSpec.chart_type}
                onChange={(event) => {
                  const chartType = event.target.value;
                  setSelectedChartType(chartType === generatedSpec.chart_type ? null : chartType);
                  setViewMode(chartType === 'table' ? 'table' : 'chart');
                }}
                style={{ background: 'transparent', border: 'none', color: 'var(--text)', padding: '6px', cursor: 'pointer' }}
              >
                <option value="bar">Barres</option>
                <option value="horizontal_bar">Barres horizontales</option>
                <option value="line">Ligne</option>
                <option value="area">Aire</option>
                <option value="pie">Secteurs</option>
                <option value="donut">Anneau</option>
                <option value="scatter">Nuage de points</option>
                <option value="radar">Radar</option>
                <option value="table">Tableau</option>
              </select>
            )}
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

