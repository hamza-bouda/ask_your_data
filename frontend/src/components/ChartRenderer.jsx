import React, { useState, useMemo, useRef, useEffect } from 'react';
import * as echarts from 'echarts';
import { AlertCircle, BarChart3, Table as TableIcon, Settings2 } from 'lucide-react';

const PALETTES = {
  standard: ['#6366f1', '#3b82f6', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#06b6d4', '#14b8a6', '#f97316', '#ef4444'],
  high_contrast: ['#2563eb', '#d97706', '#059669', '#dc2626', '#7c3aed', '#db2777', '#0891b2', '#4b5563'],
  monochrome: ['#334155', '#475569', '#64748b', '#94a3b8', '#cbd5e1', '#e2e8f0'],
};

const formatValue = (val, format) => {
  if (typeof val !== 'number') return val ?? '-';
  if (format === 'compact') return Intl.NumberFormat('fr-FR', { notation: 'compact' }).format(val);
  if (format === 'currency') return Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(val);
  if (format === 'percent') return Intl.NumberFormat('fr-FR', { style: 'percent' }).format(val / 100);
  return val.toLocaleString('fr-FR');
};

/**
 * Reusable wrapper component for Apache ECharts instance with auto-resize.
 */
function EChartInstance({ option, height = '360px', theme = 'dark' }) {
  const chartRef = useRef(null);
  const chartInstance = useRef(null);

  useEffect(() => {
    if (!chartRef.current) return;

    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current, theme === 'dark' ? 'dark' : undefined, {
        renderer: 'svg',
      });
    }

    chartInstance.current.setOption(option, true);

    const resizeObserver = new ResizeObserver(() => {
      chartInstance.current?.resize();
    });
    resizeObserver.observe(chartRef.current);

    const handleWindowResize = () => {
      chartInstance.current?.resize();
    };
    window.addEventListener('resize', handleWindowResize);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('resize', handleWindowResize);
      if (chartInstance.current) {
        chartInstance.current.dispose();
        chartInstance.current = null;
      }
    };
  }, [option, theme]);

  return (
    <div
      ref={chartRef}
      style={{
        width: '100%',
        height,
        minHeight: '280px',
        backgroundColor: 'transparent',
      }}
    />
  );
}

