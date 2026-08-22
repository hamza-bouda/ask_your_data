import React, { useState, useEffect, useRef } from 'react';
import { Search, MessageSquare, LayoutDashboard, Database, X, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { globalSearch } from '../services/api';

export default function GlobalSearch({ isOpen, onClose }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState({ conversations: [], dashboards: [], data_sources: [], total: 0 });
  const [isLoading, setIsLoading] = useState(false);
  const inputRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    } else {
      setQuery('');
      setResults({ conversations: [], dashboards: [], data_sources: [], total: 0 });
    }
  }, [isOpen]);

  useEffect(() => {
    const fetchResults = async () => {
      if (!query.trim()) {
        setResults({ conversations: [], dashboards: [], data_sources: [], total: 0 });
        return;
      }
      setIsLoading(true);
      try {
        const data = await globalSearch(query.trim(), 8);
        setResults(data);
      } catch (error) {
        console.error('Global search error:', error);
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

  const hasResults = results.total > 0;

  return (
    <div
      className="modal-overlay"
      onClick={onClose}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0,0,0,0.65)',
        backdropFilter: 'blur(4px)',
        zIndex: 9999,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'flex-start',
        paddingTop: '10vh',
      }}
    >
      <div
        className="glass-panel"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: '640px',
          padding: 0,
          overflow: 'hidden',
          backgroundColor: '#131722',
          border: '1px solid rgba(255,255,255,0.12)',
          boxShadow: '0 25px 50px -12px rgba(0,0,0,0.75)',
          borderRadius: '12px',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            padding: '16px 20px',
            borderBottom: '1px solid rgba(255,255,255,0.08)',
          }}
        >
          <Search size={20} color="var(--accent, #6366f1)" style={{ marginRight: '14px' }} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Rechercher des conversations, dashboards, sources de données..."
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              color: 'white',
              fontSize: '1.05rem',
              outline: 'none',
            }}
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              style={{
                background: 'none',
                border: 'none',
                color: 'rgba(255,255,255,0.5)',
                cursor: 'pointer',
                marginRight: '8px',
              }}
            >
              <X size={16} />
            </button>
          )}
          <button
            onClick={onClose}
            style={{
              background: 'rgba(255,255,255,0.08)',
              border: 'none',
              color: 'white',
              padding: '4px 8px',
              borderRadius: '4px',
              fontSize: '0.75rem',
              cursor: 'pointer',
            }}
          >
            ESC
          </button>
        </div>

        <div style={{ maxHeight: '420px', overflowY: 'auto', padding: '12px 16px' }}>
          {isLoading && (
            <div style={{ padding: '28px', textAlign: 'center', color: 'rgba(255,255,255,0.5)' }}>
              Recherche en cours...
            </div>
          )}

          {!isLoading && query && !hasResults && (
            <div style={{ padding: '28px', textAlign: 'center', color: 'rgba(255,255,255,0.5)' }}>
              Aucun résultat trouvé pour "{query}"
            </div>
          )}

          {!isLoading && hasResults && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {results.conversations.length > 0 && (
                <div>
                  <div
                    style={{
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      color: 'rgba(255,255,255,0.4)',
                      marginBottom: '6px',
                      paddingLeft: '8px',
                    }}
                  >
                    Conversations ({results.conversations.length})
                  </div>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                    {results.conversations.map((item) => (
                      <li key={item.id}>
                        <button
                          onClick={() => handleSelect(item.url)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            width: '100%',
                            padding: '10px 12px',
                            background: 'transparent',
                            border: 'none',
                            color: '#e2e8f0',
                            textAlign: 'left',
                            cursor: 'pointer',
                            borderRadius: '8px',
                            gap: '12px',
                            transition: 'background-color 0.15s ease',
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(99, 102, 241, 0.12)')}
                          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                        >
                          <MessageSquare size={16} color="#818cf8" />
                          <span style={{ flex: 1, fontSize: '0.92rem' }}>{item.title}</span>
                          <ArrowRight size={14} color="rgba(255,255,255,0.3)" />
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {results.dashboards.length > 0 && (
                <div>
                  <div
                    style={{
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      color: 'rgba(255,255,255,0.4)',
                      marginBottom: '6px',
                      paddingLeft: '8px',
                    }}
                  >
                    Tableaux de bord ({results.dashboards.length})
                  </div>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                    {results.dashboards.map((item) => (
                      <li key={item.id}>
                        <button
                          onClick={() => handleSelect(item.url)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            width: '100%',
                            padding: '10px 12px',
                            background: 'transparent',
                            border: 'none',
                            color: '#e2e8f0',
                            textAlign: 'left',
                            cursor: 'pointer',
                            borderRadius: '8px',
                            gap: '12px',
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(16, 185, 129, 0.12)')}
                          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                        >
                          <LayoutDashboard size={16} color="#34d399" />
                          <span style={{ flex: 1, fontSize: '0.92rem' }}>{item.title}</span>
                          <ArrowRight size={14} color="rgba(255,255,255,0.3)" />
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {results.data_sources.length > 0 && (
                <div>
                  <div
                    style={{
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      color: 'rgba(255,255,255,0.4)',
                      marginBottom: '6px',
                      paddingLeft: '8px',
                    }}
                  >
                    Sources de données ({results.data_sources.length})
                  </div>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                    {results.data_sources.map((item) => (
                      <li key={item.id}>
                        <button
                          onClick={() => handleSelect(item.url)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            width: '100%',
                            padding: '10px 12px',
                            background: 'transparent',
                            border: 'none',
                            color: '#e2e8f0',
                            textAlign: 'left',
                            cursor: 'pointer',
                            borderRadius: '8px',
                            gap: '12px',
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(245, 158, 11, 0.12)')}
                          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                        >
                          <Database size={16} color="#fbbf24" />
                          <span style={{ flex: 1, fontSize: '0.92rem' }}>{item.title}</span>
                          {item.dialect && (
                            <span
                              style={{
                                fontSize: '0.75rem',
                                padding: '2px 6px',
                                backgroundColor: 'rgba(255,255,255,0.1)',
                                borderRadius: '4px',
                                color: 'rgba(255,255,255,0.6)',
                              }}
                            >
                              {item.dialect}
                            </span>
                          )}
                          <ArrowRight size={14} color="rgba(255,255,255,0.3)" />
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {!query && (
            <div
              style={{
                padding: '28px',
                textAlign: 'center',
                color: 'rgba(255,255,255,0.4)',
                fontSize: '0.9rem',
              }}
            >
              Recherchez instantanément dans vos conversations, tableaux de bord et sources de données.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
