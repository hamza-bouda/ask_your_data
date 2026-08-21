import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Database, Link } from 'lucide-react';
import { registerDatabase } from '../services/api';

export default function ConnectDatabase() {
  const [connectionString, setConnectionString] = useState('postgresql://askyourdata:askyourdata_dev@postgres:5432/askyourdata');
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleConnect = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      // In real life, we would wait for the database introspection and embedding to complete
      await registerDatabase(connectionString);
      navigate('/chat');
    } catch (err) {
      setError("Impossible de se connecter à la base de données. Assurez-vous que l'URL est correcte.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', backgroundColor: '#0f172a' }}>
      <div style={{ padding: '2rem', backgroundColor: '#1e293b', borderRadius: '12px', width: '100%', maxWidth: '500px', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: '2rem' }}>
          <Link size={48} color="#10b981" style={{ marginBottom: '1rem' }} />
          <h2 style={{ color: 'white', margin: 0 }}>Connecter une base de données</h2>
          <p style={{ color: '#94a3b8', margin: '0.5rem 0 0 0', textAlign: 'center' }}>
            Nous allons analyser votre schéma pour permettre à l'IA de répondre à vos questions.
          </p>
          <div style={{ marginTop: '1.5rem', padding: '1rem', backgroundColor: 'rgba(239, 68, 68, 0.1)', borderLeft: '4px solid #ef4444', borderRadius: '4px' }}>
            <p style={{ color: '#f87171', margin: 0, fontSize: '0.875rem', fontWeight: '500' }}>
              ⚠️ Sécurité : Utilisez un compte en lecture seule (Read-Only)
            </p>
            <p style={{ color: '#fca5a5', margin: '0.5rem 0 0 0', fontSize: '0.75rem' }}>
              Par mesure de sécurité, veuillez fournir les accès à un utilisateur de base de données ayant uniquement les droits de lecture (SELECT). L'application n'exécute que des requêtes de lecture.
            </p>
          </div>
        </div>
        
        <form onSubmit={handleConnect} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label style={{ color: '#cbd5e1', fontSize: '0.875rem', marginBottom: '0.5rem', display: 'block' }}>Chaîne de connexion (Connection String)</label>
            <input 
              type="text" 
              value={connectionString} 
              onChange={e => setConnectionString(e.target.value)}
              placeholder="postgresql://user:password@localhost:5432/dbname"
              style={{ width: '100%', padding: '0.75rem', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }}
            />
          </div>
          
          {error && <div style={{ color: '#ef4444', fontSize: '0.875rem' }}>{error}</div>}
          
          <button 
            type="submit" 
            disabled={isLoading}
            style={{ marginTop: '1rem', width: '100%', padding: '0.75rem', backgroundColor: '#10b981', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold' }}
          >
            {isLoading ? "Connexion & Analyse en cours..." : "Connecter et Analyser"}
          </button>
        </form>
      </div>
    </div>
  );
}
