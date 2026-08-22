import React, { useState } from 'react';
import { Menu, X } from 'lucide-react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';

export default function AppLayout() {
  const [isNavigationOpen, setIsNavigationOpen] = useState(false);
  return (
    <div className="app-layout">
      <button
        className="mobile-nav-toggle"
        type="button"
        aria-label={isNavigationOpen ? 'Fermer la navigation' : 'Ouvrir la navigation'}
        aria-expanded={isNavigationOpen}
        onClick={() => setIsNavigationOpen((open) => !open)}
      >
        {isNavigationOpen ? <X size={22} /> : <Menu size={22} />}
      </button>
      {isNavigationOpen && <button className="mobile-nav-backdrop" type="button" aria-label="Fermer la navigation" onClick={() => setIsNavigationOpen(false)} />}
      <Sidebar isOpen={isNavigationOpen} onNavigate={() => setIsNavigationOpen(false)} />
      <main className="app-main-content">
        <Outlet />
      </main>
    </div>
  );
}
