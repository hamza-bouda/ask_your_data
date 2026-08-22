import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Database, RefreshCw, Lock, Table as TableIcon, ArrowRight, CheckCircle, BarChart2 } from 'lucide-react';
import { registerDatabase, syncAdminDatasource, getAdminCatalog, updateTablePolicy, setActiveSourceId, createConversation } from '../services/api';

export default function OnboardingPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [connectionString, setConnectionString] = useState('');
  const [name, setName] = useState('');
  const [sourceData, setSourceData] = useState(null);
  const [tables, setTables] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Step 4 & 5 states
  const [question, setQuestion] = useState('');

  const handleConnect = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      const registered = await registerDatabase(connectionString, { name: name.trim() });
      setSourceData(registered);
      setActiveSourceId(registered.id);
      setStep(2);
      
      // Auto trigger sync
      await syncAdminDatasource(registered.id);
      
      // Fetch catalog for next step
      const data = await getAdminCatalog(registered.id);
      setTables(data.tables || []);
      setStep(3);
    } catch {
      setError('Impossible de se connecter à la base. Vérifiez la chaîne et les droits read-only.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleTableToggle = async (table) => {
    if (!sourceData?.id) return;
    const isAllowed = !table.is_allowed;
    try {
      await updateTablePolicy(sourceData.id, table.id, isAllowed);
      setTables(current => current.map(item => item.id === table.id ? { ...item, is_allowed: isAllowed } : item));
    } catch {
      setError('La politique de table n\'a pas pu être mise à jour.');
    }
  };

  const askFirstQuestion = async (e) => {
    e.preventDefault();
    if (!question.trim() || !sourceData?.id) return;
    setIsLoading(true);
    setError(null);
    try {
      const conv = await createConversation("Ma première question", sourceData.id);
      // Pass the question in state so ConversationsPage can auto-send it
      navigate('/chat', { state: { autoSend: question, conversationId: conv.id } });
    } catch {
      setError("Erreur lors de la création de la question.");
      setIsLoading(false);
    }
  };

  return (
    <div className="app-container" style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div className="glass-panel" style={{ padding: '40px', width: '100%', maxWidth: '650px', textAlign: 'left', margin: '0 16px' }}>
        <div style={{ marginBottom: '32px', textAlign: 'center' }}>
          <h1 style={{ fontSize: '2rem', marginBottom: '8px', color: 'var(--text-main)' }}>Bienvenue sur Ask Your Data</h1>
          <p style={{ color: 'var(--text-muted)' }}>Configurons votre première source de données en quelques minutes.</p>
        </div>

        {/* Stepper */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '40px', position: 'relative' }}>
          <div style={{ position: 'absolute', top: '15px', left: '0', right: '0', height: '2px', background: 'var(--border-color)', zIndex: 0 }} />
          
          {[1, 2, 3, 4].map(num => (
            <div key={num} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 1, background: 'var(--panel-bg)', padding: '0 10px', borderRadius: '50%' }}>
              <div style={{ 
                width: '32px', height: '32px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: step >= num ? 'var(--accent)' : 'var(--panel-bg)',
                border: `1px solid ${step >= num ? 'var(--accent)' : 'var(--border-color)'}`,
                color: step >= num ? 'white' : 'var(--text-muted)',
                fontWeight: 'bold', transition: 'all 0.3s'
              }}>
                {step > num ? <CheckCircle size={18} /> : num}
              </div>
            </div>
          ))}
        </div>

        {error && <div className="error-message">{error}</div>}

        {step === 1 && (
          <div style={{ animation: 'fadeIn 0.3s ease-out' }}>
            <h2 style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-main)' }}><Database size={24} color="var(--accent)" /> Connexion à votre base</h2>
            <form onSubmit={handleConnect}>
              <div className="form-group">
                <label>Nom du projet (ex: Chinook Sales)</label>
                <input value={name} onChange={e => setName(e.target.value)} required placeholder="Mon Projet BI" />
              </div>
              <div className="form-group">
                <label>Chaîne de connexion (Read-Only)</label>
                <input type="password" value={connectionString} onChange={e => setConnectionString(e.target.value)} required placeholder="postgresql://user:password@host:5432/db" />
              </div>
              <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '16px' }} disabled={isLoading}>
                {isLoading ? <><RefreshCw className="spinner" size={16} /> Connexion...</> : 'Connecter & Synchroniser'}
              </button>
            </form>
          </div>
        )}

        {step === 2 && (
          <div style={{ animation: 'fadeIn 0.3s ease-out', padding: '40px 0', textAlign: 'center' }}>
            <RefreshCw className="spinner" size={48} color="var(--accent)" style={{ margin: '0 auto 24px' }} />
            <h2 style={{ color: 'var(--text-main)' }}>Analyse de la structure...</h2>
            <p style={{ color: 'var(--text-muted)', maxWidth: '400px', margin: '16px auto' }}>Nous parcourons vos tables et schémas pour préparer l'intelligence artificielle.</p>
          </div>
        )}

        {step === 3 && (
          <div style={{ animation: 'fadeIn 0.3s ease-out' }}>
            <h2 style={{ marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-main)' }}><Lock size={24} color="var(--accent)" /> Gouvernance des données</h2>
            <p style={{ color: 'var(--text-muted)', marginBottom: '24px' }}>Sélectionnez les tables qui seront accessibles par vos utilisateurs. Vous pourrez affiner colonne par colonne plus tard.</p>
            
            <div style={{ maxHeight: '300px', overflowY: 'auto', border: '1px solid var(--border-color)', borderRadius: 'var(--border-radius-md)', padding: '12px', background: 'rgba(0,0,0,0.2)' }}>
              {tables.map(table => (
                <div key={table.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '12px', borderBottom: '1px solid var(--border-color)', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <TableIcon size={16} color="var(--text-muted)" />
                    <span style={{ color: table.is_allowed ? 'var(--text-main)' : 'var(--text-muted)', textDecoration: table.is_allowed ? 'none' : 'line-through' }}>{table.table_name}</span>
                  </div>
                  <label className="switch">
                    <input type="checkbox" checked={Boolean(table.is_allowed)} onChange={() => handleTableToggle(table)} />
                    <span className="slider round" />
                  </label>
                </div>
              ))}
            </div>
            
            <button className="btn-primary" style={{ width: '100%', marginTop: '24px' }} onClick={() => setStep(4)}>
              Continuer vers l'exploration <ArrowRight size={16} />
            </button>
          </div>
        )}

        {step === 4 && (
          <div style={{ animation: 'fadeIn 0.3s ease-out' }}>
            <h2 style={{ marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-main)' }}><BarChart2 size={24} color="var(--accent)" /> Posez votre première question</h2>
            <p style={{ color: 'var(--text-muted)', marginBottom: '24px' }}>Votre base est prête ! Essayez de poser une question en langage naturel.</p>
            
            <form onSubmit={askFirstQuestion}>
              <div className="form-group">
                <input 
                  value={question} 
                  onChange={e => setQuestion(e.target.value)} 
                  required 
                  placeholder="Ex: Quel est le chiffre d'affaires par mois ?" 
                  autoFocus
                  style={{ fontSize: '1.1rem', padding: '16px' }}
                />
              </div>
              <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '16px' }} disabled={isLoading}>
                {isLoading ? <><RefreshCw className="spinner" size={16} /> Création...</> : 'Générer le graphique'}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
