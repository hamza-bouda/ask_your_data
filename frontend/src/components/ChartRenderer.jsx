import React, { useId, useState, useMemo } from 'react';
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
  PolarRadiusAxis,
} from 'recharts';
import { AlertCircle, BarChart3, Table as TableIcon, Settings2 } from 'lucide-react';

const PALETTES = {
  standard: ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1'],
  high_contrast: ['#000000', '#E69F00', '#56B4E9', '#009E73', '#F0E442', '#0072B2', '#D55E00', '#CC79A7'],
  monochrome: ['#0f172a', '#1e293b', '#334155', '#475569', '#64748b', '#94a3b8', '#cbd5e1'],
};

const formatValue = (val, format) => {
  if (typeof val !== 'number') return val;
  if (format === 'compact') return Intl.NumberFormat('fr-FR', { notation: 'compact' }).format(val);
  if (format === 'currency') return Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(val);
  if (format === 'percent') return Intl.NumberFormat('fr-FR', { style: 'percent' }).format(val / 100);
  return val.toLocaleString();
};

const ChartRenderer = ({ data, chartSpec }) => {
  const [viewMode, setViewMode] = useState('chart');
  const [selectedChartType, setSelectedChartType] = useState(null);
  
  // Customization State
  const [showSettings, setShowSettings] = useState(false);
  const [customTitle, setCustomTitle] = useState('');
  const [palette, setPalette] = useState('standard');
  const [showAxes, setShowAxes] = useState(true);
  const [showLegend, setShowLegend] = useState(true);
  const [numberFormat, setNumberFormat] = useState('standard');
  const [sortOrder, setSortOrder] = useState('none');

  const chartId = useId().replace(/:/g, '');
  const areaGradientId = `areaGrad-${chartId}`;
  const barGradientId = `barGrad-${chartId}`;

  if (!data || data.length === 0) return null;

  const generatedSpec = chartSpec || { chart_type: 'table', title: 'Résultats', warnings: [] };
  const spec = selectedChartType ? { ...generatedSpec, chart_type: selectedChartType } : generatedSpec;
  const isTableForced = spec.chart_type === 'table';
  const canChooseChart = Boolean(generatedSpec.x_field && generatedSpec.y_field);
  
  const colors = PALETTES[palette] || PALETTES.standard;
  const titleToDisplay = customTitle || spec.title;

  const processedData = useMemo(() => {
    let d = [...data];
    if (sortOrder !== 'none' && spec.y_field) {
      d.sort((a, b) => {
        const valA = Number(a[spec.y_field] ?? 0);
        const valB = Number(b[spec.y_field] ?? 0);
        return sortOrder === 'asc' ? valA - valB : valB - valA;
      });
    }
    return d;
  }, [data, sortOrder, spec.y_field]);

  const renderTable = () => {
    const keys = Object.keys(processedData[0]);
    return (
      <div style={{ overflowX: 'auto', marginTop: '16px' }} role="region" aria-label="Tableau de données" tabIndex="0">
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr>
              {keys.map((k) => <th key={k} scope="col" style={{ padding: '8px', borderBottom: '2px solid var(--border)', color: 'var(--text)' }}>{k}</th>)}
            </tr>
          </thead>
          <tbody>
            {processedData.map((row, i) => (
              <tr key={i}>
                {keys.map((k) => (
                  <td key={k} style={{ padding: '8px', borderBottom: '1px solid var(--border)', color: 'var(--text)' }}>
                    {typeof row[k] === 'number' ? formatValue(row[k], numberFormat) : String(row[k] ?? '')}
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
      const val = processedData[0][y_field];
      return (
        <div role="img" aria-label={titleToDisplay} style={{ padding: '24px', backgroundColor: 'var(--background)', borderRadius: '12px', border: '1px solid var(--border)', textAlign: 'center', marginTop: '16px' }}>
          <div style={{ fontSize: '36px', fontWeight: 'bold', color: colors[0] }}>
            {formatValue(val, numberFormat)}
          </div>
          <div style={{ color: 'var(--text-muted)', marginTop: '8px' }}>{y_field}</div>
        </div>
      );
    }
    
    if (chart_type === 'heatmap') {
      const maxVal = Math.max(...processedData.map(d => Number(d[y_field] || 0)));
      return (
        <div role="img" aria-label={titleToDisplay} style={{ marginTop: '16px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
          {processedData.map((d, i) => {
            const val = Number(d[y_field] || 0);
            const intensity = maxVal > 0 ? val / maxVal : 0;
            return (
              <div key={i} title={`${d[x_field]}: ${formatValue(val, numberFormat)}`} style={{
                padding: '12px',
                minWidth: '80px',
                textAlign: 'center',
                backgroundColor: colors[0],
                opacity: Math.max(0.1, intensity),
                color: intensity > 0.5 ? '#fff' : 'inherit',
                borderRadius: '4px',
                fontSize: '12px',
                border: '1px solid rgba(0,0,0,0.1)'
              }}>
                <div style={{ fontWeight: 'bold', opacity: 1 }}>{String(d[x_field]).slice(0, 10)}</div>
                <div style={{ opacity: 1 }}>{formatValue(val, numberFormat)}</div>
              </div>
            );
          })}
        </div>
      );
    }

    if (chart_type === 'waterfall') {
      let cumulative = 0;
      const wfData = processedData.map(d => {
        const val = Number(d[y_field] || 0);
        const start = cumulative;
        cumulative += val;
        return {
          ...d,
          transparentBase: val >= 0 ? start : start + val,
          positiveVal: val >= 0 ? val : 0,
          negativeVal: val < 0 ? Math.abs(val) : 0,
          rawVal: val
        };
      });
      return (
        <div role="img" aria-label={titleToDisplay} style={{ width: '100%', height: 380, marginTop: '16px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={wfData} margin={{ top: 10, right: 20, left: 10, bottom: 50 }}>
              {showAxes && <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />}
              {showAxes && <XAxis dataKey={x_field} stroke="#94a3b8" fontSize={11} angle={-25} textAnchor="end" />}
              {showAxes && <YAxis stroke="#94a3b8" fontSize={11} tickFormatter={(v) => formatValue(v, numberFormat)} />}
              <Tooltip 
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px', color: '#f8fafc' }}
                formatter={(value, name, props) => [formatValue(props.payload.rawVal, numberFormat), y_field]}
              />
              <Bar dataKey="transparentBase" stackId="a" fill="transparent" />
              <Bar dataKey="positiveVal" stackId="a" fill={colors[2] || '#10b981'} />
              <Bar dataKey="negativeVal" stackId="a" fill={colors[4] || '#ef4444'} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
    }

    const commonProps = {
      data: processedData,
      margin: { top: 10, right: 20, left: 10, bottom: 50 }
    };

    const CommonAxes = () => (
      <>
        {showAxes && <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />}
        {showAxes && <XAxis dataKey={x_field} stroke="#94a3b8" fontSize={11} angle={-25} textAnchor="end" />}
        {showAxes && <YAxis stroke="#94a3b8" fontSize={11} tickFormatter={(v) => formatValue(v, numberFormat)} />}
        <Tooltip
          contentStyle={{ backgroundColor: '#1e293b', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px', color: '#f8fafc' }}
          formatter={(value) => formatValue(value, numberFormat)}
        />
        {showLegend && <Legend wrapperStyle={{ color: '#94a3b8', fontSize: '13px', paddingTop: '10px' }} />}
      </>
    );

    if (chart_type === 'pie' || chart_type === 'donut') {
      const pieData = processedData.length > 12
        ? [
            ...[...processedData].sort((a, b) => Number(b[y_field] ?? 0) - Number(a[y_field] ?? 0)).slice(0, 11),
            {
              [x_field]: 'Autres',
              [y_field]: [...processedData].sort((a, b) => Number(b[y_field] ?? 0) - Number(a[y_field] ?? 0)).slice(11).reduce((total, row) => total + Number(row[y_field] ?? 0), 0),
            },
          ]
        : processedData;
      return (
        <div role="img" aria-label={titleToDisplay} style={{ width: '100%', height: 380, marginTop: '16px' }}>
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
                  <Cell key={i} fill={colors[i % colors.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px', color: '#f8fafc' }}
                formatter={(value) => formatValue(value, numberFormat)}
              />
              {showLegend && <Legend wrapperStyle={{ color: '#94a3b8', fontSize: '13px', paddingTop: '10px' }} />}
            </PieChart>
          </ResponsiveContainer>
        </div>
      );
    }

    if (chart_type === 'line') {
      return (
        <div role="img" aria-label={titleToDisplay} style={{ width: '100%', height: 380, marginTop: '16px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart {...commonProps}>
              <CommonAxes />
              <Line type="monotone" dataKey={y_field} stroke={colors[0]} strokeWidth={3} dot={{ r: 4, fill: colors[0] }} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      );
    }

    if (chart_type === 'area') {
      return (
        <div role="img" aria-label={titleToDisplay} style={{ width: '100%', height: 380, marginTop: '16px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart {...commonProps}>
              <defs>
                <linearGradient id={areaGradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={colors[0]} stopOpacity={0.7} />
                  <stop offset="95%" stopColor={colors[0]} stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CommonAxes />
              <Area type="monotone" dataKey={y_field} stroke={colors[0]} fill={`url(#${areaGradientId})`} strokeWidth={3} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      );
    }

    if (chart_type === 'bar' || chart_type === 'stacked_bar' || chart_type === 'histogram') {
      const isHistogram = chart_type === 'histogram';
      return (
        <div role="img" aria-label={titleToDisplay} style={{ width: '100%', height: 380, marginTop: '16px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart {...commonProps} barCategoryGap={isHistogram ? 0 : '10%'}>
              <defs>
                <linearGradient id={barGradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={colors[0]} stopOpacity={1} />
                  <stop offset="100%" stopColor={colors[1] || colors[0]} stopOpacity={0.8} />
                </linearGradient>
              </defs>
              <CommonAxes />
              <Bar 
                dataKey={y_field} 
                fill={`url(#${barGradientId})`} 
                radius={isHistogram ? 0 : [6, 6, 0, 0]} 
                stackId={chart_type === 'stacked_bar' ? "a" : undefined}
                animationDuration={800} 
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
    }

    if (chart_type === 'horizontal_bar') {
      return (
        <div role="img" aria-label={titleToDisplay} style={{ width: '100%', height: Math.max(380, processedData.length * 38), marginTop: '16px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={processedData} layout="vertical" margin={{ top: 10, right: 20, left: 90, bottom: 10 }}>
              {showAxes && <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />}
              {showAxes && <XAxis type="number" stroke="#94a3b8" fontSize={11} tickFormatter={(v) => formatValue(v, numberFormat)} />}
              {showAxes && <YAxis type="category" dataKey={x_field} stroke="#94a3b8" fontSize={11} width={85} />}
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px', color: '#f8fafc' }} formatter={(v) => formatValue(v, numberFormat)} />
              {showLegend && <Legend />}
              <Bar dataKey={y_field} fill={colors[0]} radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
    }

    if (chart_type === 'scatter') {
      return (
        <div role="img" aria-label={titleToDisplay} style={{ width: '100%', height: 380, marginTop: '16px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
              {showAxes && <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />}
              {showAxes && <XAxis type="number" dataKey={x_field} name={x_field} stroke="#94a3b8" tickFormatter={(v) => formatValue(v, numberFormat)} />}
              {showAxes && <YAxis type="number" dataKey={y_field} name={y_field} stroke="#94a3b8" tickFormatter={(v) => formatValue(v, numberFormat)} />}
              <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ backgroundColor: '#1e293b', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px', color: '#f8fafc' }} formatter={(v) => formatValue(v, numberFormat)} />
              {showLegend && <Legend />}
              <Scatter data={processedData} fill={colors[0]} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      );
    }

    if (chart_type === 'radar') {
      return (
        <div role="img" aria-label={titleToDisplay} style={{ width: '100%', height: 380, marginTop: '16px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={processedData}>
              <PolarGrid stroke="rgba(255,255,255,0.15)" />
              <PolarAngleAxis dataKey={x_field} stroke="#94a3b8" fontSize={11} />
              <PolarRadiusAxis stroke="#94a3b8" fontSize={11} tickFormatter={(v) => formatValue(v, numberFormat)} />
              <Radar name={y_field} dataKey={y_field} stroke={colors[0]} fill={colors[0]} fillOpacity={0.55} />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '8px', color: '#f8fafc' }} formatter={(v) => formatValue(v, numberFormat)} />
              {showLegend && <Legend />}
            </RadarChart>
          </ResponsiveContainer>
        </div>
      );
    }

    return renderTable();
  };

  return (
    <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <h4 style={{ margin: 0, color: 'var(--text)' }}>{titleToDisplay}</h4>
          {spec.reason && <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--text-muted)' }}>{spec.reason}</p>}
        </div>
        
        {(!isTableForced || canChooseChart) && (
          <div style={{ display: 'flex', gap: '4px', backgroundColor: 'var(--background)', padding: '4px', borderRadius: '8px', border: '1px solid var(--border)', flexWrap: 'wrap' }}>
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
                <option value="stacked_bar">Barres empilées</option>
                <option value="horizontal_bar">Barres horizontales</option>
                <option value="line">Ligne</option>
                <option value="area">Aire</option>
                <option value="pie">Secteurs</option>
                <option value="donut">Anneau</option>
                <option value="scatter">Nuage de points</option>
                <option value="radar">Radar</option>
                <option value="heatmap">Carte de chaleur</option>
                <option value="waterfall">Cascade</option>
                <option value="histogram">Histogramme</option>
                <option value="table">Tableau</option>
              </select>
            )}
            <button
              onClick={() => setShowSettings(!showSettings)}
              aria-label="Personnaliser"
              style={{
                background: showSettings ? 'var(--border)' : 'transparent',
                border: 'none', padding: '6px', borderRadius: '6px', cursor: 'pointer',
                display: 'flex', alignItems: 'center', color: 'var(--text)'
              }}
            >
              <Settings2 size={16} />
            </button>
          </div>
        )}
      </div>

      {showSettings && (
        <div style={{ padding: '16px', backgroundColor: 'var(--border)', borderRadius: '8px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', color: 'var(--text-muted)' }}>Titre personnalisé</label>
            <input 
              type="text" 
              value={customTitle} 
              onChange={e => setCustomTitle(e.target.value)} 
              placeholder={spec.title}
              style={{ width: '100%', padding: '6px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.1)', background: 'var(--background)', color: 'var(--text)' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', color: 'var(--text-muted)' }}>Palette de couleurs</label>
            <select value={palette} onChange={e => setPalette(e.target.value)} style={{ width: '100%', padding: '6px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.1)', background: 'var(--background)', color: 'var(--text)' }}>
              <option value="standard">Standard</option>
              <option value="high_contrast">Haut contraste (A11y)</option>
              <option value="monochrome">Monochrome</option>
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', color: 'var(--text-muted)' }}>Format des nombres</label>
            <select value={numberFormat} onChange={e => setNumberFormat(e.target.value)} style={{ width: '100%', padding: '6px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.1)', background: 'var(--background)', color: 'var(--text)' }}>
              <option value="standard">Standard</option>
              <option value="compact">Compact (1K, 1M)</option>
              <option value="currency">Devise (€)</option>
              <option value="percent">Pourcentage (%)</option>
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', color: 'var(--text-muted)' }}>Tri</label>
            <select value={sortOrder} onChange={e => setSortOrder(e.target.value)} style={{ width: '100%', padding: '6px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.1)', background: 'var(--background)', color: 'var(--text)' }}>
              <option value="none">Aucun</option>
              <option value="asc">Croissant</option>
              <option value="desc">Décroissant</option>
            </select>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', justifyContent: 'center' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--text)' }}>
              <input type="checkbox" checked={showAxes} onChange={e => setShowAxes(e.target.checked)} />
              Afficher les axes
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--text)' }}>
              <input type="checkbox" checked={showLegend} onChange={e => setShowLegend(e.target.checked)} />
              Afficher la légende
            </label>
          </div>
        </div>
      )}

      {spec.warnings && spec.warnings.length > 0 && (
        <div role="alert" style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', backgroundColor: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b', borderRadius: '8px', fontSize: '12px' }}>
          <AlertCircle size={16} />
          <span>{spec.warnings[0]}</span>
        </div>
      )}

      {isTableForced || viewMode === 'table' ? renderTable() : renderChart()}
    </div>
  );
};

export default ChartRenderer;
