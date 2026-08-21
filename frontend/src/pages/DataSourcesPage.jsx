import React, { useState, useEffect } from 'react';
import { Database, Link, CheckCircle, PlusCircle, RefreshCw } from 'lucide-react';
import { registerDatabase, getDataSource, syncAdminDatasource } from '../services/api';

export default function DataSourcesPage() {
  const [connectionString, setConnectionString] = useState('postgresql://askyourdata:askyourdata_dev@postgres:5432/askyourdata');
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(true);
  const [sourceData, setSourceData] = useState(null);
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    fetchSourceStatus();
  }, []);

  const fetchSourceStatus = async () => {
    setIsFetching(true);
    try {
      const data = await getDataSource();
      setSourceData(data);
    } catch (err) {
      console.error("Failed to fetch source status", err);
    } finally {
      setIsFetching(false);
    }
  };

  const handleConnect = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      await registerDatabase(connectionString);
      // The gateway validates that an admin can only operate on the source
      // belonging to the current tenant. Retrieve its server-issued id instead
      // of relying on an old placeholder such as "primary".
      const registeredSource = await getDataSource();
      if (!registeredSource?.id) {
        throw new Error('Datasource registration did not return a source id');
      }
      await syncAdminDatasource(registeredSource.id);
      setShowForm(false);
      await fetchSourceStatus();
    } catch (err) {
      setError("Impossible de connecter et synchroniser la base. Vérifiez l'URL et vos droits administrateur.");
    } finally {
      setIsLoading(false);
    }
  };

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
        <h1>Sources de données</h1>
        <p>Gérez vos connexions aux bases de données</p>
      </header>

      <div className="page-content">
        {sourceData?.connected && !showForm ? (
          <div className="card source-card">
            <div className="source-card-header">
              <div className="source-title">
                <Database size={24} color="#10b981" />
                <h3>Base de données principale</h3>
              </div>
              <span className="status-badge success">
                <CheckCircle size={14} />
                Connecté
              </span>
            </div>
            <div className="source-card-body">
              <div className="stat-item">
                <span className="stat-value">{sourceData.table_count}</span>
                <span className="stat-label">Tables indexées</span>
              </div>
            </div>
            <div className="source-card-actions">
              <button className="btn-secondary" onClick={() => setShowForm(true)}>
                Modifier la connexion
              </button>
            </div>
          </div>
        ) : (
          <div className="card connection-form-card">
            <div className="form-header">
              <Link size={32} color="#3b82f6" />
              <h3>{sourceData?.connected ? "Modifier la connexion" : "Connecter une base de données"}</h3>
              <p>Nous allons analyser votre schéma pour permettre à l'IA de répondre à vos questions.</p>
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
                  <button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>
                    Annuler
                  </button>
                )}
                <button 
                  type="submit" 
                  className="btn-primary"
                  disabled={isLoading}
                >
                  {isLoading ? "Connexion en cours..." : "Connecter et Analyser"}
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
