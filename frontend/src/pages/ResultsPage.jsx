import React, { useState, useEffect } from 'react';
import { Database, LineChart, FileText, ChevronRight } from 'lucide-react';
import { getConversations, getConversation } from '../services/api';
import ChartRenderer from '../components/ChartRenderer';

export default function ResultsPage() {
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedResult, setSelectedResult] = useState(null);

  useEffect(() => {
    const fetchAllResults = async () => {
      try {
        const convs = await getConversations();
        const allResults = [];
        
        for (const conv of convs) {
          const detail = await getConversation(conv.id);
          for (const msg of detail.messages) {
            if (msg.role === 'ai' || msg.role === 'assistant') {
              if (
                ['DATA_QUERY', 'CHART_GENERATION'].includes(msg.payload?.semantic_plan?.intent)
                && Array.isArray(msg.payload.results)
                && msg.payload.results.length > 0
              ) {
                allResults.push({
                  id: msg.id,
                  date: msg.created_at,
                  title: msg.payload.chart_spec?.title || `Résultat de ${conv.title}`,
                  conversationTitle: conv.title,
                  data: msg.payload.results,
                  chartSpec: msg.payload.chart_spec,
                  sql: msg.payload.sql_query
                });
              }
            }
          }
        }
        
        // Sort by date desc
        allResults.sort((a, b) => new Date(b.date) - new Date(a.date));
        setResults(allResults);
        if (allResults.length > 0) {
          setSelectedResult(allResults[0]);
        }
      } catch (error) {
        console.error("Error fetching results", error);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchAllResults();
  }, []);

  return (
    <div className="page-container" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <header className="page-header">
        <h1>Résultats & Visualisations</h1>
        <p>Retrouvez et explorez les résultats de vos conversations précédentes</p>
      </header>

      <div style={{ display: 'flex', flex: 1, gap: '20px', overflow: 'hidden' }}>
        {/* Sidebar list */}
        <div style={{ width: '300px', backgroundColor: 'var(--card-bg)', borderRadius: '12px', border: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <h3 style={{ padding: '16px', margin: 0, borderBottom: '1px solid var(--border)', fontSize: '16px' }}>Historique</h3>
          <div style={{ overflowY: 'auto', flex: 1 }}>
            {isLoading ? (
              <div style={{ padding: '16px', color: 'var(--text-muted)' }}>Chargement...</div>
            ) : results.length === 0 ? (
              <div style={{ padding: '16px', color: 'var(--text-muted)' }}>Aucun résultat trouvé.</div>
            ) : (
              results.map(res => (
                <div 
                  key={res.id} 
                  onClick={() => setSelectedResult(res)}
                  style={{
                    padding: '12px 16px',
                    borderBottom: '1px solid var(--border)',
                    cursor: 'pointer',
                    backgroundColor: selectedResult?.id === res.id ? 'rgba(59, 130, 246, 0.1)' : 'transparent',
                    borderLeft: selectedResult?.id === res.id ? '3px solid var(--primary-color)' : '3px solid transparent'
                  }}
                >
                  <div style={{ fontWeight: '500', color: 'var(--text)', marginBottom: '4px' }}>{res.title}</div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{res.conversationTitle}</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                    {new Date(res.date).toLocaleString()}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Detail view */}
        <div style={{ flex: 1, backgroundColor: 'var(--card-bg)', borderRadius: '12px', border: '1px solid var(--border)', overflowY: 'auto', padding: '24px' }}>
          {selectedResult ? (
            <div>
              <h2 style={{ margin: '0 0 16px 0', color: 'var(--text)' }}>{selectedResult.title}</h2>
              <div style={{ color: 'var(--text-muted)', marginBottom: '24px', fontSize: '14px' }}>
                Extrait de la conversation : <strong>{selectedResult.conversationTitle}</strong>
              </div>
              
              <div style={{ marginBottom: '24px' }}>
                <ChartRenderer 
                  data={selectedResult.data} 
                  chartSpec={selectedResult.chartSpec}
                />
              </div>

              <div style={{ marginTop: '32px' }}>
                <h4 style={{ margin: '0 0 8px 0', color: 'var(--text-muted)' }}>Requête SQL exécutée</h4>
                <pre style={{ backgroundColor: 'var(--background)', padding: '12px', borderRadius: '8px', border: '1px solid var(--border)', fontSize: '13px', overflowX: 'auto', color: 'var(--text)' }}>
                  {selectedResult.sql}
                </pre>
              </div>
            </div>
          ) : (
            <div className="center-content empty-state" style={{ height: '100%', border: 'none' }}>
              <LineChart size={48} color="#475569" />
              <h2>Aucun résultat sélectionné</h2>
              <p>Sélectionnez un résultat dans la liste pour l'afficher.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
