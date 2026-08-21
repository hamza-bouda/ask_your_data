import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Database } from 'lucide-react';
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
    } catch (err) {
      setError("Identifiants incorrects ou serveur injoignable.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', backgroundColor: '#0f172a' }}>
      <div style={{ padding: '2rem', backgroundColor: '#1e293b', borderRadius: '12px', width: '100%', maxWidth: '400px', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: '2rem' }}>
          <Database size={48} color="#3b82f6" style={{ marginBottom: '1rem' }} />
          <h2 style={{ color: 'white', margin: 0 }}>Ask Your Data</h2>
          <p style={{ color: '#94a3b8', margin: '0.5rem 0 0 0' }}>Connectez-vous à votre espace</p>
        </div>
        
        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label style={{ color: '#cbd5e1', fontSize: '0.875rem', marginBottom: '0.5rem', display: 'block' }}>Nom d'utilisateur</label>
            <input 
              type="text" 
              value={username} 
              onChange={e => setUsername(e.target.value)}
              style={{ width: '100%', padding: '0.75rem', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }}
            />
          </div>
          <div>
            <label style={{ color: '#cbd5e1', fontSize: '0.875rem', marginBottom: '0.5rem', display: 'block' }}>Mot de passe</label>
            <input 
              type="password" 
              value={password} 
              onChange={e => setPassword(e.target.value)}
              style={{ width: '100%', padding: '0.75rem', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }}
            />
          </div>
          
          {error && <div style={{ color: '#ef4444', fontSize: '0.875rem' }}>{error}</div>}
          
          <button 
            type="submit" 
            disabled={isLoading}
            style={{ marginTop: '1rem', width: '100%', padding: '0.75rem', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold' }}
          >
            {isLoading ? "Connexion..." : "Se connecter"}
          </button>
        </form>
      </div>
    </div>
  );
}
