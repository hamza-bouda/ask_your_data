import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { MessageSquare, Database, LayoutDashboard, Settings, HardDrive, LogOut, Plug, PanelsTopLeft, Activity, Search, HelpCircle } from 'lucide-react';

export default function Sidebar({ isOpen = false, onNavigate = () => {}, onOpenSearch = () => {} }) {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    localStorage.removeItem('activeSourceId');
    onNavigate();
    navigate('/login');
  };

  const userStr = localStorage.getItem('user');
  let user = null;
  try { user = userStr ? JSON.parse(userStr) : null; } catch { user = null; }
  const isAdmin = user && user.roles && user.roles.includes('admin');

  const navItems = [
    { to: "/chat", icon: MessageSquare, label: "Conversations" },
    { to: "/sources", icon: Plug, label: "Sources de données" },
    { to: "/explorer", icon: LayoutDashboard, label: "Explorer les données" },
    { to: "/results", icon: Database, label: "Résultats" },
    { to: "/dashboards", icon: PanelsTopLeft, label: "Dashboards" }
  ];
  
  if (isAdmin) {
    navItems.push({ to: "/admin/data", icon: HardDrive, label: "Administration des données" });
    navItems.push({ to: "/admin/health", icon: Activity, label: "Santé de la plateforme" });
  }

  return (
    <aside className={`app-sidebar ${isOpen ? 'open' : ''}`}>
      <div className="sidebar-header" style={{ display: 'flex', flexDirection: 'column', alignItems: 'stretch' }}>
        <h2 style={{ marginBottom: '16px' }}>AskYourData</h2>
        <button 
          className="nav-item" 
          onClick={onOpenSearch}
          style={{ width: '100%', justifyContent: 'space-between', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-color)' }}
        >
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <Search size={18} style={{ marginRight: '12px' }} />
            <span>Recherche</span>
          </div>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', background: 'var(--panel-bg)', padding: '2px 6px', borderRadius: '4px' }}>⌘K</span>
        </button>
      </div>
      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <NavLink 
            key={item.to} 
            to={item.to} 
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            onClick={onNavigate}
          >
            <item.icon size={20} />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-footer">
        <NavLink to="/help" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} onClick={onNavigate}>
          <HelpCircle size={20} />
          <span>Centre d'aide</span>
        </NavLink>
        <NavLink to="/profile" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} onClick={onNavigate}>
          <Settings size={20} />
          <span>Profil & Paramètres</span>
        </NavLink>
        <button onClick={handleLogout} className="nav-item logout-btn">
          <LogOut size={20} />
          <span>Déconnexion</span>
        </button>
      </div>
    </aside>
  );
}
