import React, { useCallback, useEffect, useState } from 'react';
import { CheckCircle, Database, Link, Plus, RefreshCw } from 'lucide-react';
import {
  getActiveSourceId, getDataSources, registerDatabase, setActiveSourceId,
  syncAdminDatasource,
} from '../services/api';

export default function DataSourcesPage() {
  const [connectionString, setConnectionString] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(true);
  const [sources, setSources] = useState([]);
  const [showForm, setShowForm] = useState(false);

  const fetchSources = useCallback(async () => {
    setIsFetching(true);
    try {
      const items = await getDataSources();
      setSources(items);
      const activeId = getActiveSourceId();
      if (!activeId && items.length === 1) setActiveSourceId(items[0].id);
      if (activeId && !items.some((source) => source.id === activeId)) setActiveSourceId(items[0]?.id);
    } catch (requestError) {
      console.error('Failed to fetch sources', requestError);
      setError('Impossible de charger les sources de données.');
    } finally { setIsFetching(false); }
  }, []);

  useEffect(() => { fetchSources(); }, [fetchSources]);

  const selectSource = (sourceId) => {
    setActiveSourceId(sourceId);
    setSources((items) => [...items]);
  };

  const handleConnect = async (event) => {
    event.preventDefault();
    setIsLoading(true); setError(null);
    try {
      const registered = await registerDatabase(connectionString, { name: name.trim() || undefined });
      setActiveSourceId(registered.id);
      await syncAdminDatasource(registered.id);
      setConnectionString(''); setName(''); setShowForm(false);
      await fetchSources();
    } catch {
      setError('Impossible de connecter ou synchroniser la base. Vérifiez la chaîne et vos droits administrateur.');
    } finally { setIsLoading(false); }
  };

  if (isFetching) return <div className="page-container center-content"><RefreshCw className="spinner" size={32} /></div>;

  const activeSourceId = getActiveSourceId();
  return <div className="page-container"><header className="page-header"><h1>Sources de données</h1><p>Sélectionnez le périmètre de données utilisé par l’explorateur et l’agent.</p></header><div className="page-content">
    {error && <div className="error-message">{error}</div>}
    <div className="datasource-grid">
      {sources.map((source) => <article className={`card source-card datasource-card ${source.id === activeSourceId ? 'selected' : ''}`} key={source.id}>
        <div className="source-card-header"><div className="source-title"><Database size={23} color={source.id === activeSourceId ? '#3b82f6' : '#10b981'} /><h3>{source.name}</h3></div>{source.status === 'active' && <span className="status-badge success"><CheckCircle size={14} />Prête</span>}</div>
        <div className="source-card-body"><div className="stat-item"><span className="stat-value">{source.table_count}</span><span className="stat-label">Tables indexées</span></div><div className="stat-item"><span className="stat-value source-dialect">{source.dialect || '—'}</span><span className="stat-label">Moteur</span></div></div>
        <div className="source-card-actions"><button className={source.id === activeSourceId ? 'btn-secondary' : 'btn-primary'} onClick={() => selectSource(source.id)}>{source.id === activeSourceId ? 'Source active' : 'Utiliser cette source'}</button></div>
      </article>)}
      {!sources.length && <div className="empty-state small"><Database size={28} /><p>Aucune source connectée.</p></div>}
    </div>
    {!showForm ? <button className="btn-primary datasource-add" onClick={() => setShowForm(true)}><Plus size={17} />Ajouter une source</button> : <section className="card connection-form-card datasource-form"><div className="form-header"><Link size={32} color="#3b82f6" /><h3>Connecter une source</h3><p>Employez un compte de base de données strictement en lecture seule.</p></div><form onSubmit={handleConnect} className="connection-form"><div className="form-group"><label>Nom de la source</label><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Ex. Production Europe" required /></div><div className="form-group"><label>Chaîne de connexion</label><input type="password" value={connectionString} onChange={(event) => setConnectionString(event.target.value)} placeholder="postgresql://user:password@host:5432/database" required /></div><div className="form-actions"><button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>Annuler</button><button type="submit" className="btn-primary" disabled={isLoading}>{isLoading ? 'Connexion…' : 'Connecter et analyser'}</button></div></form></section>}
  </div></div>;
}
