import React, { useState, useEffect, useRef } from 'react';
import { Search, MessageSquare, PanelsTopLeft, Database, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { getConversations } from '../services/api';

export default function GlobalSearch({ isOpen, onClose }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const inputRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    } else {
      setQuery('');
      setResults([]);
    }
  }, [isOpen]);

  useEffect(() => {
    const fetchResults = async () => {
      if (!query.trim()) {
        setResults([]);
        return;
      }
      setIsLoading(true);
      try {
        // Mock search using conversations (which we can fetch)
        const convs = await getConversations();
        const filteredConvs = convs.filter(c => 
          (c.title || '').toLowerCase().includes(query.toLowerCase())
        );
        
        // We could also add dashboards here if we had an endpoint
        const formattedResults = filteredConvs.map(c => ({
          id: c.id,
          type: 'conversation',
          title: c.title || 'Nouvelle conversation',
          icon: MessageSquare,
          url: `/chat?conv=${c.id}`
        }));
        
        setResults(formattedResults);
      } catch (error) {
        console.error("Search failed", error);
      } finally {
        setIsLoading(false);
      }
    };

    const debounce = setTimeout(fetchResults, 300);
    return () => clearTimeout(debounce);
  }, [query]);

  const handleSelect = (url) => {
    onClose();
    navigate(url);
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose} style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 9999,
      display: 'flex', justifyContent: 'center', alignItems: 'flex-start', paddingTop: '10vh'
    }}>
      <div className="glass-panel" onClick={e => e.stopPropagation()} style={{
        width: '100%', maxWidth: '600px', padding: 0, overflow: 'hidden',
        border: '1px solid rgba(255,255,255,0.1)', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', padding: '16px 24px', borderBottom: '1px solid var(--border-color)' }}>
          <Search size={20} color="var(--text-muted)" style={{ marginRight: '16px' }} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Rechercher une conversation, un dashboard..."
            style={{ flex: 1, background: 'transparent', border: 'none', color: 'white', fontSize: '1.1rem', outline: 'none' }}
          />
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
            <X size={20} />
          </button>
        </div>

        <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
          {isLoading && <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>Recherche en cours...</div>}
          {!isLoading && query && results.length === 0 && (
            <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>Aucun résultat trouvé pour "{query}"</div>
          )}
          {!isLoading && results.length > 0 && (
            <ul style={{ listStyle: 'none', padding: '8px' }}>
              {results.map((item, idx) => (
                <li key={idx}>
                  <button
                    onClick={() => handleSelect(item.url)}
                    style={{
                      display: 'flex', alignItems: 'center', width: '100%', padding: '12px 16px',
                      background: 'transparent', border: 'none', color: 'var(--text-main)',
                      textAlign: 'left', cursor: 'pointer', borderRadius: '8px', gap: '12px'
                    }}
                    onMouseEnter={e => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.05)'}
                    onMouseLeave={e => e.currentTarget.style.backgroundColor = 'transparent'}
                  >
                    <item.icon size={18} color="var(--accent)" />
                    <span>{item.title}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {!query && (
            <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
              Commencez à taper pour rechercher dans tout l'espace de travail.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
