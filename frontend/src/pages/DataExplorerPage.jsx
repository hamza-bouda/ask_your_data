import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Database, KeyRound, LayoutList, RefreshCw, Search, Table as TableIcon } from 'lucide-react';
import { getTables, getDataSource, getTablePreview } from '../services/api';

export default function DataExplorerPage() {
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const fetchData = useCallback(async () => {
    setIsLoading(true); setError('');
    try {
      const source = await getDataSource();
      setIsConnected(Boolean(source.connected));
      if (!source.connected) { setTables([]); setSelectedTable(null); return; }
      const data = await getTables();
      const items = data.tables || [];
      setTables(items);
      setSelectedTable((current) => items.find((table) => table.table_name === current?.table_name) || items[0] || null);
    } catch (requestError) { setError(requestError.response?.data?.detail || 'Impossible de charger le catalogue de données.'); }
    finally { setIsLoading(false); }
  }, []);
  const fetchPreview = useCallback(async (tableName) => {
    if (!tableName) return;
    setPreviewLoading(true); setPreview(null); setPreviewError('');
    try { setPreview(await getTablePreview(tableName)); }
    catch { setPreviewError('Aperçu indisponible pour cette table. Vérifiez les droits de lecture et réessayez.'); }
    finally { setPreviewLoading(false); }
  }, []);
  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => { if (selectedTable) fetchPreview(selectedTable.table_name); }, [fetchPreview, selectedTable]);
  const filteredTables = useMemo(() => tables.filter((table) => table.table_name.toLowerCase().includes(query.trim().toLowerCase())), [query, tables]);
  if (isLoading) return <div className="page-container center-content"><RefreshCw className="spinner" size={32} /></div>;
  if (!isConnected && !error) return <div className="page-container center-content empty-state"><Database size={48} color="#475569" /><h2>Aucune source de données</h2><p>Connectez une base dans « Sources de données » pour explorer ses tables autorisées.</p></div>;
  return <div className="page-container explorer-layout"><aside className="explorer-sidebar"><header className="explorer-sidebar-header"><div><h3><LayoutList size={18} /> Tables</h3><span>{tables.length} autorisée(s)</span></div><button className="icon-btn" onClick={fetchData} disabled={isLoading} title="Actualiser le catalogue" aria-label="Actualiser le catalogue"><RefreshCw size={17} /></button></header><label className="explorer-search"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Rechercher une table" aria-label="Rechercher une table" /></label><div className="table-list">{filteredTables.length ? filteredTables.map((table) => <button key={table.table_name} className={`table-list-item ${selectedTable?.table_name === table.table_name ? 'active' : ''}`} onClick={() => setSelectedTable(table)}><TableIcon size={16} /><span>{table.table_name}</span><small>{table.columns.length}</small></button>) : <p className="table-list-empty">Aucune table ne correspond à cette recherche.</p>}</div></aside><section className="explorer-content">{error && <div className="error-message" role="alert">{error}</div>}{selectedTable ? <div className="table-details-card"><header className="table-header"><h2>{selectedTable.table_name}</h2><p>{selectedTable.description || 'Aucune description fournie par la source.'}</p><div className="schema-badges">{selectedTable.primary_key && <span><KeyRound size={13} /> Clé primaire : {selectedTable.primary_key}</span>}{selectedTable.foreign_keys?.length > 0 && <span>{selectedTable.foreign_keys.length} relation(s)</span>}{selectedTable.indices?.length > 0 && <span>{selectedTable.indices.length} index</span>}</div></header><section className="table-schema"><h3>Schéma des colonnes <span>{selectedTable.columns.length}</span></h3><div className="table-scroll"><table className="data-table"><thead><tr><th>Nom</th><th>Type</th><th>Description</th></tr></thead><tbody>{selectedTable.columns.map((column) => <tr key={column.name}><td className="col-name">{column.name}{selectedTable.primary_key === column.name && <KeyRound size={13} className="primary-key-icon" aria-label="Clé primaire" />}</td><td><span className="type-badge">{column.type}</span></td><td className="col-desc">{column.description || '—'}</td></tr>)}</tbody></table></div></section><section className="table-preview"><header><div><h3>Aperçu sécurisé</h3><p>Maximum 10 lignes · données soumises à vos politiques d’accès.</p></div><button className="btn-secondary" onClick={() => fetchPreview(selectedTable.table_name)} disabled={previewLoading}><RefreshCw size={15} className={previewLoading ? 'spinner' : ''} /> Actualiser</button></header>{previewError && <p className="error-message" role="alert">{previewError}</p>}{previewLoading && <p className="muted-copy">Chargement de l’aperçu…</p>}{preview && (preview.rows.length ? <div className="table-scroll"><table className="data-table"><thead><tr>{preview.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{preview.rows.map((row, index) => <tr key={index}>{preview.columns.map((column) => <td key={column}>{String(row[column] ?? '')}</td>)}</tr>)}</tbody></table></div> : <p className="muted-copy">Aucune ligne disponible.</p>)}</section></div> : <div className="empty-state"><TableIcon size={38} /><h2>Aucune table autorisée</h2><p>Demandez à un administrateur d’autoriser au moins une table dans le catalogue.</p></div>}</section></div>;
}
