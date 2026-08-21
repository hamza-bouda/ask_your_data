import React, { useState, useEffect } from 'react';
import { Database, Table as TableIcon, LayoutList, RefreshCw } from 'lucide-react';
import { getTables, getDataSource, getTablePreview } from '../services/api';

export default function DataExplorerPage() {
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isConnected, setIsConnected] = useState(false);
  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const sourceData = await getDataSource();
        setIsConnected(sourceData.connected);
        
        if (sourceData.connected) {
          const tablesData = await getTables();
          setTables(tablesData.tables || []);
          if (tablesData.tables && tablesData.tables.length > 0) {
            setSelectedTable(tablesData.tables[0]);
          }
        }
      } catch (err) {
        console.error("Failed to fetch data explorer info", err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  useEffect(() => {
    if (!selectedTable) return;
    setPreview(null);
    setPreviewError(null);
    getTablePreview(selectedTable.table_name)
      .then(setPreview)
      .catch(() => setPreviewError("Aperçu indisponible pour cette table."));
  }, [selectedTable]);

  if (isLoading) {
    return (
      <div className="page-container center-content">
        <RefreshCw className="spinner" size={32} />
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="page-container center-content empty-state">
        <Database size={48} color="#475569" />
        <h2>Aucune source de données</h2>
        <p>Veuillez connecter une base de données dans la section "Sources de données" pour explorer les tables.</p>
      </div>
    );
  }

  return (
    <div className="page-container explorer-layout">
      <div className="explorer-sidebar">
        <div className="explorer-sidebar-header">
          <h3><LayoutList size={18} /> Tables ({tables.length})</h3>
        </div>
        <div className="table-list">
          {tables.map(table => (
            <button
              key={table.table_name}
              className={`table-list-item ${selectedTable?.table_name === table.table_name ? 'active' : ''}`}
              onClick={() => setSelectedTable(table)}
            >
              <TableIcon size={16} />
              <span>{table.table_name}</span>
            </button>
          ))}
        </div>
      </div>
      
      <div className="explorer-content">
        {selectedTable ? (
          <div className="table-details-card">
            <div className="table-header">
              <h2>{selectedTable.table_name}</h2>
              <p>{selectedTable.description}</p>

            <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
              {selectedTable.primary_key && <span style={{ background: '#fef3c7', color: '#92400e', padding: '4px 8px', borderRadius: '4px', fontSize: '0.8rem' }}>PK: {selectedTable.primary_key}</span>}
              {selectedTable.foreign_keys && selectedTable.foreign_keys.length > 0 && <span style={{ background: '#e0e7ff', color: '#3730a3', padding: '4px 8px', borderRadius: '4px', fontSize: '0.8rem' }}>Relations: {selectedTable.foreign_keys.length}</span>}
              {selectedTable.indices && selectedTable.indices.length > 0 && <span style={{ background: '#dcfce7', color: '#166534', padding: '4px 8px', borderRadius: '4px', fontSize: '0.8rem' }}>Index: {selectedTable.indices.length}</span>}
            </div>

            </div>
            
            <div className="table-schema">
              <h3>Schéma des colonnes ({selectedTable.columns.length})</h3>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Nom de la colonne</th>
                    <th>Type</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedTable.columns.map(col => (
                    <tr key={col.name}>
                                            <td className="col-name">
                        {col.name} {selectedTable.primary_key === col.name && <span title="Primary Key" style={{color: '#f59e0b', fontSize: '12px'}}>🔑</span>}
                      </td>
                      <td className="col-type"><span className="type-badge">{col.type}</span></td>
                      <td className="col-desc">{col.description || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            
            <div className="table-preview">
              <h3>Aperçu sécurisé (10 lignes maximum)</h3>
              {previewError && <p className="error-message">{previewError}</p>}
              {!preview && !previewError && <p>Chargement de l’aperçu…</p>}
              {preview && (
                preview.rows.length ? (
                  <div style={{ overflowX: 'auto' }}><table className="data-table"><thead><tr>{preview.columns.map(column => <th key={column}>{column}</th>)}</tr></thead><tbody>{preview.rows.map((row, index) => <tr key={index}>{preview.columns.map(column => <td key={column}>{String(row[column] ?? '')}</td>)}</tr>)}</tbody></table></div>
                ) : <p>Aucune ligne disponible.</p>
              )}
            </div>
          </div>
        ) : (
          <div className="empty-state">
            <p>Sélectionnez une table pour voir les détails</p>
          </div>
        )}
      </div>
    </div>
  );
}
