import React, { useState, useRef, useEffect } from 'react';
import { Send, Database, PanelRightClose, PanelRightOpen, LogOut, MessageSquarePlus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import MessageBubble from './MessageBubble';
import ChartRenderer from './ChartRenderer';
import DebugPanel from './DebugPanel';
import { getConversations, createConversation, getConversation, sendMessage, getRun } from '../services/api';
import '../App.css';

export default function MainChat() {
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [debugData, setDebugData] = useState(null);
  const [showDebug, setShowDebug] = useState(true);
  const navigate = useNavigate();

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    // Load last conversation on mount
    const initConversation = async () => {
      try {
        const convs = await getConversations();
        if (convs.length > 0) {
          const latestConvId = convs[0].id;
          setConversationId(latestConvId);
          await loadConversationMessages(latestConvId);
        } else {
          // No conversation exists, add the welcome message
          setMessages([
            { role: 'assistant', content: "Bonjour ! Je suis AskYourData. Posez-moi une question sur vos données (ex: 'Combien y a-t-il d'utilisateurs ?')." }
          ]);
        }
      } catch (error) {
        if (error.response?.status === 401) {
          handleLogout();
        }
      }
    };
    initConversation();
  }, []);

  const loadConversationMessages = async (id) => {
    try {
      const data = await getConversation(id);
      const formattedMessages = data.messages.map(msg => ({
        role: msg.role === 'ai' ? 'assistant' : msg.role, // normalize to 'user' / 'assistant'
        content: msg.content,
        payload: msg.payload
      }));
      if (formattedMessages.length === 0) {
        formattedMessages.push({ role: 'assistant', content: "Bonjour ! Je suis AskYourData. Posez-moi une question sur vos données." });
      }
      setMessages(formattedMessages);
      
      // Update debug panel with last assistant message payload if it exists
      const lastAssistantMsg = formattedMessages.filter(m => m.role === 'assistant').pop();
      if (lastAssistantMsg && lastAssistantMsg.payload) {
        setDebugData({
          plan: lastAssistantMsg.payload.semantic_plan,
          sql: lastAssistantMsg.payload.sql_query,
          error: lastAssistantMsg.payload.error_message
        });
      }
    } catch (error) {
      console.error("Error loading conversation", error);
    }
  };

  const handleNewConversation = async () => {
    try {
      const conv = await createConversation();
      setConversationId(conv.id);
      setMessages([
        { role: 'assistant', content: "Nouvelle conversation démarrée ! Que voulez-vous savoir ?" }
      ]);
      setDebugData(null);
    } catch (error) {
      console.error("Error creating conversation", error);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/login');
  };

  const handleSend = async (e, textOverride = null) => {
    if (e) e.preventDefault();
    const userMessage = textOverride || inputValue.trim();
    if (!userMessage || isLoading) return;

    setInputValue('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      let currentConvId = conversationId;
      if (!currentConvId) {
        const newConv = await createConversation();
        currentConvId = newConv.id;
        setConversationId(currentConvId);
      }

      const response = await sendMessage(currentConvId, userMessage);
      
      const token = localStorage.getItem('token');
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const eventSourceUrl = `${API_URL}${response.events_url}?token=${token}`;
      
      const eventSource = new EventSource(eventSourceUrl);
      
      const finishRun = async () => {
          setIsLoading(false);
          eventSource.close();
          try {
              const finalRun = await getRun(response.run_id);
              const payload = {
                semantic_plan: finalRun.semantic_plan,
                results: finalRun.results,
                chart_spec: finalRun.chart_spec,
                sql_query: finalRun.sql_draft?.sql_query || finalRun.sql_query,
                error_message: finalRun.error_message,
                clarification_options: finalRun.clarification_options
              };
              
              const aiMessage = {
                id: finalRun.final_message_id,
                role: 'assistant',
                content: finalRun.response || "Voici les résultats de votre requête.",
                payload: payload
              };

              setMessages(prev => [...prev.filter(m => m.id !== 'temp-loading'), aiMessage]);

              setDebugData({
                plan: payload.semantic_plan,
                sql: payload.sql_query,
                error: payload.error_message !== null
              });
          } catch (fetchErr) {
              setMessages(prev => [...prev.filter(m => m.id !== 'temp-loading'), { role: 'assistant', content: "Désolé, une erreur s'est produite lors de la récupération des résultats." }]);
          }
      };
      
      eventSource.onmessage = async (event) => {
        try {
            const data = JSON.parse(event.data);
            
            if (data.event_type === 'run_completed' || data.event_type === 'result_ready' || data.event_type === 'run_failed') {
                await finishRun();
            } else {
                let statusText = "En cours d'analyse...";
                if (data.status === 'pending') statusText = "En attente du traitement...";
                if (data.event_type === 'run_started') statusText = "Démarrage du traitement...";
                if (data.event_type === 'retrieval_completed') statusText = "Recherche du schéma de données...";
                if (data.event_type === 'planning') statusText = "Planification sémantique...";
                if (data.event_type === 'sql_generating') statusText = "Préparation de la requête...";
                if (data.event_type === 'query_executing') statusText = "Exécution de la requête...";
                if (data.event_type === 'visualization_generating') statusText = "Préparation de la visualisation...";
                if (data.event_type === 'clarification_requested') statusText = "Une clarification est requise...";
                
                setMessages(prev => {
                   const newMsgs = [...prev];
                   const last = newMsgs[newMsgs.length - 1];
                   if (last && last.id === 'temp-loading') {
                       last.content = statusText;
                   } else {
                       newMsgs.push({ id: 'temp-loading', role: 'assistant', content: statusText, isTimeline: true });
                   }
                   return newMsgs;
                });
            }
        } catch (err) {
            console.error("SSE parse error", err);
        }
      };
      
      eventSource.onerror = async (err) => {
          console.error("SSE error, falling back to polling", err);
          eventSource.close();
          await finishRun();
      };

    } catch (error) {
      if (error.response?.status === 401) {
        handleLogout();
        return;
      }
      setMessages(prev => [...prev.filter(m => m.id !== 'temp-loading'), { 
        role: 'assistant', 
        content: "Désolé, une erreur s'est produite." 
      }]);
      setIsLoading(false);
    }
  };

  const handleClarificationClick = (optionText) => {
    handleSend(null, optionText);
  };

  return (
    <div className="app-container">
      <div className="chat-section">
        {/* Header */}
        <header className="app-header glass">
          <Database className="header-icon" />
          <span>Ask Your Data</span>
          <div style={{ flex: 1 }} />
          <button 
            onClick={handleNewConversation}
            style={{ color: 'var(--primary-color)', marginRight: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'none', border: 'none', cursor: 'pointer' }}
            title="Nouvelle conversation"
          >
            <MessageSquarePlus size={18} />
          </button>
          <button 
            onClick={handleLogout} 
            style={{ color: '#ef4444', marginRight: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'none', border: 'none', cursor: 'pointer' }}
            title="Se déconnecter"
          >
            <LogOut size={18} />
          </button>
          <button 
            onClick={() => setShowDebug(!showDebug)} 
            style={{ color: 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer' }}
            title="Toggle Debug Panel"
          >
            {showDebug ? <PanelRightClose size={20} /> : <PanelRightOpen size={20} />}
          </button>
        </header>

        {/* Chat History */}
        <div className="chat-history">
          {messages.map((msg, idx) => (
            <div key={idx}>
              {msg.isTimeline ? (
                <div style={{ padding: '0.5rem 1rem', color: '#64748b', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <div className="typing-dot" style={{ animationDelay: '0s', width: 4, height: 4 }}></div>
                    <div className="typing-dot" style={{ animationDelay: '0.2s', width: 4, height: 4 }}></div>
                    <div className="typing-dot" style={{ animationDelay: '0.4s', width: 4, height: 4 }}></div>
                    {msg.content}
                </div>
              ) : (
                <MessageBubble role={msg.role === 'assistant' ? 'ai' : msg.role} content={msg.content} />
              )}
              
                            {msg.payload?.semantic_plan && msg.payload.semantic_plan.intent !== 'UNRELATED' && msg.payload.semantic_plan.intent !== 'AMBIGUOUS' && (
                <div style={{ maxWidth: '85%', alignSelf: 'flex-start', marginTop: '8px', background: '#f8fafc', padding: '12px', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '0.9rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', color: '#0f172a', fontWeight: '500' }}>
                    <Database size={16} />
                    Détails de l'interprétation
                  </div>
                  <div style={{ color: '#475569' }}>
                    {msg.payload.semantic_plan.reasoning && <p style={{ margin: '0 0 8px 0', fontStyle: 'italic' }}>"{msg.payload.semantic_plan.reasoning}"</p>}
                    <ul style={{ margin: 0, paddingLeft: '20px' }}>
                      {msg.payload.semantic_plan.metric && <li><strong>Métrique :</strong> {msg.payload.semantic_plan.metric}</li>}
                      {msg.payload.semantic_plan.dimensions?.length > 0 && <li><strong>Dimensions :</strong> {msg.payload.semantic_plan.dimensions.join(', ')}</li>}
                      {msg.payload.semantic_plan.source_tables?.length > 0 && <li><strong>Sources :</strong> {msg.payload.semantic_plan.source_tables.join(', ')}</li>}
                    </ul>
                  </div>
                </div>
              )}
              {msg.payload?.results && (
                <div style={{ maxWidth: '85%', alignSelf: 'flex-start', marginTop: '8px' }}>
                  <ChartRenderer 
                    data={msg.payload.results} 
                    chartSpec={msg.payload.chart_spec}
                  />
                  {msg.id && (
                    <div style={{ display: 'flex', gap: '8px', marginTop: '8px', fontSize: '12px' }}>
                      <button 
                        onClick={() => {
                          const url = `/api/v1/results/${msg.id}/export?format=csv`;
                          fetch(url, { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } })
                            .then(res => {
                              if (!res.ok) throw new Error('Export denied');
                              return res.blob();
                            })
                            .then(blob => {
                              const link = document.createElement('a');
                              link.href = window.URL.createObjectURL(blob);
                              link.download = `export_${msg.id}.csv`;
                              link.click();
                            })
                            .catch(e => alert(e.message));
                        }}
                        style={{ padding: '4px 8px', background: '#e2e8f0', border: 'none', borderRadius: '4px', cursor: 'pointer', color: '#1e293b' }}
                      >
                        Exporter CSV
                      </button>
                      <button 
                        onClick={async () => {
                          const name = prompt("Enter dashboard ID to save to:");
                          if (name) {
                            try {
                                await fetch(`/api/v1/dashboards/${name}/items`, {
                                    method: 'POST',
                                    headers: { 
                                        'Content-Type': 'application/json',
                                        Authorization: `Bearer ${localStorage.getItem('token')}` 
                                    },
                                    body: JSON.stringify({
                                        source_message_id: msg.id,
                                        title: msg.payload.chart_spec?.title || "Result",
                                        order: 0
                                    })
                                });
                                alert("Saved to dashboard!");
                            } catch (e) {
                                alert("Error saving");
                            }
                          }
                        }}
                        style={{ padding: '4px 8px', background: '#e2e8f0', border: 'none', borderRadius: '4px', cursor: 'pointer', color: '#1e293b' }}
                      >
                        Sauvegarder
                      </button>
                    </div>
                  )}
                </div>
              )}
              
              {msg.payload?.clarification_options && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.5rem', marginLeft: '1rem' }}>
                   {msg.payload.clarification_options.map((opt, oIdx) => (
                      <button 
                        key={oIdx}
                        onClick={() => handleClarificationClick(opt.text)}
                        style={{
                          padding: '0.5rem 1rem',
                          background: 'var(--background)',
                          border: '1px solid var(--border)',
                          borderRadius: '0.5rem',
                          cursor: 'pointer',
                          textAlign: 'left',
                          color: 'var(--text)'
                        }}
                      >
                        {opt.text}
                      </button>
                   ))}
                </div>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="typing-indicator">
              <div className="typing-dot"></div>
              <div className="typing-dot"></div>
              <div className="typing-dot"></div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="input-area">
          <form className="input-container" onSubmit={(e) => handleSend(e)}>
            <input 
              type="text" 
              className="chat-input"
              placeholder="Posez votre question ici..." 
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              disabled={isLoading}
            />
            <button 
              type="submit" 
              className="send-button"
              disabled={!inputValue.trim() || isLoading}
            >
              <Send size={18} />
            </button>
          </form>
        </div>
      </div>

      {/* Debug Panel */}
      {showDebug && debugData && (
        <DebugPanel 
          plan={debugData.plan} 
          sql={debugData.sql} 
          error={debugData.error} 
        />
      )}
    </div>
  );
}
