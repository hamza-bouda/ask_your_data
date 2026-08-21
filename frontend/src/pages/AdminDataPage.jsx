import React, { useState, useEffect } from 'react';
import { Database, Link, CheckCircle, RefreshCw, Table as TableIcon, Lock, Settings, Activity, BookOpen, Plus, LayoutList } from 'lucide-react';
import { registerDatabase, getAdminDatasources, syncAdminDatasource, getAdminCatalog, updateTablePolicy, updateColumnPolicy, getAdminAudit, getAdminMetrics, createAdminMetric } from '../services/api';

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
  const [activeTab, setActiveTab] = useState('catalog');
  const [metrics, setMetrics] = useState([]);
  const [showMetricForm, setShowMetricForm] = useState(false);
  const [newMetric, setNewMetric] = useState({name: '', description: '', sql_expression: ''});


  useEffect(() => {
    fetchSourceStatus();
  }, []);

  const fetchSourceStatus = async () => {
    setIsFetching(true);
    try {
      const data = await getAdminDatasources();
      if (data && data.length > 0 && data[0].connected) {
        setSourceData(data[0]);
        await fetchCatalog(data[0].id);
      }
    } catch (err) {
      console.error("Failed to fetch source status", err);
    } finally {
      setIsFetching(false);
    }
  };

  const fetchCatalog = async (sourceId) => {
    try {
      const catalogData = await getAdminCatalog(sourceId);
      setTables(catalogData.tables || []);
    } catch (err) {
      console.error("Failed to fetch catalog", err);
    }
  };

  const fetchAudits = async () => {
    try {
      const auditData = await getAdminAudit();
      setAudits(auditData.audits || []);
    } catch (err) {
      console.error("Failed to fetch audits", err);
    }
  };

  useEffect(() => {
    if (activeTab === 'audit') {
      fetchAudits();
    } else if (activeTab === 'metrics') {
      fetchMetrics();
    }
  }, [activeTab]);
  const fetchMetrics = async () => {
    if (!sourceData?.id) return;
    try {
      const data = await getAdminMetrics(sourceData.id);
      setMetrics(data.metrics || []);
    } catch (err) {
      console.error("Failed to fetch metrics", err);
    }
  };

  const handleCreateMetric = async (e) => {
    e.preventDefault();
    try {
      await createAdminMetric(sourceData.id, newMetric);
      setShowMetricForm(false);
      setNewMetric({name: '', description: '', sql_expression: ''});
      fetchMetrics();
    } catch (err) {
      alert("Erreur lors de la création de la métrique");
    }
  };


  const handleConnect = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      await registerDatabase(connectionString);
      setShowForm(false);
      await fetchSourceStatus();
    } catch (err) {
      setError("Impossible de se connecter à la base de données.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSync = async () => {
    if (!sourceData?.id) return;
    setIsLoading(true);
    try {
      await syncAdminDatasource(sourceData.id);
      await fetchSourceStatus();
    } catch (err) {
      setError("Erreur lors de la synchronisation.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleTableToggle = async (table) => {
    if (!sourceData?.id) return;
    try {
      const newStatus = !table.is_allowed;
      await updateTablePolicy(sourceData.id, table.id, newStatus);
      
      // Update local state
      const updatedTables = tables.map(t => 
        t.id === table.id ? { ...t, is_allowed: newStatus } : t
      );
      setTables(updatedTables);
      if (selectedTable?.id === table.id) {
        setSelectedTable({ ...selectedTable, is_allowed: newStatus });
      }
    } catch (err) {
      console.error("Failed to update table policy", err);
      alert("Erreur lors de la mise à jour");
    }
  };

  const handleColumnToggle = async (tableId, column) => {
    if (!sourceData?.id) return;
    try {
      const newStatus = !column.is_allowed;
      await updateColumnPolicy(sourceData.id, tableId, column.id, newStatus);
      
      // Update local state
      const updatedTables = tables.map(t => {
        if (t.id === tableId) {
          return {
            ...t,
            columns: t.columns.map(c => c.id === column.id ? { ...c, is_allowed: newStatus } : c)
          };
        }
        return t;
      });
      setTables(updatedTables);
      if (selectedTable?.id === tableId) {
        const updatedSelected = updatedTables.find(t => t.id === tableId);
        setSelectedTable(updatedSelected);
      }
    } catch (err) {
      console.error("Failed to update column policy", err);
      alert("Erreur lors de la mise à jour");
    }
  };

  const handleDenyAll = async () => {
      if (!sourceData?.id) return;
      if(window.confirm("Voulez-vous vraiment interdire l'accès à TOUTES les tables ? Cette action est immédiate.")) {
          for(const t of tables) {
              if (t.is_allowed) {
                  await updateTablePolicy(sourceData.id, t.id, false);
              }
          }
          await fetchCatalog(sourceData.id);
      }
  }

  if (isFetching) {
    return (
      <div className="page-container center-content">
        <RefreshCw className="spinner" size={32} />
      </div>
    );
  }

  return (
    <div className="page-container">
      <header className="page-header">
        <h1>Administration des données</h1>
        <p>Gérez vos sources, synchronisez le catalogue et configurez les autorisations d'accès strictes (Deny-All).</p>
      </header>

      <div className="page-content">
        {sourceData?.connected && !showForm ? (
          <div className="card source-card" style={{ marginBottom: '20px' }}>
            <div className="source-card-header">
              <div className="source-title">
                <Database size={24} color="#10b981" />
                <h3>Base de données principale ({sourceData.dialect})</h3>
              </div>
              <span className="status-badge success">
                <CheckCircle size={14} />
                Connecté
              </span>
            </div>
            <div className="source-card-body">
              <div className="stat-item">
                <span className="stat-value">{sourceData.table_count}</span>
                <span className="stat-label">Tables détectées</span>
              </div>
              <div className="stat-item">
                <span className="stat-value" style={{fontSize: '0.9rem'}}>{sourceData.last_synced_at ? new Date(sourceData.last_synced_at).toLocaleString() : 'Jamais'}</span>
                <span className="stat-label">Dernière synchro</span>
              </div>
            </div>
            <div className="source-card-actions">
              <button className="btn-primary" onClick={handleSync} disabled={isLoading}>
                {isLoading ? <RefreshCw className="spinner" size={16} /> : <RefreshCw size={16} />}
                &nbsp;Synchroniser le schéma
              </button>
              <button className="btn-secondary" onClick={() => setShowForm(true)}>
                Modifier la connexion
              </button>
            </div>
          </div>
        ) : (
          <div className="card connection-form-card" style={{ marginBottom: '20px' }}>
            <div className="form-header">
              <Link size={32} color="#3b82f6" />
              <h3>{sourceData?.connected ? "Modifier la connexion" : "Connecter une base de données"}</h3>
              <p>Configurer une source de données. L'accès sera bloqué par défaut jusqu'à autorisation explicite.</p>
            </div>
            
            <form onSubmit={handleConnect} className="connection-form">
              <div className="form-group">
                <label>Chaîne de connexion (Connection String)</label>
                <input 
                  type="password" 
                  value={connectionString} 
                  onChange={e => setConnectionString(e.target.value)}
                  placeholder="postgresql://user:password@localhost:5432/dbname"
                  required
                />
              </div>
              {error && <div className="error-message">{error}</div>}
              <div className="form-actions">
                {sourceData?.connected && (
                  <button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>Annuler</button>
                )}
            {activeTab === 'metrics' && (
                <div className="metrics-list" style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                        <h3 style={{ margin: 0 }}><BookOpen size={18} style={{ verticalAlign: 'middle', marginRight: '8px' }} /> Métriques Métier</h3>
                        <button className="btn-primary" onClick={() => setShowMetricForm(true)}><Plus size={16} /> Ajouter</button>
                    </div>

                    {showMetricForm && (
                        <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', marginBottom: '20px', border: '1px solid #e2e8f0' }}>
                            <form onSubmit={handleCreateMetric}>
                                <div className="form-group">
                                    <label>Nom de la métrique (ex: Chiffre d'Affaires)</label>
                                    <input type="text" value={newMetric.name} onChange={e => setNewMetric({...newMetric, name: e.target.value})} required />
                                </div>
                                <div className="form-group">
                                    <label>Description détaillée (utilisée par l'IA)</label>
                                    <textarea value={newMetric.description} onChange={e => setNewMetric({...newMetric, description: e.target.value})} rows="2"></textarea>
                                </div>
                                <div className="form-group">
                                    <label>Expression SQL (ex: SUM(total_amount))</label>
                                    <input type="text" value={newMetric.sql_expression} onChange={e => setNewMetric({...newMetric, sql_expression: e.target.value})} required style={{ fontFamily: 'monospace' }} />
                                </div>
                                <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                                    <button type="submit" className="btn-primary">Enregistrer</button>
                                    <button type="button" className="btn-secondary" onClick={() => setShowMetricForm(false)}>Annuler</button>
                                </div>
                            </form>
                        </div>
                    )}

                    {metrics.length === 0 && !showMetricForm ? (
                        <p style={{ color: '#64748b' }}>Aucune métrique définie. Ajoutez-en une pour aider l'IA à calculer vos indicateurs métier.</p>
                    ) : (
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                            <thead>
                                <tr style={{ borderBottom: '2px solid #e2e8f0', textAlign: 'left' }}>
                                    <th style={{ padding: '10px' }}>Nom</th>
                                    <th style={{ padding: '10px' }}>Description</th>
                                    <th style={{ padding: '10px' }}>SQL</th>
                                </tr>
                            </thead>
                            <tbody>
                                {metrics.map(m => (
                                    <tr key={m.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                        <td style={{ padding: '10px', fontWeight: '500' }}>{m.name}</td>
                                        <td style={{ padding: '10px', color: '#64748b' }}>{m.description}</td>
                                        <td style={{ padding: '10px', fontFamily: 'monospace', color: '#0369a1', background: '#f0f9ff', borderRadius: '4px' }}>{m.sql_expression}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            )}
                <button type="submit" className="btn-primary" disabled={isLoading}>
                  {isLoading ? "Connexion..." : "Enregistrer"}
                </button>
              </div>
            </form>
          </div>
        )}
            {activeTab === 'metrics' && (
                <div className="metrics-list" style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                        <h3 style={{ margin: 0 }}><BookOpen size={18} style={{ verticalAlign: 'middle', marginRight: '8px' }} /> Métriques Métier</h3>
                        <button className="btn-primary" onClick={() => setShowMetricForm(true)}><Plus size={16} /> Ajouter</button>
                    </div>

                    {showMetricForm && (
                        <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', marginBottom: '20px', border: '1px solid #e2e8f0' }}>
                            <form onSubmit={handleCreateMetric}>
                                <div className="form-group">
                                    <label>Nom de la métrique (ex: Chiffre d'Affaires)</label>
                                    <input type="text" value={newMetric.name} onChange={e => setNewMetric({...newMetric, name: e.target.value})} required />
                                </div>
                                <div className="form-group">
                                    <label>Description détaillée (utilisée par l'IA)</label>
                                    <textarea value={newMetric.description} onChange={e => setNewMetric({...newMetric, description: e.target.value})} rows="2"></textarea>
                                </div>
                                <div className="form-group">
                                    <label>Expression SQL (ex: SUM(total_amount))</label>
                                    <input type="text" value={newMetric.sql_expression} onChange={e => setNewMetric({...newMetric, sql_expression: e.target.value})} required style={{ fontFamily: 'monospace' }} />
                                </div>
                                <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                                    <button type="submit" className="btn-primary">Enregistrer</button>
                                    <button type="button" className="btn-secondary" onClick={() => setShowMetricForm(false)}>Annuler</button>
                                </div>
                            </form>
                        </div>
                    )}

                    {metrics.length === 0 && !showMetricForm ? (
                        <p style={{ color: '#64748b' }}>Aucune métrique définie. Ajoutez-en une pour aider l'IA à calculer vos indicateurs métier.</p>
                    ) : (
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                            <thead>
                                <tr style={{ borderBottom: '2px solid #e2e8f0', textAlign: 'left' }}>
                                    <th style={{ padding: '10px' }}>Nom</th>
                                    <th style={{ padding: '10px' }}>Description</th>
                                    <th style={{ padding: '10px' }}>SQL</th>
                                </tr>
                            </thead>
                            <tbody>
                                {metrics.map(m => (
                                    <tr key={m.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                        <td style={{ padding: '10px', fontWeight: '500' }}>{m.name}</td>
                                        <td style={{ padding: '10px', color: '#64748b' }}>{m.description}</td>
                                        <td style={{ padding: '10px', fontFamily: 'monospace', color: '#0369a1', background: '#f0f9ff', borderRadius: '4px' }}>{m.sql_expression}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            )}

        {sourceData?.connected && (
          <div className="admin-tabs">
            <div className="tabs-header" style={{ display: 'flex', gap: '10px', marginBottom: '20px', borderBottom: '1px solid #e2e8f0', paddingBottom: '10px' }}>
                <button className={`btn-secondary ${activeTab === 'catalog' ? 'active' : ''}`} onClick={() => setActiveTab('catalog')} style={{ background: activeTab === 'catalog' ? '#e2e8f0' : 'transparent' }}>Catalogue & Politiques</button>
                <button className={`btn-secondary ${activeTab === 'audit' ? 'active' : ''}`} onClick={() => setActiveTab('audit')} style={{ background: activeTab === 'audit' ? '#e2e8f0' : 'transparent' }}>Journal d'Audit</button>
                <button className={`btn-secondary ${activeTab === 'metrics' ? 'active' : ''}`} onClick={() => setActiveTab('metrics')} style={{ background: activeTab === 'metrics' ? '#e2e8f0' : 'transparent' }}>Métriques & Glossaire</button>
            </div>
            
            {activeTab === 'catalog' && (
                <div className="explorer-layout" style={{ height: '600px', border: '1px solid #e2e8f0', borderRadius: '8px', overflow: 'hidden' }}>
                  <div className="explorer-sidebar">
                    <div className="explorer-sidebar-header" style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                      <h3><LayoutList size={18} /> Tables ({tables.length})</h3>
                      <button onClick={handleDenyAll} style={{background: '#ef4444', color: 'white', border: 'none', padding: '4px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem'}}>Tout interdire</button>
                    </div>
                    <div className="table-list">
                      {tables.map(table => (
                        <div key={table.table_name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingRight: '10px' }} className={`table-list-item ${selectedTable?.table_name === table.table_name ? 'active' : ''}`}>
                          <button
                            style={{ flex: 1, textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}
                            onClick={() => setSelectedTable(table)}
                          >
                            <TableIcon size={16} />
                            <span style={{ color: table.is_allowed ? '#0f172a' : '#94a3b8', textDecoration: table.is_allowed ? 'none' : 'line-through' }}>{table.table_name}</span>
                          </button>
                          <label className="switch" style={{ margin: 0 }}>
                            <input type="checkbox" checked={table.is_allowed} onChange={() => handleTableToggle(table)} />
                            <span className="slider round"></span>
                          </label>
                        </div>
                      ))}
                    </div>
                  </div>
                  
                  <div className="explorer-content" style={{ padding: '20px', overflowY: 'auto' }}>
                    {selectedTable ? (
                      <div className="table-details-card">
                        <div className="table-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                          <div>
                            <h2>{selectedTable.table_name}</h2>
                            <p style={{ color: '#64748b' }}>Seules les tables et colonnes autorisées pourront être utilisées par l’agent.</p>
                          </div>
                          <div style={{ textAlign: 'right', fontSize: '0.85rem', color: '#64748b' }}>
                            <p>Modifié par: {selectedTable.modified_by || 'Système'}</p>
                            <p>Le: {selectedTable.last_modified_at ? new Date(selectedTable.last_modified_at).toLocaleString() : 'N/A'}</p>
                          </div>
                        </div>
                        
                        {!selectedTable.is_allowed && (
                            <div style={{ background: '#fef2f2', color: '#991b1b', padding: '12px', borderRadius: '6px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <Lock size={18} />
                                <strong>Cette table est interdite.</strong> Aucune colonne ne sera accessible, même si elles sont individuellement autorisées.
                            </div>
                        )}
            {activeTab === 'metrics' && (
                <div className="metrics-list" style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                        <h3 style={{ margin: 0 }}><BookOpen size={18} style={{ verticalAlign: 'middle', marginRight: '8px' }} /> Métriques Métier</h3>
                        <button className="btn-primary" onClick={() => setShowMetricForm(true)}><Plus size={16} /> Ajouter</button>
                    </div>

                    {showMetricForm && (
                        <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', marginBottom: '20px', border: '1px solid #e2e8f0' }}>
                            <form onSubmit={handleCreateMetric}>
                                <div className="form-group">
                                    <label>Nom de la métrique (ex: Chiffre d'Affaires)</label>
                                    <input type="text" value={newMetric.name} onChange={e => setNewMetric({...newMetric, name: e.target.value})} required />
                                </div>
                                <div className="form-group">
                                    <label>Description détaillée (utilisée par l'IA)</label>
                                    <textarea value={newMetric.description} onChange={e => setNewMetric({...newMetric, description: e.target.value})} rows="2"></textarea>
                                </div>
                                <div className="form-group">
                                    <label>Expression SQL (ex: SUM(total_amount))</label>
                                    <input type="text" value={newMetric.sql_expression} onChange={e => setNewMetric({...newMetric, sql_expression: e.target.value})} required style={{ fontFamily: 'monospace' }} />
                                </div>
                                <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                                    <button type="submit" className="btn-primary">Enregistrer</button>
                                    <button type="button" className="btn-secondary" onClick={() => setShowMetricForm(false)}>Annuler</button>
                                </div>
                            </form>
                        </div>
                    )}

                    {metrics.length === 0 && !showMetricForm ? (
                        <p style={{ color: '#64748b' }}>Aucune métrique définie. Ajoutez-en une pour aider l'IA à calculer vos indicateurs métier.</p>
                    ) : (
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                            <thead>
                                <tr style={{ borderBottom: '2px solid #e2e8f0', textAlign: 'left' }}>
                                    <th style={{ padding: '10px' }}>Nom</th>
                                    <th style={{ padding: '10px' }}>Description</th>
                                    <th style={{ padding: '10px' }}>SQL</th>
                                </tr>
                            </thead>
                            <tbody>
                                {metrics.map(m => (
                                    <tr key={m.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                        <td style={{ padding: '10px', fontWeight: '500' }}>{m.name}</td>
                                        <td style={{ padding: '10px', color: '#64748b' }}>{m.description}</td>
                                        <td style={{ padding: '10px', fontFamily: 'monospace', color: '#0369a1', background: '#f0f9ff', borderRadius: '4px' }}>{m.sql_expression}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            )}

                        <div className="table-schema">
                          <h3>Colonnes ({selectedTable.columns.length})</h3>
                          <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead>
                              <tr style={{ textAlign: 'left', borderBottom: '1px solid #e2e8f0' }}>
                                <th style={{ padding: '12px' }}>Statut</th>
                                <th style={{ padding: '12px' }}>Nom</th>
                                <th style={{ padding: '12px' }}>Type</th>
                                <th style={{ padding: '12px' }}>Modifié par</th>
                              </tr>
                            </thead>
                            <tbody>
                              {selectedTable.columns.map(col => (
                                <tr key={col.id} style={{ borderBottom: '1px solid #f1f5f9', opacity: selectedTable.is_allowed ? 1 : 0.6 }}>
                                  <td style={{ padding: '12px' }}>
                                    <label className="switch" style={{ margin: 0 }}>
                                      <input type="checkbox" checked={col.is_allowed} onChange={() => handleColumnToggle(selectedTable.id, col)} disabled={!selectedTable.is_allowed} />
                                      <span className="slider round"></span>
                                    </label>
                                  </td>
                                  <td className="col-name" style={{ padding: '12px', fontWeight: '500', color: col.is_allowed ? '#0f172a' : '#94a3b8', textDecoration: col.is_allowed ? 'none' : 'line-through' }}>{col.name}</td>
                                  <td className="col-type" style={{ padding: '12px' }}><span className="type-badge">{col.type}</span></td>
                                  <td style={{ padding: '12px', fontSize: '0.85rem', color: '#64748b' }}>{col.modified_by || 'Système'}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    ) : (
                      <div className="empty-state" style={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', color: '#94a3b8' }}>
                        <Settings size={48} style={{ marginBottom: '16px', opacity: 0.5 }} />
                        <p>Sélectionnez une table pour configurer ses accès</p>
                      </div>
                    )}
            {activeTab === 'metrics' && (
                <div className="metrics-list" style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                        <h3 style={{ margin: 0 }}><BookOpen size={18} style={{ verticalAlign: 'middle', marginRight: '8px' }} /> Métriques Métier</h3>
                        <button className="btn-primary" onClick={() => setShowMetricForm(true)}><Plus size={16} /> Ajouter</button>
                    </div>

                    {showMetricForm && (
                        <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', marginBottom: '20px', border: '1px solid #e2e8f0' }}>
                            <form onSubmit={handleCreateMetric}>
                                <div className="form-group">
                                    <label>Nom de la métrique (ex: Chiffre d'Affaires)</label>
                                    <input type="text" value={newMetric.name} onChange={e => setNewMetric({...newMetric, name: e.target.value})} required />
                                </div>
                                <div className="form-group">
                                    <label>Description détaillée (utilisée par l'IA)</label>
                                    <textarea value={newMetric.description} onChange={e => setNewMetric({...newMetric, description: e.target.value})} rows="2"></textarea>
                                </div>
                                <div className="form-group">
                                    <label>Expression SQL (ex: SUM(total_amount))</label>
                                    <input type="text" value={newMetric.sql_expression} onChange={e => setNewMetric({...newMetric, sql_expression: e.target.value})} required style={{ fontFamily: 'monospace' }} />
                                </div>
                                <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                                    <button type="submit" className="btn-primary">Enregistrer</button>
                                    <button type="button" className="btn-secondary" onClick={() => setShowMetricForm(false)}>Annuler</button>
                                </div>
                            </form>
                        </div>
                    )}

                    {metrics.length === 0 && !showMetricForm ? (
                        <p style={{ color: '#64748b' }}>Aucune métrique définie. Ajoutez-en une pour aider l'IA à calculer vos indicateurs métier.</p>
                    ) : (
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                            <thead>
                                <tr style={{ borderBottom: '2px solid #e2e8f0', textAlign: 'left' }}>
                                    <th style={{ padding: '10px' }}>Nom</th>
                                    <th style={{ padding: '10px' }}>Description</th>
                                    <th style={{ padding: '10px' }}>SQL</th>
                                </tr>
                            </thead>
                            <tbody>
                                {metrics.map(m => (
                                    <tr key={m.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                        <td style={{ padding: '10px', fontWeight: '500' }}>{m.name}</td>
                                        <td style={{ padding: '10px', color: '#64748b' }}>{m.description}</td>
                                        <td style={{ padding: '10px', fontFamily: 'monospace', color: '#0369a1', background: '#f0f9ff', borderRadius: '4px' }}>{m.sql_expression}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            )}
                  </div>
                </div>
            )}
            {activeTab === 'metrics' && (
                <div className="metrics-list" style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                        <h3 style={{ margin: 0 }}><BookOpen size={18} style={{ verticalAlign: 'middle', marginRight: '8px' }} /> Métriques Métier</h3>
                        <button className="btn-primary" onClick={() => setShowMetricForm(true)}><Plus size={16} /> Ajouter</button>
                    </div>

                    {showMetricForm && (
                        <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', marginBottom: '20px', border: '1px solid #e2e8f0' }}>
                            <form onSubmit={handleCreateMetric}>
                                <div className="form-group">
                                    <label>Nom de la métrique (ex: Chiffre d'Affaires)</label>
                                    <input type="text" value={newMetric.name} onChange={e => setNewMetric({...newMetric, name: e.target.value})} required />
                                </div>
                                <div className="form-group">
                                    <label>Description détaillée (utilisée par l'IA)</label>
                                    <textarea value={newMetric.description} onChange={e => setNewMetric({...newMetric, description: e.target.value})} rows="2"></textarea>
                                </div>
                                <div className="form-group">
                                    <label>Expression SQL (ex: SUM(total_amount))</label>
                                    <input type="text" value={newMetric.sql_expression} onChange={e => setNewMetric({...newMetric, sql_expression: e.target.value})} required style={{ fontFamily: 'monospace' }} />
                                </div>
                                <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                                    <button type="submit" className="btn-primary">Enregistrer</button>
                                    <button type="button" className="btn-secondary" onClick={() => setShowMetricForm(false)}>Annuler</button>
                                </div>
                            </form>
                        </div>
                    )}

                    {metrics.length === 0 && !showMetricForm ? (
                        <p style={{ color: '#64748b' }}>Aucune métrique définie. Ajoutez-en une pour aider l'IA à calculer vos indicateurs métier.</p>
                    ) : (
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                            <thead>
                                <tr style={{ borderBottom: '2px solid #e2e8f0', textAlign: 'left' }}>
                                    <th style={{ padding: '10px' }}>Nom</th>
                                    <th style={{ padding: '10px' }}>Description</th>
                                    <th style={{ padding: '10px' }}>SQL</th>
                                </tr>
                            </thead>
                            <tbody>
                                {metrics.map(m => (
                                    <tr key={m.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                        <td style={{ padding: '10px', fontWeight: '500' }}>{m.name}</td>
                                        <td style={{ padding: '10px', color: '#64748b' }}>{m.description}</td>
                                        <td style={{ padding: '10px', fontFamily: 'monospace', color: '#0369a1', background: '#f0f9ff', borderRadius: '4px' }}>{m.sql_expression}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            )}

            {activeTab === 'audit' && (
                <div className="audit-list" style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '20px' }}>
                    <h3 style={{ marginTop: 0, marginBottom: '20px' }}><Activity size={18} style={{ verticalAlign: 'middle', marginRight: '8px' }} /> Journal des modifications de politiques</h3>
                    {audits.length === 0 ? (
                        <p style={{ color: '#64748b' }}>Aucune action d'administration récente.</p>
                    ) : (
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                            <thead>
                                <tr style={{ borderBottom: '2px solid #e2e8f0', textAlign: 'left' }}>
                                    <th style={{ padding: '10px' }}>Date</th>
                                    <th style={{ padding: '10px' }}>Utilisateur</th>
                                    <th style={{ padding: '10px' }}>Action</th>
                                    <th style={{ padding: '10px' }}>Cible</th>
                                </tr>
                            </thead>
                            <tbody>
                                {audits.map(a => (
                                    <tr key={a.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                        <td style={{ padding: '10px', color: '#64748b' }}>{new Date(a.timestamp).toLocaleString()}</td>
                                        <td style={{ padding: '10px', fontWeight: '500' }}>{a.user_id}</td>
                                        <td style={{ padding: '10px' }}>
                                            <span style={{ 
                                                padding: '4px 8px', borderRadius: '4px', fontSize: '0.8rem',
                                                background: a.action.includes('allow') ? '#dcfce7' : (a.action.includes('deny') ? '#fee2e2' : '#e0e7ff'),
                                                color: a.action.includes('allow') ? '#166534' : (a.action.includes('deny') ? '#991b1b' : '#3730a3')
                                            }}>{a.action}</span>
                                        </td>
                                        <td style={{ padding: '10px', fontFamily: 'monospace' }}>{a.target}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
            {activeTab === 'metrics' && (
                <div className="metrics-list" style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                        <h3 style={{ margin: 0 }}><BookOpen size={18} style={{ verticalAlign: 'middle', marginRight: '8px' }} /> Métriques Métier</h3>
                        <button className="btn-primary" onClick={() => setShowMetricForm(true)}><Plus size={16} /> Ajouter</button>
                    </div>

                    {showMetricForm && (
                        <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', marginBottom: '20px', border: '1px solid #e2e8f0' }}>
                            <form onSubmit={handleCreateMetric}>
                                <div className="form-group">
                                    <label>Nom de la métrique (ex: Chiffre d'Affaires)</label>
                                    <input type="text" value={newMetric.name} onChange={e => setNewMetric({...newMetric, name: e.target.value})} required />
                                </div>
                                <div className="form-group">
                                    <label>Description détaillée (utilisée par l'IA)</label>
                                    <textarea value={newMetric.description} onChange={e => setNewMetric({...newMetric, description: e.target.value})} rows="2"></textarea>
                                </div>
                                <div className="form-group">
                                    <label>Expression SQL (ex: SUM(total_amount))</label>
                                    <input type="text" value={newMetric.sql_expression} onChange={e => setNewMetric({...newMetric, sql_expression: e.target.value})} required style={{ fontFamily: 'monospace' }} />
                                </div>
                                <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                                    <button type="submit" className="btn-primary">Enregistrer</button>
                                    <button type="button" className="btn-secondary" onClick={() => setShowMetricForm(false)}>Annuler</button>
                                </div>
                            </form>
                        </div>
                    )}

                    {metrics.length === 0 && !showMetricForm ? (
                        <p style={{ color: '#64748b' }}>Aucune métrique définie. Ajoutez-en une pour aider l'IA à calculer vos indicateurs métier.</p>
                    ) : (
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                            <thead>
                                <tr style={{ borderBottom: '2px solid #e2e8f0', textAlign: 'left' }}>
                                    <th style={{ padding: '10px' }}>Nom</th>
                                    <th style={{ padding: '10px' }}>Description</th>
                                    <th style={{ padding: '10px' }}>SQL</th>
                                </tr>
                            </thead>
                            <tbody>
                                {metrics.map(m => (
                                    <tr key={m.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                        <td style={{ padding: '10px', fontWeight: '500' }}>{m.name}</td>
                                        <td style={{ padding: '10px', color: '#64748b' }}>{m.description}</td>
                                        <td style={{ padding: '10px', fontFamily: 'monospace', color: '#0369a1', background: '#f0f9ff', borderRadius: '4px' }}>{m.sql_expression}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            )}
                </div>
            )}
            {activeTab === 'metrics' && (
                <div className="metrics-list" style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                        <h3 style={{ margin: 0 }}><BookOpen size={18} style={{ verticalAlign: 'middle', marginRight: '8px' }} /> Métriques Métier</h3>
                        <button className="btn-primary" onClick={() => setShowMetricForm(true)}><Plus size={16} /> Ajouter</button>
                    </div>

                    {showMetricForm && (
                        <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', marginBottom: '20px', border: '1px solid #e2e8f0' }}>
                            <form onSubmit={handleCreateMetric}>
                                <div className="form-group">
                                    <label>Nom de la métrique (ex: Chiffre d'Affaires)</label>
                                    <input type="text" value={newMetric.name} onChange={e => setNewMetric({...newMetric, name: e.target.value})} required />
                                </div>
                                <div className="form-group">
                                    <label>Description détaillée (utilisée par l'IA)</label>
                                    <textarea value={newMetric.description} onChange={e => setNewMetric({...newMetric, description: e.target.value})} rows="2"></textarea>
                                </div>
                                <div className="form-group">
                                    <label>Expression SQL (ex: SUM(total_amount))</label>
                                    <input type="text" value={newMetric.sql_expression} onChange={e => setNewMetric({...newMetric, sql_expression: e.target.value})} required style={{ fontFamily: 'monospace' }} />
                                </div>
                                <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                                    <button type="submit" className="btn-primary">Enregistrer</button>
                                    <button type="button" className="btn-secondary" onClick={() => setShowMetricForm(false)}>Annuler</button>
                                </div>
                            </form>
                        </div>
                    )}

                    {metrics.length === 0 && !showMetricForm ? (
                        <p style={{ color: '#64748b' }}>Aucune métrique définie. Ajoutez-en une pour aider l'IA à calculer vos indicateurs métier.</p>
                    ) : (
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                            <thead>
                                <tr style={{ borderBottom: '2px solid #e2e8f0', textAlign: 'left' }}>
                                    <th style={{ padding: '10px' }}>Nom</th>
                                    <th style={{ padding: '10px' }}>Description</th>
                                    <th style={{ padding: '10px' }}>SQL</th>
                                </tr>
                            </thead>
                            <tbody>
                                {metrics.map(m => (
                                    <tr key={m.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                        <td style={{ padding: '10px', fontWeight: '500' }}>{m.name}</td>
                                        <td style={{ padding: '10px', color: '#64748b' }}>{m.description}</td>
                                        <td style={{ padding: '10px', fontFamily: 'monospace', color: '#0369a1', background: '#f0f9ff', borderRadius: '4px' }}>{m.sql_expression}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            )}
          </div>
        )}
            {activeTab === 'metrics' && (
                <div className="metrics-list" style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                        <h3 style={{ margin: 0 }}><BookOpen size={18} style={{ verticalAlign: 'middle', marginRight: '8px' }} /> Métriques Métier</h3>
                        <button className="btn-primary" onClick={() => setShowMetricForm(true)}><Plus size={16} /> Ajouter</button>
                    </div>

                    {showMetricForm && (
                        <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', marginBottom: '20px', border: '1px solid #e2e8f0' }}>
                            <form onSubmit={handleCreateMetric}>
                                <div className="form-group">
                                    <label>Nom de la métrique (ex: Chiffre d'Affaires)</label>
                                    <input type="text" value={newMetric.name} onChange={e => setNewMetric({...newMetric, name: e.target.value})} required />
                                </div>
                                <div className="form-group">
                                    <label>Description détaillée (utilisée par l'IA)</label>
                                    <textarea value={newMetric.description} onChange={e => setNewMetric({...newMetric, description: e.target.value})} rows="2"></textarea>
                                </div>
                                <div className="form-group">
                                    <label>Expression SQL (ex: SUM(total_amount))</label>
                                    <input type="text" value={newMetric.sql_expression} onChange={e => setNewMetric({...newMetric, sql_expression: e.target.value})} required style={{ fontFamily: 'monospace' }} />
                                </div>
                                <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                                    <button type="submit" className="btn-primary">Enregistrer</button>
                                    <button type="button" className="btn-secondary" onClick={() => setShowMetricForm(false)}>Annuler</button>
                                </div>
                            </form>
                        </div>
                    )}

                    {metrics.length === 0 && !showMetricForm ? (
                        <p style={{ color: '#64748b' }}>Aucune métrique définie. Ajoutez-en une pour aider l'IA à calculer vos indicateurs métier.</p>
                    ) : (
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                            <thead>
                                <tr style={{ borderBottom: '2px solid #e2e8f0', textAlign: 'left' }}>
                                    <th style={{ padding: '10px' }}>Nom</th>
                                    <th style={{ padding: '10px' }}>Description</th>
                                    <th style={{ padding: '10px' }}>SQL</th>
                                </tr>
                            </thead>
                            <tbody>
                                {metrics.map(m => (
                                    <tr key={m.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                        <td style={{ padding: '10px', fontWeight: '500' }}>{m.name}</td>
                                        <td style={{ padding: '10px', color: '#64748b' }}>{m.description}</td>
                                        <td style={{ padding: '10px', fontFamily: 'monospace', color: '#0369a1', background: '#f0f9ff', borderRadius: '4px' }}>{m.sql_expression}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            )}
      </div>
    </div>
  );
}
