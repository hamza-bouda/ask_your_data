import React, { useEffect, useMemo, useState } from 'react';
import { Database, ExternalLink, LogOut, ShieldCheck, User } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { getActiveSourceId, getDataSources } from '../services/api';

const storedUser = () => { try { return JSON.parse(localStorage.getItem('user') || '{}'); } catch { return {}; } };

export default function ProfilePage() {
  const navigate = useNavigate();
  const [sources, setSources] = useState([]);
  const [sourceError, setSourceError] = useState(false);
  const user = useMemo(() => {
    const data = storedUser();
    return { username: data.username || data.id || 'Utilisateur', tenant: data.tenant || data.tenant_id || 'Organisation', roles: Array.isArray(data.roles) && data.roles.length ? data.roles : ['analyst'] };
  }, []);
  const activeSourceId = getActiveSourceId();
  const activeSource = sources.find((source) => source.id === activeSourceId);
  useEffect(() => { getDataSources().then(setSources).catch(() => setSourceError(true)); }, []);
  const handleLogout = () => { localStorage.removeItem('token'); localStorage.removeItem('user'); localStorage.removeItem('activeSourceId'); navigate('/login'); };

  return <div className="page-container"><header className="page-header"><h1>Profil & espace de travail</h1><p>Consultez votre accès, votre organisation et le périmètre de données actif.</p></header><div className="page-content profile-layout"><aside className="profile-sidebar"><div className="profile-avatar"><User size={48} color="#94a3b8" /></div><h2 className="profile-name">{user.username}</h2><p className="profile-tenant">{user.tenant}</p><div className="profile-roles">{user.roles.map((role) => <span key={role} className="role-badge">{role}</span>)}</div><button className="btn-secondary logout-full-btn" onClick={handleLogout}><LogOut size={16} /> Déconnexion</button></aside><section className="profile-settings"><section className="settings-section"><h3><User size={18} /> Compte</h3><div className="settings-grid"><div className="setting-item"><label>Identifiant</label><div className="setting-value">{user.username}</div></div><div className="setting-item"><label>Organisation</label><div className="setting-value">{user.tenant}</div></div></div></section><section className="settings-section"><h3><Database size={18} /> Périmètre de données actif</h3><div className="profile-source-card"><div><strong>{activeSource?.name || 'Aucune source sélectionnée'}</strong><p>{sourceError ? 'Les sources sont momentanément indisponibles.' : activeSource ? `${activeSource.table_count} table(s) indexée(s) · ${activeSource.dialect || 'moteur non précisé'}` : 'Sélectionnez une source avant de démarrer une nouvelle analyse.'}</p></div><Link className="btn-secondary" to="/sources">Gérer les sources <ExternalLink size={15} /></Link></div></section><section className="settings-section"><h3><ShieldCheck size={18} /> Accès & sécurité</h3><div className="settings-list"><div className="settings-list-item"><ShieldCheck size={20} /><div className="item-text"><h4>Rôles appliqués à cette session</h4><p>{user.roles.join(', ')}. Les tables et colonnes restent filtrées par la politique de gouvernance de la source.</p></div></div><div className="settings-list-item"><LogOut size={20} /><div className="item-text"><h4>Session locale</h4><p>La déconnexion supprime le jeton et la sélection de source de ce navigateur.</p></div></div></div></section></section></div></div>;
}
