import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Database, KeyRound, LayoutList, RefreshCw, Search, Table as TableIcon, Network, FileSpreadsheet, ChevronRight, ChevronLeft, Lightbulb, PlayCircle, Lock } from 'lucide-react';
import { getTables, getDataSource, getTablePreview } from '../services/api';

export default function DataExplorerPage() {
  const navigate = useNavigate();
  const [sourceName, setSourceName] = useState('');
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState(null);
  
  const [activeTab, setActiveTab] = useState('schema');
  
  const [isLoading, setIsLoading] = useState(true);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  
  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewOffset, setPreviewOffset] = useState(0);

  const fetchData = useCallback(async () => {
    setIsLoading(true); setError('');
    try {
      const source = await getDataSource();
      setIsConnected(Boolean(source.connected));
      if (!source.connected) { setTables([]); setSelectedTable(null); return; }
      setSourceName(source.name);
      const data = await getTables();
      const items = data.tables || [];
      setTables(items);
      setSelectedTable((current) => items.find((table) => table.table_name === current?.table_name) || items[0] || null);
    } catch (requestError) { setError(requestError.response?.data?.detail || 'Impossible de charger le catalogue de données.'); }
    finally { setIsLoading(false); }
  }, []);

  const fetchPreview = useCallback(async (tableName, offset = 0) => {
    if (!tableName) return;
    setPreviewLoading(true); setPreviewError('');
    try { 
      const newPreview = await getTablePreview(tableName, 10, offset);
      setPreview(newPreview);
    }
    catch { setPreviewError('Aperçu indisponible pour cette table. Vérifiez les droits de lecture et réessayez.'); }
    finally { setPreviewLoading(false); }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => { 
    if (selectedTable && activeTab === 'preview') {
      fetchPreview(selectedTable.table_name, previewOffset);
    }
  }, [fetchPreview, selectedTable, activeTab, previewOffset]);
  
  const handleTableSelect = (table) => {
    setSelectedTable(table);
    setPreviewOffset(0);
    setPreview(null);
    setActiveTab('schema');
  };

  const handleNextPage = () => setPreviewOffset(prev => prev + 10);
  const handlePrevPage = () => setPreviewOffset(prev => Math.max(0, prev - 10));

  const filteredTables = useMemo(() => tables.filter((table) => table.table_name.toLowerCase().includes(query.trim().toLowerCase())), [query, tables]);

  // Lineage logic
  const parentTables = useMemo(() => {
    if (!selectedTable || !selectedTable.foreign_keys) return [];
    return selectedTable.foreign_keys.map(fk => fk.referred_table);
  }, [selectedTable]);

  const childTables = useMemo(() => {
    if (!selectedTable || !tables) return [];
    return tables.filter(t => t.foreign_keys?.some(fk => fk.referred_table === selectedTable.table_name)).map(t => t.table_name);
  }, [selectedTable, tables]);

  const askBIQuestion = (question) => {
    navigate('/chat', { state: { initialMessage: question } });
  };

  if (isLoading) return <div className="page-container center-content"><RefreshCw className="spinner" size={32} /></div>;
  if (!isConnected && !error) return <div className="page-container center-content empty-state"><Database size={48} color="#475569" /><h2>Aucune source de données</h2><p>Connectez une base dans « Sources de données » pour explorer ses tables autorisées.</p></div>;
  
  return (
    <div className="page-container explorer-layout">
      <aside className="explorer-sidebar">
        <header className="explorer-sidebar-header">
          <div>
            <h3 style={{display: 'flex', alignItems: 'center'}}><Database size={16} style={{marginRight: 6}} /> {sourceName || 'Source'}</h3>
            <span style={{opacity: 0.7, fontSize: 12}}>{tables.length} table(s) autorisée(s)</span>
          </div>
          <button className="icon-btn" onClick={fetchData} disabled={isLoading} title="Actualiser le catalogue"><RefreshCw size={17} /></button>
        </header>
        <label className="explorer-search">
          <Search size={16} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Rechercher une table" />
        </label>
        <div className="table-list">
          {filteredTables.length ? filteredTables.map((table) => (
            <button key={table.table_name} className={`table-list-item ${selectedTable?.table_name === table.table_name ? 'active' : ''}`} onClick={() => handleTableSelect(table)}>
              <TableIcon size={16} />
              <span>{table.table_name}</span>
              <small>{table.columns.length}</small>
            </button>
          )) : <p className="table-list-empty">Aucune table ne correspond à cette recherche.</p>}
        </div>
      </aside>

      <section className="explorer-content">
        {error && <div className="error-message" role="alert">{error}</div>}
        {selectedTable ? (
          <div className="table-details-card">
            <header className="table-header">
              <div className="breadcrumb" style={{display: 'flex', alignItems: 'center', gap: 6, fontSize: '13px', color: '#64748b', marginBottom: 12}}>
                <span>{sourceName}</span> <ChevronRight size={14} /> <span>Schéma</span> <ChevronRight size={14} /> <strong style={{color: '#0f172a'}}>{selectedTable.table_name}</strong>
              </div>
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start'}}>
                <div>
                  <h2>{selectedTable.table_name}</h2>
                  <p>{selectedTable.description || 'Aucune description fournie par la source.'}</p>
                </div>
                <div style={{display: 'flex', alignItems: 'center', gap: 8, color: '#16a34a', fontSize: '13px', fontWeight: 500, backgroundColor: '#dcfce7', padding: '4px 10px', borderRadius: 12}}>
                   <Lock size={14} /> Accès autorisé
                </div>
              </div>
              <div className="schema-badges" style={{marginTop: 12}}>
                {selectedTable.primary_key && <span><KeyRound size={13} /> Clé primaire : {selectedTable.primary_key}</span>}
                {selectedTable.foreign_keys?.length > 0 && <span><Network size={13} /> {selectedTable.foreign_keys.length} relation(s)</span>}
                {selectedTable.indices?.length > 0 && <span>{selectedTable.indices.length} index</span>}
              </div>
            </header>
            
            <div className="explorer-tabs" style={{display: 'flex', borderBottom: '1px solid #e2e8f0', marginBottom: 20, gap: 20, padding: '0 20px'}}>
              <button className={`tab-btn ${activeTab === 'schema' ? 'active' : ''}`} onClick={() => setActiveTab('schema')} style={{padding: '12px 0', borderBottom: activeTab === 'schema' ? '2px solid #3b82f6' : '2px solid transparent', background: 'none', border: 'none', cursor: 'pointer', fontWeight: activeTab === 'schema' ? 600 : 400, color: activeTab === 'schema' ? '#3b82f6' : '#64748b', display: 'flex', alignItems: 'center', gap: 6}}><LayoutList size={16}/> Schéma</button>
              <button className={`tab-btn ${activeTab === 'preview' ? 'active' : ''}`} onClick={() => setActiveTab('preview')} style={{padding: '12px 0', borderBottom: activeTab === 'preview' ? '2px solid #3b82f6' : '2px solid transparent', background: 'none', border: 'none', cursor: 'pointer', fontWeight: activeTab === 'preview' ? 600 : 400, color: activeTab === 'preview' ? '#3b82f6' : '#64748b', display: 'flex', alignItems: 'center', gap: 6}}><FileSpreadsheet size={16}/> Aperçu des données</button>
              <button className={`tab-btn ${activeTab === 'relations' ? 'active' : ''}`} onClick={() => setActiveTab('relations')} style={{padding: '12px 0', borderBottom: activeTab === 'relations' ? '2px solid #3b82f6' : '2px solid transparent', background: 'none', border: 'none', cursor: 'pointer', fontWeight: activeTab === 'relations' ? 600 : 400, color: activeTab === 'relations' ? '#3b82f6' : '#64748b', display: 'flex', alignItems: 'center', gap: 6}}><Network size={16}/> Relations & Lignage</button>
              <button className={`tab-btn ${activeTab === 'bi' ? 'active' : ''}`} onClick={() => setActiveTab('bi')} style={{padding: '12px 0', borderBottom: activeTab === 'bi' ? '2px solid #3b82f6' : '2px solid transparent', background: 'none', border: 'none', cursor: 'pointer', fontWeight: activeTab === 'bi' ? 600 : 400, color: activeTab === 'bi' ? '#3b82f6' : '#64748b', display: 'flex', alignItems: 'center', gap: 6}}><Lightbulb size={16}/> Suggestions BI</button>
            </div>

            {activeTab === 'schema' && (
              <section className="table-schema" style={{padding: '0 20px 20px 20px'}}>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead><tr><th>Nom</th><th>Type</th><th>Attributs</th><th>Description</th></tr></thead>
                    <tbody>
                      {selectedTable.columns.map((column) => (
                        <tr key={column.name}>
                          <td className="col-name" style={{display: 'flex', alignItems: 'center', gap: 6}}>
                            {column.name}
                            {selectedTable.primary_key === column.name && <KeyRound size={13} className="primary-key-icon" title="Clé primaire" style={{color: '#eab308'}} />}
                            {selectedTable.foreign_keys?.some(fk => fk.constrained_columns.includes(column.name)) && <Network size={13} title="Clé étrangère" style={{color: '#3b82f6'}} />}
                          </td>
                          <td><span className="type-badge">{column.type}</span></td>
                          <td>
                            <div style={{display: 'flex', gap: 4}}>
                              {!column.is_nullable && <span style={{fontSize: 11, background: '#f1f5f9', padding: '2px 6px', borderRadius: 4, color: '#475569'}}>NOT NULL</span>}
                              {column.is_nullable && <span style={{fontSize: 11, background: '#f8fafc', padding: '2px 6px', borderRadius: 4, color: '#94a3b8'}}>NULL</span>}
                            </div>
                          </td>
                          <td className="col-desc">{column.description || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            {activeTab === 'preview' && (
              <section className="table-preview" style={{padding: '0 20px 20px 20px'}}>
                <header style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16}}>
                  <div>
                    <h3 style={{margin: 0, fontSize: 16}}>Aperçu paginé</h3>
                    <p style={{margin: '4px 0 0 0', fontSize: 13, color: '#64748b'}}>Maximum 10 lignes par page · données soumises à vos politiques d’accès.</p>
                  </div>
                  <div style={{display: 'flex', gap: 8, alignItems: 'center'}}>
                    <button className="icon-btn" onClick={handlePrevPage} disabled={previewLoading || previewOffset === 0}><ChevronLeft size={18} /></button>
                    <span style={{fontSize: 13, color: '#475569'}}>Offset: {previewOffset}</span>
                    <button className="icon-btn" onClick={handleNextPage} disabled={previewLoading || !preview?.rows || preview.rows.length < 10}><ChevronRight size={18} /></button>
                    <button className="btn-secondary" onClick={() => fetchPreview(selectedTable.table_name, previewOffset)} disabled={previewLoading} style={{marginLeft: 8}}><RefreshCw size={15} className={previewLoading ? 'spinner' : ''} /> Actualiser</button>
                  </div>
                </header>
                {previewError && <p className="error-message" role="alert">{previewError}</p>}
                {previewLoading && <div style={{padding: 40, textAlign: 'center', color: '#64748b'}}><RefreshCw className="spinner" size={24} style={{marginBottom: 8}}/> <p>Chargement des données...</p></div>}
                {!previewLoading && preview && (
                  preview.rows.length ? (
                    <div className="table-scroll">
                      <table className="data-table">
                        <thead><tr>{preview.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
                        <tbody>
                          {preview.rows.map((row, index) => (
                            <tr key={index}>
                              {preview.columns.map((column) => <td key={column}>{String(row[column] ?? '')}</td>)}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : <p className="muted-copy" style={{padding: 20, textAlign: 'center'}}>Aucune ligne disponible.</p>
                )}
              </section>
            )}

            {activeTab === 'relations' && (
              <section className="table-relations" style={{padding: '0 20px 20px 20px'}}>
                 <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24}}>
                    <div className="relations-card" style={{border: '1px solid #e2e8f0', borderRadius: 8, padding: 16}}>
                      <h4 style={{margin: '0 0 12px 0', display: 'flex', alignItems: 'center', gap: 6}}><ChevronRight size={16}/> Tables parentes (Référencées par {selectedTable.table_name})</h4>
                      {parentTables.length > 0 ? (
                        <ul style={{listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 8}}>
                          {parentTables.map((t, idx) => (
                             <li key={idx} style={{display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, color: '#334155', background: '#f8fafc', padding: '8px 12px', borderRadius: 6}}>
                               <TableIcon size={14} color="#64748b" /> {t}
                             </li>
                          ))}
                        </ul>
                      ) : <p style={{fontSize: 13, color: '#64748b', margin: 0}}>Aucune table parente détectée.</p>}
                    </div>

                    <div className="relations-card" style={{border: '1px solid #e2e8f0', borderRadius: 8, padding: 16}}>
                      <h4 style={{margin: '0 0 12px 0', display: 'flex', alignItems: 'center', gap: 6}}><ChevronLeft size={16}/> Tables enfants (Référencent {selectedTable.table_name})</h4>
                      {childTables.length > 0 ? (
                        <ul style={{listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 8}}>
                          {childTables.map((t, idx) => (
                             <li key={idx} style={{display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, color: '#334155', background: '#f8fafc', padding: '8px 12px', borderRadius: 6}}>
                               <TableIcon size={14} color="#64748b" /> {t}
                             </li>
                          ))}
                        </ul>
                      ) : <p style={{fontSize: 13, color: '#64748b', margin: 0}}>Aucune table enfant détectée.</p>}
                    </div>
                 </div>
              </section>
            )}

            {activeTab === 'bi' && (
              <section className="table-bi-suggestions" style={{padding: '0 20px 20px 20px'}}>
                <h3 style={{fontSize: 16, marginTop: 0, marginBottom: 16}}>Démarrer une analyse</h3>
                <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16}}>
                  {[
                    `Combien y a-t-il d'enregistrements dans ${selectedTable.table_name} ?`,
                    `Quelle est l'évolution des données dans ${selectedTable.table_name} au fil du temps ?`,
                    `Affiche-moi le top 10 des éléments de ${selectedTable.table_name}.`,
                    `Quelle est la répartition par catégories dans ${selectedTable.table_name} ?`,
                    `Vérifie la qualité des données (valeurs nulles, doublons) dans ${selectedTable.table_name}.`
                  ].map((question, idx) => (
                    <button key={idx} onClick={() => askBIQuestion(question)} style={{display: 'flex', textAlign: 'left', alignItems: 'flex-start', gap: 12, padding: 16, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, cursor: 'pointer', transition: 'all 0.2s'}} onMouseOver={(e) => e.currentTarget.style.borderColor = '#3b82f6'} onMouseOut={(e) => e.currentTarget.style.borderColor = '#e2e8f0'}>
                      <PlayCircle size={20} color="#3b82f6" style={{flexShrink: 0, marginTop: 2}} />
                      <div>
                         <span style={{fontSize: 14, fontWeight: 500, color: '#1e293b'}}>{question}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </section>
            )}

          </div>
        ) : (
          <div className="empty-state">
            <TableIcon size={38} />
            <h2>Aucune table autorisée</h2>
            <p>Demandez à un administrateur d’autoriser au moins une table dans le catalogue.</p>
          </div>
        )}
      </section>
    </div>
  );
}
