import React from 'react';
import { User, Shield, Key, Bell, LogOut } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function ProfilePage() {
  const navigate = useNavigate();
  // Simulate user data from token/local storage
  const userString = localStorage.getItem('user');
  let storedUser = {};
  try {
    storedUser = userString ? JSON.parse(userString) : {};
  } catch {
    storedUser = {};
  }
  const user = {
    username: storedUser.username || storedUser.id || 'Utilisateur',
    tenant: storedUser.tenant || storedUser.tenant_id || 'Organisation',
    roles: Array.isArray(storedUser.roles) && storedUser.roles.length ? storedUser.roles : ['Analyst'],
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/login');
  };

  return (
    <div className="page-container">
      <header className="page-header">
        <h1>Profil & Paramètres</h1>
        <p>Gérez vos informations personnelles et vos préférences</p>
      </header>

      <div className="page-content profile-layout">
        <div className="profile-sidebar">
          <div className="profile-avatar">
            <User size={48} color="#94a3b8" />
          </div>
          <h2 className="profile-name">{user.username}</h2>
          <p className="profile-tenant">{user.tenant}</p>
          
          <div className="profile-roles">
            {user.roles && user.roles.map(role => (
              <span key={role} className="role-badge">{role}</span>
            ))}
          </div>

          <button className="btn-secondary logout-full-btn" onClick={handleLogout}>
            <LogOut size={16} />
            Déconnexion
          </button>
        </div>

        <div className="profile-settings">
          <div className="settings-section">
            <h3><User size={18} /> Informations personnelles</h3>
            <div className="settings-grid">
              <div className="setting-item placeholder">
                <label>Nom complet</label>
                <div className="setting-value disabled">{user.username}</div>
              </div>
              <div className="setting-item placeholder">
                <label>Email</label>
                <div className="setting-value disabled">Non renseigné</div>
              </div>
            </div>
          </div>

          <div className="settings-section">
            <h3><Shield size={18} /> Sécurité & Accès</h3>
            <div className="settings-list placeholder-list">
              <div className="settings-list-item disabled">
                <Key size={18} />
                <div className="item-text">
                  <h4>Changer le mot de passe</h4>
                  <p>Mettre à jour votre mot de passe de connexion</p>
                </div>
              </div>
              <div className="settings-list-item disabled">
                <Shield size={18} />
                <div className="item-text">
                  <h4>Authentification à deux facteurs</h4>
                  <p>Non configurée (Bientôt disponible)</p>
                </div>
              </div>
            </div>
          </div>

          <div className="settings-section">
            <h3><Bell size={18} /> Préférences</h3>
            <div className="settings-list placeholder-list">
              <div className="settings-list-item disabled">
                <Bell size={18} />
                <div className="item-text">
                  <h4>Notifications</h4>
                  <p>Gérer les alertes par email</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