export default function ChartRenderer({ data, chartSpec }) {
  // Unconditionally declared hooks at the top level
  const [viewMode, setViewMode] = useState('chart');
  const [selectedChartType, setSelectedChartType] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [customTitle, setCustomTitle] = useState('');
  const [palette, setPalette] = useState('standard');
  const [showAxes, setShowAxes] = useState(true);
  const [showLegend, setShowLegend] = useState(true);
  const [numberFormat, setNumberFormat] = useState('standard');
  const [sortOrder, setSortOrder] = useState('none');
  const [currentPage, setCurrentPage] = useState(1);

  const rawData = useMemo(() => data || [], [data]);
  const rowsPerPage = 100;

  const generatedSpec = useMemo(
    () => chartSpec || { chart_type: 'table', title: 'Résultats', warnings: [] },
    [chartSpec],
  );
  const spec = useMemo(
    () => (selectedChartType ? { ...generatedSpec, chart_type: selectedChartType } : generatedSpec),
    [generatedSpec, selectedChartType],
  );

  const colors = PALETTES[palette] || PALETTES.standard;
  const titleToDisplay = customTitle || spec.title || 'Visualisation';

  const processedData = useMemo(() => {
    if (!rawData.length) return [];
    let d = [...rawData];
    if (sortOrder !== 'none' && spec.y_field) {
      d.sort((a, b) => {
        const valA = Number(a[spec.y_field] ?? 0);
        const valB = Number(b[spec.y_field] ?? 0);
        return sortOrder === 'asc' ? valA - valB : valB - valA;
      });
    }
    return d;
  }, [rawData, sortOrder, spec.y_field]);

  // Build Apache ECharts Option based on spec and processed data
  const echartsOption = useMemo(() => {
    if (!processedData.length) return {};

    const chartType = spec.chart_type;
    const xField = spec.x_field || (Object.keys(processedData[0] || {})[0] || 'x');
    const yField = spec.y_field || (Object.keys(processedData[0] || {})[1] || 'y');

    const xValues = processedData.map((row) => String(row[xField] ?? ''));
    const yValues = processedData.map((row) => Number(row[yField] ?? 0));

    const baseConfig = {
      backgroundColor: 'transparent',
      color: colors,
      animationDuration: 750,
      textStyle: {
        fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
        color: '#94a3b8',
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#1e293b',
        borderColor: '#334155',
        textStyle: { color: '#f8fafc' },
        formatter: (params) => {
          if (!Array.isArray(params) || !params.length) return '';
          const item = params[0];
          return `<div style="font-weight:600;margin-bottom:4px">${item.name}</div>
                  <div>${item.marker} ${yField}: <b>${formatValue(item.value, numberFormat)}</b></div>`;
        },
      },
      grid: {
        top: 40,
        left: '3%',
        right: '4%',
        bottom: showAxes ? 40 : 15,
        containLabel: true,
      },
      toolbox: {
        show: true,
        feature: {
          saveAsImage: { show: true, title: 'Télécharger PNG' },
          dataView: { show: false },
        },
        iconStyle: { borderColor: '#64748b' },
        right: 15,
        top: 0,
      },
    };

    if (showLegend && ['pie', 'donut', 'stacked_bar', 'radar'].includes(chartType)) {
      baseConfig.legend = {
        show: true,
        orient: 'horizontal',
        bottom: 0,
        textStyle: { color: '#94a3b8' },
      };
    }

    switch (chartType) {
      case 'line':
      case 'area': {
        const isArea = chartType === 'area';
        return {
          ...baseConfig,
          xAxis: {
            type: 'category',
            data: xValues,
            show: showAxes,
            axisLine: { lineStyle: { color: '#334155' } },
            axisLabel: { color: '#94a3b8', rotate: xValues.length > 8 ? 30 : 0 },
          },
          yAxis: {
            type: 'value',
            show: showAxes,
            splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
            axisLabel: {
              color: '#94a3b8',
              formatter: (val) => formatValue(val, numberFormat === 'standard' ? 'compact' : numberFormat),
            },
          },
          series: [
            {
              name: yField,
              type: 'line',
              smooth: true,
              data: yValues,
              itemStyle: { color: colors[0] },
              lineStyle: { width: 3, color: colors[0] },
              areaStyle: isArea
                ? {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                      { offset: 0, color: colors[0] + '88' },
                      { offset: 1, color: colors[0] + '05' },
                    ]),
                  }
                : undefined,
              symbolSize: 6,
            },
          ],
        };
      }

      case 'horizontal_bar': {
        return {
          ...baseConfig,
          xAxis: {
            type: 'value',
            show: showAxes,
            splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
            axisLabel: {
              color: '#94a3b8',
              formatter: (val) => formatValue(val, numberFormat === 'standard' ? 'compact' : numberFormat),
            },
          },
          yAxis: {
            type: 'category',
            data: xValues,
            show: showAxes,
            inverse: true,
            axisLine: { lineStyle: { color: '#334155' } },
            axisLabel: { color: '#94a3b8' },
          },
          series: [
            {
              name: yField,
              type: 'bar',
              data: yValues,
              itemStyle: {
                borderRadius: [0, 6, 6, 0],
                color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                  { offset: 0, color: colors[0] },
                  { offset: 1, color: colors[1] || colors[0] },
                ]),
              },
            },
          ],
        };
      }

      case 'pie':
      case 'donut': {
        const isDonut = chartType === 'donut';
        const pieData = processedData.map((row) => ({
          name: String(row[xField] ?? 'Autre'),
          value: Number(row[yField] ?? 0),
        }));

        return {
          ...baseConfig,
          tooltip: {
            trigger: 'item',
            backgroundColor: '#1e293b',
            borderColor: '#334155',
            textStyle: { color: '#f8fafc' },
            formatter: (item) =>
              `<b>${item.name}</b><br/>${yField}: ${formatValue(item.value, numberFormat)} (${item.percent}%)`,
          },
          series: [
            {
              name: yField,
              type: 'pie',
              radius: isDonut ? ['48%', '75%'] : '70%',
              center: ['50%', '50%'],
              avoidLabelOverlap: true,
              itemStyle: {
                borderRadius: 4,
                borderColor: '#0f172a',
                borderWidth: 2,
              },
              label: {
                show: true,
                color: '#cbd5e1',
                formatter: '{b}: {d}%',
              },
              data: pieData,
            },
          ],
        };
      }

      case 'scatter': {
        const numericKeys = Object.keys(processedData[0] || {}).filter(
          (k) => typeof processedData[0][k] === 'number'
        );
        const xNumField = numericKeys[0] || xField;
        const yNumField = numericKeys[1] || yField;
        const scatterData = processedData.map((row) => [
          Number(row[xNumField] ?? 0),
          Number(row[yNumField] ?? 0),
        ]);

        return {
          ...baseConfig,
          tooltip: {
            trigger: 'item',
            backgroundColor: '#1e293b',
            borderColor: '#334155',
            formatter: (params) =>
              `${xNumField}: <b>${formatValue(params.value[0], numberFormat)}</b><br/>` +
              `${yNumField}: <b>${formatValue(params.value[1], numberFormat)}</b>`,
          },
          xAxis: {
            type: 'value',
            name: xNumField,
            splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
          },
          yAxis: {
            type: 'value',
            name: yNumField,
            splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
          },
          series: [
            {
              type: 'scatter',
              data: scatterData,
              symbolSize: 12,
              itemStyle: { color: colors[0], opacity: 0.85 },
            },
          ],
        };
      }

      case 'radar': {
        const maxVal = Math.max(...yValues, 10);
        const indicators = xValues.map((name) => ({ name, max: maxVal * 1.15 }));
        return {
          ...baseConfig,
          tooltip: { trigger: 'item' },
          radar: {
            indicator: indicators,
            shape: 'polygon',
            splitArea: { show: false },
            axisLine: { lineStyle: { color: '#334155' } },
            splitLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
          },
          series: [
            {
              type: 'radar',
              data: [
                {
                  value: yValues,
                  name: yField,
                  areaStyle: { color: colors[0] + '44' },
                  lineStyle: { color: colors[0], width: 2 },
                  itemStyle: { color: colors[0] },
                },
              ],
            },
          ],
        };
      }

      case 'stacked_bar': {
        const keys = Object.keys(processedData[0] || {}).filter((k) => k !== xField);
        const seriesList = keys.map((k, idx) => ({
          name: k,
          type: 'bar',
          stack: 'total',
          data: processedData.map((row) => Number(row[k] ?? 0)),
          itemStyle: { color: colors[idx % colors.length] },
        }));

        return {
          ...baseConfig,
          xAxis: { type: 'category', data: xValues },
          yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } } },
          series: seriesList,
        };
      }

      case 'waterfall': {
        const baseValues = [];
        let runningTotal = 0;
        const barHeights = [];
        for (const v of yValues) {
          baseValues.push(runningTotal);
          runningTotal += v;
          barHeights.push(Math.abs(v));
        }

        return {
          ...baseConfig,
          xAxis: { type: 'category', data: xValues },
          yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } } },
          series: [
            {
              name: 'Placeholder',
              type: 'bar',
              stack: 'Total',
              itemStyle: { borderColor: 'transparent', color: 'transparent' },
              data: baseValues,
            },
            {
              name: yField,
              type: 'bar',
              stack: 'Total',
              data: barHeights,
              itemStyle: {
                color: (param) => (yValues[param.dataIndex] >= 0 ? '#10b981' : '#ef4444'),
                borderRadius: 4,
              },
            },
          ],
        };
      }

      case 'heatmap':
      case 'histogram':
      case 'bar':
      default: {
        return {
          ...baseConfig,
          xAxis: {
            type: 'category',
            data: xValues,
            show: showAxes,
            axisLine: { lineStyle: { color: '#334155' } },
            axisLabel: { color: '#94a3b8', rotate: xValues.length > 6 ? 30 : 0 },
          },
          yAxis: {
            type: 'value',
            show: showAxes,
            splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
            axisLabel: {
              color: '#94a3b8',
              formatter: (val) => formatValue(val, numberFormat === 'standard' ? 'compact' : numberFormat),
            },
          },
          series: [
            {
              name: yField,
              type: 'bar',
              data: yValues,
              itemStyle: {
                borderRadius: [6, 6, 0, 0],
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                  { offset: 0, color: colors[0] },
                  { offset: 1, color: colors[1] || colors[0] },
                ]),
              },
            },
          ],
        };
      }
    }
  }, [processedData, spec, colors, showAxes, showLegend, numberFormat]);

  // Early return for empty data AFTER all hooks are called
  if (!rawData || rawData.length === 0) {
    return null;
  }

  const isTableForced = spec.chart_type === 'table';
  const isMetric = spec.chart_type === 'metric';
  const canChooseChart = Boolean(generatedSpec.x_field && generatedSpec.y_field);

  const renderTable = () => {
    if (!processedData.length) return null;
    const keys = Object.keys(processedData[0]);
    const totalPages = Math.ceil(processedData.length / rowsPerPage);
    const startIndex = (currentPage - 1) * rowsPerPage;
    const paginatedData = processedData.slice(startIndex, startIndex + rowsPerPage);

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '16px' }}>
        <div
          style={{ overflowX: 'auto', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.08)' }}
          role="region"
          aria-label="Tableau de données"
          tabIndex="0"
        >
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.88rem' }}>
            <thead>
              <tr style={{ backgroundColor: 'rgba(255,255,255,0.04)' }}>
                {keys.map((k) => (
                  <th
                    key={k}
                    scope="col"
                    style={{
                      padding: '10px 14px',
                      borderBottom: '1px solid rgba(255,255,255,0.1)',
                      color: '#94a3b8',
                      fontWeight: 600,
                    }}
                  >
                    {k}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {paginatedData.map((row, i) => (
                <tr
                  key={i}
                  style={{
                    borderBottom: '1px solid rgba(255,255,255,0.04)',
                    backgroundColor: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)',
                  }}
                >
                  {keys.map((k) => (
                    <td key={k} style={{ padding: '8px 14px', color: '#e2e8f0' }}>
                      {row[k] === null || row[k] === undefined
                        ? '-'
                        : typeof row[k] === 'number'
                        ? formatValue(row[k], numberFormat)
                        : String(row[k])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem' }}>
            <span style={{ color: '#94a3b8' }}>
              Affichage {startIndex + 1} à {Math.min(startIndex + rowsPerPage, processedData.length)} sur{' '}
              {processedData.length}
            </span>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                disabled={currentPage === 1}
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                style={{
                  padding: '4px 10px',
                  background: 'rgba(255,255,255,0.08)',
                  border: 'none',
                  color: 'white',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  opacity: currentPage === 1 ? 0.4 : 1,
                }}
              >
                Précédent
              </button>
              <span style={{ color: '#cbd5e1', alignSelf: 'center' }}>
                Page {currentPage} / {totalPages}
              </span>
              <button
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                style={{
                  padding: '4px 10px',
                  background: 'rgba(255,255,255,0.08)',
                  border: 'none',
                  color: 'white',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  opacity: currentPage === totalPages ? 0.4 : 1,
                }}
              >
                Suivant
              </button>
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderMetric = () => {
    const yField = spec.y_field || Object.keys(processedData[0] || {})[0];
    const metricVal = processedData[0]?.[yField];

    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '32px 16px',
          background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(59, 130, 246, 0.04))',
          borderRadius: '12px',
          border: '1px solid rgba(99, 102, 241, 0.2)',
          margin: '16px 0',
        }}
      >
        <span style={{ fontSize: '0.9rem', color: '#94a3b8', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {titleToDisplay}
        </span>
        <span style={{ fontSize: '2.75rem', fontWeight: 800, color: '#60a5fa', letterSpacing: '-0.02em' }}>
          {typeof metricVal === 'number' ? formatValue(metricVal, numberFormat) : String(metricVal ?? '-')}
        </span>
        {spec.reason && (
          <span style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '8px' }}>
            {spec.reason}
          </span>
        )}
      </div>
    );
  };

  return (
    <div
      className="chart-container"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        backgroundColor: '#0f172a',
        borderRadius: '12px',
        border: '1px solid rgba(255,255,255,0.08)',
        padding: '16px 20px',
        marginTop: '12px',
      }}
    >
      {/* Header with Title and Mode Switcher */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <h4 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 600, color: '#f8fafc' }}>
            {titleToDisplay}
          </h4>
          {spec.reason && !isMetric && (
            <span style={{ fontSize: '0.78rem', color: '#64748b' }}>{spec.reason}</span>
          )}
        </div>

        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          {!isTableForced && !isMetric && (
            <div style={{ display: 'flex', background: 'rgba(255,255,255,0.06)', borderRadius: '6px', padding: '2px' }}>
              <button
                onClick={() => setViewMode('chart')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '5px 10px',
                  border: 'none',
                  borderRadius: '4px',
                  background: viewMode === 'chart' ? 'var(--accent, #6366f1)' : 'transparent',
                  color: viewMode === 'chart' ? 'white' : '#94a3b8',
                  fontSize: '0.8rem',
                  cursor: 'pointer',
                }}
              >
                <BarChart3 size={14} />
                Graphique
              </button>
              <button
                onClick={() => setViewMode('table')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '5px 10px',
                  border: 'none',
                  borderRadius: '4px',
                  background: viewMode === 'table' ? 'var(--accent, #6366f1)' : 'transparent',
                  color: viewMode === 'table' ? 'white' : '#94a3b8',
                  fontSize: '0.8rem',
                  cursor: 'pointer',
                }}
              >
                <TableIcon size={14} />
                Tableau
              </button>
            </div>
          )}

          {!isTableForced && (
            <button
              onClick={() => setShowSettings(!showSettings)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '6px',
                background: showSettings ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.06)',
                border: 'none',
                borderRadius: '6px',
                color: '#cbd5e1',
                cursor: 'pointer',
              }}
              title="Personnaliser la visualisation"
            >
              <Settings2 size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Warnings */}
      {spec.warnings && spec.warnings.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {spec.warnings.map((w, i) => (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '0.82rem',
                color: '#f59e0b',
                background: 'rgba(245, 158, 11, 0.1)',
                padding: '6px 10px',
                borderRadius: '6px',
              }}
            >
              <AlertCircle size={14} />
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}

      {/* Settings Drawer */}
      {showSettings && (
        <div
          style={{
            padding: '12px',
            backgroundColor: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: '8px',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '14px',
            fontSize: '0.82rem',
            color: '#cbd5e1',
          }}
        >
          <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            Titre personnalisé:
            <input
              type="text"
              value={customTitle}
              onChange={(e) => setCustomTitle(e.target.value)}
              placeholder={spec.title || 'Titre du graphique'}
              style={{
                background: '#1e293b',
                color: 'white',
                border: '1px solid #334155',
                borderRadius: '4px',
                padding: '4px 8px',
              }}
            />
          </label>

          {canChooseChart && (
            <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              Type de graphique:
              <select
                value={selectedChartType || spec.chart_type}
                onChange={(e) => setSelectedChartType(e.target.value)}
                style={{
                  background: '#1e293b',
                  color: 'white',
                  border: '1px solid #334155',
                  borderRadius: '4px',
                  padding: '4px 8px',
                }}
              >
                <option value="bar">Barres verticales</option>
                <option value="horizontal_bar">Barres horizontales</option>
                <option value="line">Ligne</option>
                <option value="area">Aire</option>
                <option value="pie">Camembert</option>
                <option value="donut">Donut (Anneau)</option>
                <option value="scatter">Nuage de points</option>
                <option value="radar">Radar</option>
                <option value="stacked_bar">Barres empilées</option>
                <option value="waterfall">Cascade</option>
              </select>
            </label>
          )}

          <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            Palette de couleurs:
            <select
              value={palette}
              onChange={(e) => setPalette(e.target.value)}
              style={{
                background: '#1e293b',
                color: 'white',
                border: '1px solid #334155',
                borderRadius: '4px',
                padding: '4px 8px',
              }}
            >
              <option value="standard">Standard (Vibrant)</option>
              <option value="high_contrast">Contraste élevé</option>
              <option value="monochrome">Monochrome</option>
            </select>
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            Format des nombres:
            <select
              value={numberFormat}
              onChange={(e) => setNumberFormat(e.target.value)}
              style={{
                background: '#1e293b',
                color: 'white',
                border: '1px solid #334155',
                borderRadius: '4px',
                padding: '4px 8px',
              }}
            >
              <option value="standard">Standard (1 234)</option>
              <option value="compact">Compact (1,2k)</option>
              <option value="currency">Monétaire (€)</option>
              <option value="percent">Pourcentage (%)</option>
            </select>
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            Tri des valeurs:
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value)}
              style={{
                background: '#1e293b',
                color: 'white',
                border: '1px solid #334155',
                borderRadius: '4px',
                padding: '4px 8px',
              }}
            >
              <option value="none">Par défaut</option>
              <option value="desc">Décroissant</option>
              <option value="asc">Croissant</option>
            </select>
          </label>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '16px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={showAxes}
                onChange={(e) => setShowAxes(e.target.checked)}
              />
              Axes visibles
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={showLegend}
                onChange={(e) => setShowLegend(e.target.checked)}
              />
              Légende
            </label>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      {isMetric ? (
        renderMetric()
      ) : isTableForced || viewMode === 'table' ? (
        renderTable()
      ) : (
        <EChartInstance option={echartsOption} height="360px" theme="dark" />
      )}
    </div>
  );
}
