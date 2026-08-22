import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Database, Loader2 } from 'lucide-react';
import { login } from '../services/api';

export default function Login() {
  const [username, setUsername] = useState('hamza');
  const [password, setPassword] = useState('password');
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      const data = await login(username, password);
      localStorage.setItem('token', data.token);
      localStorage.setItem('user', JSON.stringify(data.user));
      navigate('/sources');
    } catch {
      setError("Identifiants incorrects ou serveur injoignable.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app-container" style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div className="glass-panel" style={{ padding: '2.5rem', width: '100%', maxWidth: '420px', margin: '0 16px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: '2rem', textAlign: 'center' }}>
          <div style={{ padding: '16px', background: 'rgba(59, 130, 246, 0.1)', borderRadius: '50%', marginBottom: '1rem' }}>
            <Database size={48} color="var(--accent)" />
          </div>
          <h2 style={{ color: 'var(--text-main)', margin: 0, fontSize: '1.75rem', fontWeight: '700' }}>Ask Your Data</h2>
          <p style={{ color: 'var(--text-muted)', margin: '0.5rem 0 0 0', fontSize: '1rem' }}>Connectez-vous à votre espace</p>
        </div>
        
        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label>Nom d'utilisateur</label>
            <input 
              type="text" 
              value={username} 
              onChange={e => setUsername(e.target.value)}
              placeholder="Saisissez votre identifiant"
              required
            />
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label>Mot de passe</label>
            <input 
              type="password" 
              value={password} 
              onChange={e => setPassword(e.target.value)}
              placeholder="Saisissez votre mot de passe"
              required
            />
          </div>
          
          {error && <div className="error-message" style={{ marginBottom: 0 }}>{error}</div>}
          
          <button 
            type="submit" 
            className="btn-primary"
            disabled={isLoading}
            style={{ marginTop: '0.5rem', width: '100%', padding: '0.875rem' }}
          >
            {isLoading ? (
              <>
                <Loader2 size={18} className="spinner" />
                <span>Connexion...</span>
              </>
            ) : "Se connecter"}
          </button>
        </form>
      </div>
    </div>
  );
}
