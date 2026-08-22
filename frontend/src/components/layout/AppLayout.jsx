import React, { useState, useEffect } from 'react';
import { Menu, X } from 'lucide-react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import GlobalSearch from '../GlobalSearch';

export default function AppLayout() {
  const [isNavigationOpen, setIsNavigationOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsSearchOpen(true);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

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
      <Sidebar 
        isOpen={isNavigationOpen} 
        onNavigate={() => setIsNavigationOpen(false)}
        onOpenSearch={() => {
          setIsNavigationOpen(false);
          setIsSearchOpen(true);
        }}
      />
      <main className="app-main-content">
        <Outlet />
      </main>
      <GlobalSearch isOpen={isSearchOpen} onClose={() => setIsSearchOpen(false)} />
    </div>
  );
}
