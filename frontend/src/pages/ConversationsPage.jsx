import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  MessageSquarePlus,
  MessageSquare,
  Save,
  CheckCircle,
  Sparkles,
  AlertTriangle,
  Code2,
  Copy,
  Check,
  TrendingUp,
  HelpCircle,
} from 'lucide-react';
import { useLocation } from 'react-router-dom';
import MessageBubble from '../components/MessageBubble';
import ChartRenderer from '../components/ChartRenderer';
import SaveToDashboardDialog from '../components/SaveToDashboardDialog';
import {
  getConversations,
  createConversation,
  getConversation,
  getRun,
  sendMessage,
  setActiveSourceId,
  streamRunEvents,
  waitForRun,
  getDataSources,
  getActiveSourceId,
  getTables,
} from '../services/api';

function BusinessProvenancePanel({ provenance }) {
  if (!provenance || Object.keys(provenance).length === 0) return null;
  return (
    <div
      className="business-provenance-panel"
      style={{
        backgroundColor: 'rgba(16, 185, 129, 0.08)',
        border: '1px solid rgba(16, 185, 129, 0.25)',
        borderRadius: '8px',
        padding: '10px 14px',
        margin: '8px 48px',
        fontSize: '0.85rem',
        color: '#34d399',
      }}
    >
      <strong style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <CheckCircle size={15} /> Provenance métier (Métrique certifiée)
      </strong>
      <div style={{ marginTop: '6px', display: 'flex', flexDirection: 'column', gap: '4px', color: '#cbd5e1' }}>
        {provenance.metric_name && <div><strong>Métrique:</strong> {provenance.metric_name}</div>}
        {provenance.format && <div><strong>Format attendu:</strong> {provenance.format}</div>}
        {provenance.tables && provenance.tables.length > 0 && <div><strong>Tables:</strong> {provenance.tables.join(', ')}</div>}
      </div>
    </div>
  );
}

function SqlAccordion({ sqlQuery }) {
  const [copied, setCopied] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  if (!sqlQuery) return null;

  const handleCopy = (e) => {
    e.stopPropagation();
    navigator.clipboard.writeText(sqlQuery);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      style={{
        margin: '10px 48px',
        backgroundColor: '#0f172a',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '8px',
        overflow: 'hidden',
      }}
    >
      <div
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 14px',
          cursor: 'pointer',
          backgroundColor: 'rgba(255, 255, 255, 0.02)',
          fontSize: '0.85rem',
          color: '#94a3b8',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Code2 size={16} color="#6366f1" />
          <span style={{ fontWeight: 500 }}>Requête SQL générée</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={handleCopy}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              background: 'rgba(255, 255, 255, 0.06)',
              border: 'none',
              borderRadius: '4px',
              padding: '3px 8px',
              color: copied ? '#10b981' : '#cbd5e1',
              fontSize: '0.75rem',
              cursor: 'pointer',
            }}
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? 'Copié' : 'Copier'}
          </button>
          <span>{isOpen ? '▲' : '▼'}</span>
        </div>
      </div>

      {isOpen && (
        <pre
          style={{
            margin: 0,
            padding: '12px 14px',
            backgroundColor: '#090d16',
            color: '#38bdf8',
            fontSize: '0.82rem',
            lineHeight: 1.45,
            overflowX: 'auto',
            fontFamily: 'JetBrains Mono, Menlo, monospace',
          }}
        >
          <code>{sqlQuery}</code>
        </pre>
      )}
    </div>
  );
}

