import React, { useCallback, useEffect, useState } from 'react';
import { Archive, CheckCircle, Database, Link, Pencil, Plus, RefreshCw, RotateCcw } from 'lucide-react';
import { getActiveSourceId, getAdminDatasources, getDataSources, registerDatabase, setActiveSourceId, syncAdminDatasource, updateAdminDatasource } from '../services/api';

const currentUser = () => { try { return JSON.parse(localStorage.getItem('user') || '{}'); } catch { return {}; } };

export default function DataSourcesPage() {
  const isAdmin = currentUser().roles?.includes('admin');
  const [connectionString, setConnectionString] = useState('');
  const [name, setName] = useState('');
  const [editingSource, setEditingSource] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(true);
  const [sources, setSources] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const fetchSources = useCallback(async () => {
    setIsFetching(true);
    try {
      const items = isAdmin ? await getAdminDatasources() : await getDataSources();
      setSources(items);
      const activeId = getActiveSourceId();
      const available = items.filter((source) => source.status !== 'archived');
      if (!activeId && available.length === 1) setActiveSourceId(available[0].id);
      if (activeId && !available.some((source) => source.id === activeId)) setActiveSourceId(available[0]?.id);
    } catch (requestError) { console.error('Failed to fetch sources', requestError); setError('Impossible de charger les sources de données.'); } finally { setIsFetching(false); }
  }, [isAdmin]);
  useEffect(() => { fetchSources(); }, [fetchSources]);
  const closeForm = () => { setShowForm(false); setEditingSource(null); setName(''); setConnectionString(''); };
  const startEdit = (source) => { setEditingSource(source); setName(source.name); setConnectionString(''); setShowForm(true); setError(null); };
  const handleConnect = async (event) => { event.preventDefault(); setIsLoading(true); setError(null); try { const registered = await registerDatabase(connectionString, { name: name.trim(), sourceId: editingSource?.id }); setActiveSourceId(registered.id); await syncAdminDatasource(registered.id); closeForm(); await fetchSources(); } catch { setError('Impossible de connecter ou synchroniser la base. Vérifiez la chaîne et vos droits administrateur.'); } finally { setIsLoading(false); } };
  const changeStatus = async (source, status) => { const action = status === 'archived' ? 'Archiver' : 'Réactiver'; if (!window.confirm(`${action} « ${source.name} » ? Les historiques restent conservés et la source peut être réactivée.`)) return; setError(null); try { await updateAdminDatasource(source.id, { status }); if (status === 'archived' && getActiveSourceId() === source.id) setActiveSourceId(null); await fetchSources(); } catch (requestError) { setError(requestError.response?.data?.detail || `Impossible de ${action.toLowerCase()} cette source.`); } };
  if (isFetching) return <div className="page-container center-content"><RefreshCw className="spinner" size={32} /></div>;
  const activeSourceId = getActiveSourceId();
    return <div className="page-container"><header className="page-header datasource-page-header"><div><h1>Sources de données</h1><p>Sélectionnez le périmètre utilisé par l’explorateur et l’agent. Chaque conversation est liée à sa source.</p></div>{isAdmin && <button className="btn-primary" onClick={() => { closeForm(); setShowForm(true); }}><Plus size={17} /> Ajouter une source</button>}</header><div className="page-content">{error && <div className="error-message" role="alert">{error}</div>}<div className="datasource-grid">{sources.map((source) => { const archived = source.status === 'archived'; const selected = source.id === activeSourceId && !archived; return <article className={`card source-card datasource-card ${selected ? 'selected' : ''} ${archived ? 'archived' : ''}`} key={source.id}><div className="source-card-header"><div className="source-title"><Database size={23} color={selected ? '#3b82f6' : archived ? '#94a3b8' : '#10b981'} /><h3>{source.name}</h3></div>{archived ? <span className="status-badge">Archivée</span> : source.status === 'active' ? <span className="status-badge success"><CheckCircle size={14} />Prête</span> : <span className="status-badge">À synchroniser</span>}</div><div className="source-card-body"><div className="stat-item"><span className="stat-value">{source.table_count}</span><span className="stat-label">Tables indexées</span></div><div className="stat-item"><span className="stat-value source-dialect">{source.dialect || '—'}</span><span className="stat-label">Moteur</span></div></div><div className="source-card-actions">{!archived && <button className={selected ? 'btn-secondary' : 'btn-primary'} onClick={() => { setActiveSourceId(source.id); setSources((items) => [...items]); }}>{selected ? 'Source active' : 'Utiliser cette source'}</button>}{isAdmin && <><button className="icon-btn" title="Modifier la connexion" aria-label={`Modifier ${source.name}`} onClick={() => startEdit(source)}><Pencil size={17} /></button><button className="icon-btn" title={archived ? 'Réactiver' : 'Archiver'} aria-label={archived ? `Réactiver ${source.name}` : `Archiver ${source.name}`} onClick={() => changeStatus(source, archived ? 'active' : 'archived')}>{archived ? <RotateCcw size={17} /> : <Archive size={17} />}</button></>}</div></article>; })}</div>{!sources.length && <div className="empty-state small"><Database size={28} /><p>Aucune source connectée.</p>{isAdmin && <button className="btn-primary" onClick={() => setShowForm(true)}><Plus size={17} /> Connecter une source</button>}</div>}{isAdmin && showForm && <section className="card connection-form-card datasource-form"><div className="form-header"><Link size={32} color="#3b82f6" /><h3>{editingSource ? `Mettre à jour ${editingSource.name}` : 'Connecter une source'}</h3><p>Employez un compte de base de données strictement en lecture seule. La chaîne actuelle n’est jamais affichée.</p></div><form onSubmit={handleConnect} className="connection-form"><div className="form-group"><label>Nom de la source</label><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Ex. Production Europe" required /></div><div className="form-group"><label>{editingSource ? 'Nouvelle chaîne de connexion' : 'Chaîne de connexion'}</label><input type="password" value={connectionString} onChange={(event) => setConnectionString(event.target.value)} placeholder="postgresql://user:password@host:5432/database" required /></div><div className="form-actions"><button type="button" className="btn-secondary" onClick={closeForm}>Annuler</button><button type="submit" className="btn-primary" disabled={isLoading}>{isLoading ? 'Connexion…' : editingSource ? 'Mettre à jour et analyser' : 'Connecter et analyser'}</button></div></form></section>}</div></div>;
}
