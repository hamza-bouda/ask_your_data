import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { MessageSquare, Database, LayoutDashboard, Settings, HardDrive, LogOut, Plug, PanelsTopLeft } from 'lucide-react';

export default function Sidebar({ isOpen = false, onNavigate = () => {} }) {
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
  }

  return (
    <aside className={`app-sidebar ${isOpen ? 'open' : ''}`}>
      <div className="sidebar-header">
        <h2>AskYourData</h2>
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