export default function ConversationsPage() {
  const [conversations, setConversations] = useState([]);
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [sources, setSources] = useState([]);
  const [runStage, setRunStage] = useState(null);
  const [savingMessage, setSavingMessage] = useState(null);
  const [suggestedQuestions, setSuggestedQuestions] = useState([]);

  const location = useLocation();
  const initialMessage = location.state?.initialMessage;

  const messagesEndRef = useRef(null);

  const hasDataResult = (message) =>
    Array.isArray(message.payload?.results) && message.payload.results.length > 0;

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const loadConversationMessages = async (id) => {
    try {
      const data = await getConversation(id);
      const formattedMessages = data.messages.map((msg) => ({
        id: msg.id,
        role: msg.role === 'ai' ? 'assistant' : msg.role,
        content: msg.content,
        payload: msg.payload,
      }));

      if (formattedMessages.length === 0) {
        formattedMessages.push({
          role: 'assistant',
          content: 'Bonjour ! Je suis AskYourData. Posez-moi une question sur vos données d\'entreprise.',
        });
      }
      setMessages(formattedMessages);
    } catch (error) {
      console.error('Error loading conversation', error);
    }
  };

  useEffect(() => {
    const initPage = async () => {
      setIsLoadingHistory(true);
      try {
        const loadedSources = await getDataSources();
        setSources(loadedSources);
        const convs = await getConversations();
        setConversations(convs);
        if (convs.length > 0) {
          setConversationId(convs[0].id);
          if (convs[0].source_id) {
            setActiveSourceId(convs[0].source_id);
          }
          await loadConversationMessages(convs[0].id);
        } else {
          setMessages([
            {
              role: 'assistant',
              content: "Bonjour ! Je suis AskYourData. Posez-moi une question sur vos données (ex: 'Quel est le chiffre d'affaires par pays ?').",
            },
          ]);
        }

        // Fetch tables for contextual examples
        try {
          const tablesResponse = await getTables();
          const tableNames = (tablesResponse.tables || []).map((t) => t.table_name);
          if (tableNames.length > 0) {
            const examples = [];
            if (tableNames.length >= 1) examples.push(`Combien y a-t-il de lignes dans ${tableNames[0]} ?`);
            if (tableNames.length >= 2) examples.push(`Montre-moi un aperçu de ${tableNames[1]}`);
            if (tableNames.length >= 3) examples.push(`Quelle est la répartition dans ${tableNames[2]} ?`);
            setSuggestedQuestions(examples);
          }
        } catch (e) {
          console.warn('Could not fetch tables for suggestions', e);
        }
      } catch (error) {
        console.error('Failed to load conversations', error);
      } finally {
        setIsLoadingHistory(false);
      }
    };
    initPage();
  }, []);

  const handleNewConversationWithInitialMessage = async (msgText) => {
    try {
      const activeSource = getActiveSourceId();
      const conv = await createConversation('Nouvelle analyse', activeSource);
      setConversations((current) => [
        { id: conv.id, title: conv.title || 'Nouvelle analyse', source_id: activeSource },
        ...current,
      ]);
      setConversationId(conv.id);
      setMessages([]);
      handleSend(null, msgText);
    } catch (error) {
      console.error('Error starting initial conversation', error);
    }
  };

  useEffect(() => {
    if (initialMessage && !isLoadingHistory) {
      handleNewConversationWithInitialMessage(initialMessage);
      window.history.replaceState({}, document.title);
    }
  }, [initialMessage, isLoadingHistory]);

  const handleSelectConversation = async (id) => {
    const selectedConversation = conversations.find((c) => c.id === id);
    if (selectedConversation?.source_id) setActiveSourceId(selectedConversation.source_id);
    setConversationId(id);
    await loadConversationMessages(id);
  };

  const handleNewConversation = async () => {
    try {
      const activeSource = getActiveSourceId();
      const conv = await createConversation('Nouvelle conversation', activeSource);
      setConversations((current) => [
        { id: conv.id, title: conv.title || 'Nouvelle conversation', source_id: activeSource },
        ...current,
      ]);
      setConversationId(conv.id);
      setMessages([
        { role: 'assistant', content: 'Nouvelle conversation démarrée ! Que voulez-vous analyser aujourd\'hui ?' },
      ]);
    } catch (error) {
      console.error('Error creating conversation', error);
    }
  };

  const handleSend = async (e, textOverride = null) => {
    if (e) e.preventDefault();
    const userMessage = textOverride || inputValue.trim();
    if (!userMessage || isLoading) return;

    setInputValue('');
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      let currentConvId = conversationId;
      const currentConversation = conversations.find((c) => c.id === currentConvId);
      let sourceId = currentConversation?.source_id || getActiveSourceId();

      if (currentConversation?.source_id) {
        setActiveSourceId(currentConversation.source_id);
      }

      if (!currentConvId) {
        const newConv = await createConversation('Nouvelle conversation', sourceId);
        currentConvId = newConv.id;
        setConversationId(currentConvId);
        setConversations((current) => [
          { id: newConv.id, title: newConv.title || 'Nouvelle conversation', source_id: sourceId },
          ...current,
        ]);
      }

      const queuedRun = await sendMessage(currentConvId, userMessage, sourceId);
      setRunStage('Analyse de votre demande…');
      try {
        await streamRunEvents(queuedRun.run_id, (event) => {
          const stages = {
            run_started: 'Analyse sémantique de la question…',
            retrieval_completed: 'Exploration du catalogue de données…',
            planning: 'Planification de la requête analytique…',
            sql_generating: 'Génération SQL multi-dialecte…',
            sql_validating: 'Contrôles de sécurité AST SQLGlot…',
            query_executing: 'Exécution de la requête en lecture seule…',
            visualization_generating: 'Création du graphique ECharts…',
            clarification_requested: 'Précision requise…',
          };
          setRunStage(stages[event.event_type] || 'Traitement en cours…');
        });
      } catch (streamError) {
        console.warn('SSE unavailable, falling back to status polling', streamError);
        await waitForRun(queuedRun.run_id);
      }
      const response = await getRun(queuedRun.run_id);

      if (['failed', 'error'].includes(response.status)) {
        throw new Error(response.error_message || "L'analyse n'a pas pu être terminée.");
      }

      const payload = {
        semantic_plan: response.semantic_plan,
        results: response.results,
        chart_spec: response.chart_spec,
        sql_query: response.sql_draft?.sql_query || response.sql_query,
        executive_summary: response.executive_summary,
        key_insights: response.key_insights || [],
        warnings: response.warnings || [],
        suggested_followups: response.suggested_followups || [],
        error_message: response.error_message,
        clarification_options: response.clarification_options,
      };

      const aiMessage = {
        id: response.final_message_id,
        role: 'assistant',
        content: response.response || 'Voici les résultats de votre requête.',
        payload: payload,
      };

      setMessages((prev) => [...prev, aiMessage]);
      const convs = await getConversations();
      setConversations(convs);
    } catch (error) {
      console.error('Conversation run failed', error);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Désolé, une erreur s'est produite : ${error.message || 'Erreur inattendue'}`,
        },
      ]);
    } finally {
      setIsLoading(false);
      setRunStage(null);
    }
  };

  const handleClarificationClick = (optionText) => {
    handleSend(null, optionText);
  };

  const activeSourceId = getActiveSourceId();
  const activeSourceInfo = sources.find((s) => s.id === activeSourceId);
  const hasNoSources = sources.length === 0;
  const isSourceArchived = activeSourceInfo && activeSourceInfo.status === 'archived';

  return (
    <div className="conversations-page">
      {/* Sidebar: Conversation List */}
      <div className="conv-sidebar">
        <div className="conv-sidebar-header">
          <h3>Conversations</h3>
          <button className="btn-icon" onClick={handleNewConversation} title="Nouvelle conversation">
            <MessageSquarePlus size={18} />
          </button>
        </div>
        <div className="conv-list">
          {conversations.length === 0 ? (
            <div className="conv-list-empty">
              <MessageSquare size={24} color="#64748b" />
              <p>Aucune conversation</p>
            </div>
          ) : (
            conversations.map((conv) => (
              <button
                key={conv.id}
                className={`conv-list-item ${conv.id === conversationId ? 'active' : ''}`}
                onClick={() => handleSelectConversation(conv.id)}
              >
                <div className="conv-item-title">{conv.title || 'Nouvelle conversation'}</div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="chat-section">
        <div className="chat-header">
          <h2>Conversation {activeSourceInfo ? `— Source : ${activeSourceInfo.name}` : ''}</h2>
          <div style={{ flex: 1 }} />
        </div>

        <div className="chat-history">
          {isLoadingHistory ? (
            <div className="typing-indicator" style={{ alignSelf: 'center', margin: '2rem 0' }}>
              <span>Chargement de l'historique...</span>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <MessageBubble role={msg.role === 'assistant' ? 'ai' : msg.role} content={msg.content} />

                {/* Executive Summary Banner */}
                {msg.payload?.executive_summary && (
                  <div
                    style={{
                      margin: '6px 48px',
                      padding: '12px 16px',
                      backgroundColor: 'rgba(99, 102, 241, 0.08)',
                      border: '1px solid rgba(99, 102, 241, 0.25)',
                      borderRadius: '8px',
                      fontSize: '0.9rem',
                      color: '#e2e8f0',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '10px',
                    }}
                  >
                    <Sparkles size={18} color="#818cf8" style={{ marginTop: '2px', flexShrink: 0 }} />
                    <div>
                      <strong style={{ color: '#a5b4fc', display: 'block', marginBottom: '2px' }}>
                        Synthèse décisionnelle
                      </strong>
                      {msg.payload.executive_summary}
                    </div>
                  </div>
                )}

                {/* Key Insights List */}
                {msg.payload?.key_insights && msg.payload.key_insights.length > 0 && (
                  <div
                    style={{
                      margin: '6px 48px',
                      padding: '12px 16px',
                      backgroundColor: 'rgba(30, 41, 59, 0.6)',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: '8px',
                      fontSize: '0.85rem',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        fontWeight: 600,
                        color: '#38bdf8',
                        marginBottom: '8px',
                      }}
                    >
                      <TrendingUp size={15} />
                      <span>Faits marquants & Insights</span>
                    </div>
                    <ul style={{ margin: 0, paddingLeft: '18px', color: '#cbd5e1', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      {msg.payload.key_insights.map((insight, insIdx) => (
                        <li key={insIdx}>{insight}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Warnings / Caveats */}
                {msg.payload?.warnings && msg.payload.warnings.length > 0 && (
                  <div
                    style={{
                      margin: '6px 48px',
                      padding: '10px 14px',
                      backgroundColor: 'rgba(245, 158, 11, 0.08)',
                      border: '1px solid rgba(245, 158, 11, 0.25)',
                      borderRadius: '8px',
                      fontSize: '0.82rem',
                      color: '#fbbf24',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                    }}
                  >
                    <AlertTriangle size={16} style={{ flexShrink: 0 }} />
                    <div>{msg.payload.warnings.join(' • ')}</div>
                  </div>
                )}

                {/* Business Provenance */}
                {msg.payload?.semantic_plan?.business_provenance &&
                  Object.keys(msg.payload.semantic_plan.business_provenance).length > 0 && (
                    <BusinessProvenancePanel provenance={msg.payload.semantic_plan.business_provenance} />
                  )}

                {/* SQL Accordion */}
                {msg.payload?.sql_query && <SqlAccordion sqlQuery={msg.payload.sql_query} />}

                {/* Visual Chart / Table Result */}
                {hasDataResult(msg) && (
                  <div className="chat-result-container" style={{ margin: '6px 48px' }}>
                    {msg.id && (
                      <div className="chat-result-actions" style={{ marginBottom: '8px' }}>
                        <button
                          className="btn-secondary"
                          onClick={() =>
                            setSavingMessage({
                              id: msg.id,
                              title: msg.payload.chart_spec?.title || 'Résultat de conversation',
                            })
                          }
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '6px 12px',
                            fontSize: '0.82rem',
                          }}
                        >
                          <Save size={14} /> Sauvegarder au tableau de bord
                        </button>
                      </div>
                    )}
                    <ChartRenderer
                      data={msg.payload.results}
                      chartSpec={msg.payload.chart_spec}
                    />
                  </div>
                )}

                {/* Suggested Follow-up Chips */}
                {msg.payload?.suggested_followups && msg.payload.suggested_followups.length > 0 && (
                  <div
                    style={{
                      margin: '8px 48px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      flexWrap: 'wrap',
                    }}
                  >
                    <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>
                      Questions suggérées :
                    </span>
                    {msg.payload.suggested_followups.map((followup, fIdx) => (
                      <button
                        key={fIdx}
                        onClick={() => handleSend(null, followup)}
                        style={{
                          background: 'rgba(99, 102, 241, 0.1)',
                          border: '1px solid rgba(99, 102, 241, 0.25)',
                          borderRadius: '16px',
                          padding: '4px 12px',
                          color: '#a5b4fc',
                          fontSize: '0.8rem',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          transition: 'all 0.15s ease',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = 'rgba(99, 102, 241, 0.2)';
                          e.currentTarget.style.color = '#ffffff';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = 'rgba(99, 102, 241, 0.1)';
                          e.currentTarget.style.color = '#a5b4fc';
                        }}
                      >
                        <HelpCircle size={12} />
                        <span>{followup}</span>
                      </button>
                    ))}
                  </div>
                )}

                {/* Clarification Options */}
                {msg.payload?.clarification_options && (
                  <div className="clarification-options" style={{ margin: '8px 48px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {msg.payload.clarification_options.map((opt, oIdx) => (
                      <button
                        key={oIdx}
                        className="clarification-btn"
                        onClick={() => handleClarificationClick(opt.text)}
                        style={{
                          padding: '6px 14px',
                          borderRadius: '6px',
                          backgroundColor: '#1e293b',
                          border: '1px solid #334155',
                          color: '#f8fafc',
                          cursor: 'pointer',
                        }}
                      >
                        {opt.text}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}

          {isLoading && (
            <div className="typing-indicator" style={{ margin: '16px 48px' }}>
              <div className="typing-dot"></div>
              <span style={{ color: '#818cf8', fontWeight: 500 }}>{runStage || 'Analyse en cours…'}</span>
              <div className="typing-dot"></div>
              <div className="typing-dot"></div>
            </div>
          )}

          {messages.length <= 1 && suggestedQuestions.length > 0 && !isLoading && (
            <div
              className="suggested-questions"
              style={{
                display: 'flex',
                gap: '8px',
                flexWrap: 'wrap',
                padding: '16px 48px',
              }}
            >
              {suggestedQuestions.map((q, idx) => (
                <button
                  key={idx}
                  className="btn-secondary"
                  style={{
                    fontSize: '0.85rem',
                    padding: '6px 14px',
                    borderRadius: '16px',
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    color: '#cbd5e1',
                    cursor: 'pointer',
                  }}
                  onClick={() => handleSend(null, q)}
                >
                  {q}
                </button>
              ))}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <div className="input-area">
          {hasNoSources ? (
            <div className="error-message" style={{ margin: '1rem', textAlign: 'center' }}>
              Aucune source de données n'est configurée. Allez dans "Sources de données" pour en ajouter une.
            </div>
          ) : isSourceArchived ? (
            <div className="error-message" style={{ margin: '1rem', textAlign: 'center' }}>
              Cette conversation est liée à une source archivée. Vous ne pouvez plus y envoyer de requêtes.
            </div>
          ) : (
            <form className="input-container" onSubmit={handleSend}>
              <input
                type="text"
                className="chat-input"
                placeholder="Posez une question sur vos données (ex: Quel est le top 5 des clients par volume ?)..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                disabled={isLoading}
              />
              <button type="submit" className="btn-primary" disabled={isLoading || !inputValue.trim()}>
                <Send size={18} />
              </button>
            </form>
          )}
        </div>
      </div>

      {savingMessage && (
        <SaveToDashboardDialog
          messageId={savingMessage.id}
          initialTitle={savingMessage.title}
          onClose={() => setSavingMessage(null)}
        />
      )}
    </div>
  );
}
