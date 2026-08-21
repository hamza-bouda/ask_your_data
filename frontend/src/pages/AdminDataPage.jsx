import React, { useCallback, useEffect, useState } from 'react';
import {
  Activity, BookOpen, CheckCircle, Database, Link, Lock, Plus,
  RefreshCw, Settings, Table as TableIcon,
} from 'lucide-react';
import {
  createAdminMetric, getAdminAudit, getAdminCatalog, getAdminDatasources,
  getActiveSourceId, getAdminMetrics, registerDatabase, syncAdminDatasource, updateColumnPolicy,
  updateTablePolicy,
} from '../services/api';

const EMPTY_METRIC = { name: '', description: '', sql_expression: '' };

function MetricPanel({ metrics, isOpen, metric, onMetricChange, onOpen, onClose, onSubmit }) {
  return (
    <section className="card admin-panel">
      <div className="admin-panel-heading">
        <div>
          <h2><BookOpen size={19} /> Métriques métier</h2>
          <p>Définissez des calculs certifiés que l’agent doit privilégier.</p>
        </div>
        <button className="btn-primary" onClick={onOpen}><Plus size={16} /> Ajouter</button>
      </div>
      {isOpen && (
        <form className="admin-form" onSubmit={onSubmit}>
          <label>Nom<input value={metric.name} onChange={(event) => onMetricChange({ ...metric, name: event.target.value })} required /></label>
          <label>Description<input value={metric.description} onChange={(event) => onMetricChange({ ...metric, description: event.target.value })} /></label>
          <label>Expression SQL<input className="sql-input" value={metric.sql_expression} onChange={(event) => onMetricChange({ ...metric, sql_expression: event.target.value })} placeholder="SUM(total_amount)" required /></label>
          <div className="admin-actions"><button className="btn-primary" type="submit">Enregistrer</button><button className="btn-secondary" type="button" onClick={onClose}>Annuler</button></div>
        </form>
      )}
      {metrics.length === 0 && !isOpen ? <p className="muted-copy">Aucune métrique définie pour cette source.</p> : (
        <div className="table-scroll"><table className="data-table"><thead><tr><th>Nom</th><th>Description</th><th>SQL</th></tr></thead><tbody>
          {metrics.map((item) => <tr key={item.id}><td>{item.name}</td><td>{item.description || '—'}</td><td><code>{item.sql_expression}</code></td></tr>)}
        </tbody></table></div>
      )}
    </section>
  );
}

function AuditPanel({ audits }) {
  return (
    <section className="card admin-panel">
      <div className="admin-panel-heading"><div><h2><Activity size={19} /> Journal d’audit</h2><p>Historique des changements de gouvernance de ce tenant.</p></div></div>
      {audits.length === 0 ? <p className="muted-copy">Aucune action enregistrée.</p> : <div className="table-scroll"><table className="data-table"><thead><tr><th>Date</th><th>Utilisateur</th><th>Action</th><th>Cible</th></tr></thead><tbody>
        {audits.map((audit) => <tr key={audit.id}><td>{new Date(audit.timestamp).toLocaleString()}</td><td>{audit.user_id}</td><td><span className="audit-action">{audit.action}</span></td><td><code>{audit.target}</code></td></tr>)}
      </tbody></table></div>}
    </section>
  );
}

