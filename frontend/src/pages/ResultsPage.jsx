import React, { useCallback, useEffect, useState } from 'react';
import { Download, LineChart, RefreshCw, Save } from 'lucide-react';
import { api, getResults } from '../services/api';
import ChartRenderer from '../components/ChartRenderer';
import SaveToDashboardDialog from '../components/SaveToDashboardDialog';

export default function ResultsPage() {
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedResult, setSelectedResult] = useState(null);
  const [exporting, setExporting] = useState(false);
  const [savingResult, setSavingResult] = useState(null);
  const fetchResults = useCallback(async () => {
    setIsLoading(true); setError('');
    try {
      const data = await getResults();
      const items = data.results || [];
      setResults(items);
      setSelectedResult((current) => items.find((item) => item.id === current?.id) || items[0] || null);
    } catch (requestError) { setError(requestError.response?.data?.detail || 'Impossible de charger les résultats.'); }
    finally { setIsLoading(false); }
  }, []);
  useEffect(() => { fetchResults(); }, [fetchResults]);
  const exportSelected = async () => {
    if (!selectedResult) return;
    setExporting(true); setError('');
    try {
      const response = await api.get(`/v1/results/${selectedResult.id}/export`, { params: { format: 'csv' }, responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/csv' }));
      const link = document.createElement('a'); link.href = url; link.download = `askyourdata-${selectedResult.id}.csv`; document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url);
    } catch (requestError) { setError(requestError.response?.data?.detail || 'L’export CSV est indisponible pour ce résultat.'); }
    finally { setExporting(false); }
  };
  return <div className="page-container results-page"><header className="page-header results-header"><div><h1>Résultats & visualisations</h1><p>Retrouvez les analyses de vos conversations et exportez les données autorisées.</p></div><button className="btn-secondary" onClick={fetchResults} disabled={isLoading}><RefreshCw size={16} className={isLoading ? 'spinner' : ''} /> Actualiser</button></header>{error && <div className="error-message" role="alert">{error}</div>}<div className="results-layout"><aside className="results-list-card"><header><h2>Historique</h2><span>{results.length}</span></header><div className="results-list">{isLoading ? <div className="results-list-status"><RefreshCw className="spinner" size={20} /> Chargement…</div> : results.length === 0 ? <div className="results-list-status">Aucun résultat sauvegardé.</div> : results.map((result) => <button key={result.id} className={`result-list-item ${selectedResult?.id === result.id ? 'active' : ''}`} onClick={() => setSelectedResult(result)}><strong>{result.title}</strong><span>{result.conversation_title}</span><time>{new Date(result.date).toLocaleString('fr-FR')}</time></button>)}</div></aside><section className="results-detail-card">{selectedResult ? <><header className="results-detail-header"><div><h2>{selectedResult.title}</h2><p>Extrait de la conversation : <strong>{selectedResult.conversation_title}</strong></p></div><div className="result-header-actions"><button className="btn-secondary" onClick={() => setSavingResult(selectedResult)}><Save size={16} /> Sauvegarder</button><button className="btn-secondary" onClick={exportSelected} disabled={exporting}><Download size={16} /> {exporting ? 'Export…' : 'Exporter CSV'}</button></div></header><ChartRenderer data={selectedResult.data} chartSpec={selectedResult.chart_spec} /><section className="result-sql"><h3>Requête SQL exécutée</h3><pre>{selectedResult.sql || 'Requête SQL non disponible.'}</pre></section></> : <div className="center-content empty-state results-empty"><LineChart size={48} color="#475569" /><h2>Aucun résultat sélectionné</h2><p>Sélectionnez un résultat dans l’historique pour l’afficher.</p></div>}</section></div>{savingResult && <SaveToDashboardDialog messageId={savingResult.id} title={savingResult.title} onClose={() => setSavingResult(null)} />}</div>;
}