export default function AdminDataPage() {
  const [connectionString, setConnectionString] = useState('');
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(true);
  const [sourceData, setSourceData] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState(null);
  const [audits, setAudits] = useState([]);
  const [metrics, setMetrics] = useState([]);
  const [activeTab, setActiveTab] = useState('catalog');
  const [showMetricForm, setShowMetricForm] = useState(false);
  const [newMetric, setNewMetric] = useState(EMPTY_METRIC);

  const fetchCatalog = useCallback(async (sourceId) => {
    const data = await getAdminCatalog(sourceId);
    setTables(data.tables || []);
    setSelectedTable((current) => (current ? (data.tables || []).find((table) => table.id === current.id) || null : null));
  }, []);

  const fetchSourceStatus = useCallback(async () => {
    setIsFetching(true);
    try {
      const sources = await getAdminDatasources();
      const activeSourceId = getActiveSourceId();
      const source = sources?.find((item) => item.id === activeSourceId)
        || sources?.find((item) => item.connected)
        || null;
      setSourceData(source);
      if (source?.id) await fetchCatalog(source.id);
    } catch (requestError) {
      console.error('Unable to load administration data', requestError);
      setError('Impossible de charger les sources de données.');
    } finally {
      setIsFetching(false);
    }
  }, [fetchCatalog]);

  const fetchMetrics = useCallback(async () => {
    if (!sourceData?.id) return;
    const data = await getAdminMetrics(sourceData.id);
    setMetrics(data.metrics || []);
  }, [sourceData]);

  const fetchAudits = useCallback(async () => {
    const data = await getAdminAudit();
    setAudits(data.audits || []);
  }, []);

  useEffect(() => { fetchSourceStatus(); }, [fetchSourceStatus]);
  useEffect(() => {
    if (activeTab === 'audit') fetchAudits().catch(() => setError('Impossible de charger le journal d’audit.'));
    if (activeTab === 'metrics') fetchMetrics().catch(() => setError('Impossible de charger les métriques.'));
  }, [activeTab, fetchAudits, fetchMetrics]);

  const handleConnect = async (event) => {
    event.preventDefault();
    setIsLoading(true); setError(null);
    try {
      await registerDatabase(connectionString, { sourceId: sourceData?.id });
      await fetchSourceStatus();
      setShowForm(false);
    } catch {
      setError('Impossible de se connecter à la base. Vérifiez la chaîne et les droits read-only.');
    } finally { setIsLoading(false); }
  };

  const handleSync = async () => {
    if (!sourceData?.id) return;
    setIsLoading(true); setError(null);
    try { await syncAdminDatasource(sourceData.id); await fetchSourceStatus(); }
    catch { setError('La synchronisation a échoué.'); }
    finally { setIsLoading(false); }
  };

  const handleTableToggle = async (table) => {
    if (!sourceData?.id) return;
    const isAllowed = !table.is_allowed;
    try {
      await updateTablePolicy(sourceData.id, table.id, isAllowed);
      setTables((current) => current.map((item) => item.id === table.id ? { ...item, is_allowed: isAllowed } : item));
      setSelectedTable((current) => current?.id === table.id ? { ...current, is_allowed: isAllowed } : current);
    } catch { setError('La politique de table n’a pas pu être mise à jour.'); }
  };

  const handleColumnToggle = async (column) => {
    if (!sourceData?.id || !selectedTable?.is_allowed) return;
    const isAllowed = !column.is_allowed;
    try {
      await updateColumnPolicy(sourceData.id, selectedTable.id, column.id, isAllowed);
      const update = (table) => table.id !== selectedTable.id ? table : { ...table, columns: table.columns.map((item) => item.id === column.id ? { ...item, is_allowed: isAllowed } : item) };
      setTables((current) => current.map(update));
      setSelectedTable((current) => update(current));
    } catch { setError('La politique de colonne n’a pas pu être mise à jour.'); }
  };

  const handleDenyAll = async () => {
    if (!sourceData?.id || !window.confirm('Interdire immédiatement toutes les tables ?')) return;
    setIsLoading(true);
    try {
      await Promise.all(tables.filter((table) => table.is_allowed).map((table) => updateTablePolicy(sourceData.id, table.id, false)));
      await fetchCatalog(sourceData.id);
    } catch { setError('Certaines politiques n’ont pas pu être mises à jour.'); }
    finally { setIsLoading(false); }
  };

  const handleCreateMetric = async (event) => {
    event.preventDefault();
    if (!sourceData?.id) return;
    try {
      await createAdminMetric(sourceData.id, newMetric);
      setNewMetric(EMPTY_METRIC); setShowMetricForm(false); await fetchMetrics();
    } catch { setError('La métrique n’a pas pu être enregistrée.'); }
  };

  if (isFetching) return <div className="page-container center-content"><RefreshCw className="spinner" size={32} /></div>;

  return <div className="page-container"><header className="page-header"><h1>Administration des données</h1><p>Connectez, synchronisez et gouvernez ce que l’agent peut utiliser.</p></header><div className="page-content">
    {error && <div className="error-message">{error}</div>}
    {sourceData?.connected && !showForm ? <section className="card source-card admin-source-card"><div className="source-card-header"><div className="source-title"><Database size={24} color="#10b981" /><h3>{sourceData.name || 'Base de données principale'} · {sourceData.dialect}</h3></div><span className="status-badge success"><CheckCircle size={14} />Connectée</span></div><div className="source-card-body"><div className="stat-item"><span className="stat-value">{sourceData.table_count}</span><span className="stat-label">Tables détectées</span></div><div className="stat-item"><span className="stat-value admin-date">{sourceData.last_synced_at ? new Date(sourceData.last_synced_at).toLocaleString() : 'Jamais'}</span><span className="stat-label">Dernière synchronisation</span></div></div><div className="source-card-actions"><button className="btn-primary" onClick={handleSync} disabled={isLoading}><RefreshCw className={isLoading ? 'spinner' : ''} size={16} />Synchroniser</button><button className="btn-secondary" onClick={() => setShowForm(true)}>Modifier la connexion</button></div></section> : <section className="card connection-form-card"><div className="form-header"><Link size={32} color="#3b82f6" /><h3>{sourceData?.connected ? 'Modifier la connexion' : 'Connecter une base de données'}</h3><p>Utilisez impérativement un compte de base en lecture seule.</p></div><form onSubmit={handleConnect} className="connection-form"><div className="form-group"><label>Chaîne de connexion</label><input type="password" value={connectionString} onChange={(event) => setConnectionString(event.target.value)} placeholder="postgresql://user:password@host:5432/database" required /></div><div className="form-actions">{sourceData?.connected && <button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>Annuler</button>}<button type="submit" className="btn-primary" disabled={isLoading}>{isLoading ? 'Connexion…' : 'Enregistrer'}</button></div></form></section>}
    {sourceData?.connected && <section className="admin-tabs"><div className="tabs-header"><button className={activeTab === 'catalog' ? 'active' : ''} onClick={() => setActiveTab('catalog')}>Catalogue & politiques</button><button className={activeTab === 'metrics' ? 'active' : ''} onClick={() => setActiveTab('metrics')}>Métriques métier</button><button className={activeTab === 'audit' ? 'active' : ''} onClick={() => setActiveTab('audit')}>Journal d’audit</button></div>
      {activeTab === 'catalog' && <div className="explorer-layout admin-catalog"><aside className="explorer-sidebar"><div className="explorer-sidebar-header"><h3><TableIcon size={18} />Tables ({tables.length})</h3><button className="danger-button" onClick={handleDenyAll} disabled={isLoading}>Tout interdire</button></div><div className="table-list">{tables.map((table) => <div key={table.id} className={`table-list-item ${selectedTable?.id === table.id ? 'active' : ''}`}><button onClick={() => setSelectedTable(table)}><TableIcon size={16} /><span className={table.is_allowed ? '' : 'denied-label'}>{table.table_name}</span></button><label className="switch"><input type="checkbox" checked={Boolean(table.is_allowed)} onChange={() => handleTableToggle(table)} /><span className="slider round" /></label></div>)}</div></aside><main className="explorer-content">{selectedTable ? <div className="table-details-card"><div className="table-header"><div><h2>{selectedTable.table_name}</h2><p>Une table et chacune de ses colonnes doivent être autorisées pour être exposées à l’agent.</p></div></div>{!selectedTable.is_allowed && <div className="policy-warning"><Lock size={18} /><span>Cette table est interdite : ses colonnes ne sont pas accessibles.</span></div>}<h3>Colonnes ({selectedTable.columns.length})</h3><div className="table-scroll"><table className="data-table"><thead><tr><th>Autoriser</th><th>Nom</th><th>Type</th><th>Modifié par</th></tr></thead><tbody>{selectedTable.columns.map((column) => <tr key={column.id}><td><label className="switch"><input type="checkbox" checked={Boolean(column.is_allowed)} onChange={() => handleColumnToggle(column)} disabled={!selectedTable.is_allowed} /><span className="slider round" /></label></td><td className={column.is_allowed ? '' : 'denied-label'}>{column.name}</td><td><span className="type-badge">{column.type}</span></td><td>{column.modified_by || 'Système'}</td></tr>)}</tbody></table></div></div> : <div className="empty-state"><Settings size={44} /><p>Sélectionnez une table pour gérer ses accès.</p></div>}</main></div>}
      {activeTab === 'metrics' && <MetricPanel metrics={metrics} isOpen={showMetricForm} metric={newMetric} onMetricChange={setNewMetric} onOpen={() => setShowMetricForm(true)} onClose={() => setShowMetricForm(false)} onSubmit={handleCreateMetric} />}
      {activeTab === 'audit' && <AuditPanel audits={audits} />}
    </section>}
  </div></div>;
}
