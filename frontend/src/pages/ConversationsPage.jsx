import React, { useState, useRef, useEffect } from 'react';
import { Send, PanelRightClose, PanelRightOpen, MessageSquarePlus, MessageSquare, Save } from 'lucide-react';
import MessageBubble from '../components/MessageBubble';
import ChartRenderer from '../components/ChartRenderer';
import DebugPanel from '../components/DebugPanel';
import SaveToDashboardDialog from '../components/SaveToDashboardDialog';
import { getConversations, createConversation, getConversation, getRun, sendMessage, streamRunEvents, waitForRun } from '../services/api';

export default function ConversationsPage() {
  const [conversations, setConversations] = useState([]);
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [debugData, setDebugData] = useState(null);
  // The semantic plan and SQL are useful for investigation, but should not
  // overwhelm a normal analyst's conversation by default.
  const [showDebug, setShowDebug] = useState(false);
  const [runStage, setRunStage] = useState(null);
  const [savingMessage, setSavingMessage] = useState(null);
  
  const messagesEndRef = useRef(null);
  const hasDataResult = (message) => (
    ['DATA_QUERY', 'CHART_GENERATION'].includes(message.payload?.semantic_plan?.intent)
    && Array.isArray(message.payload?.results)
    && message.payload.results.length > 0
  );

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const loadConversationMessages = async (id) => {
    try {
      const data = await getConversation(id);
      const formattedMessages = data.messages.map(msg => ({
        id: msg.id,
        role: msg.role === 'ai' ? 'assistant' : msg.role,
        content: msg.content,
        payload: msg.payload
      }));
      
      if (formattedMessages.length === 0) {
        formattedMessages.push({ role: 'assistant', content: "Bonjour ! Je suis AskYourData. Posez-moi une question sur vos données." });
      }
      setMessages(formattedMessages);
      
      // Update debug panel
      const lastAssistantMsg = formattedMessages.filter(m => m.role === 'assistant').pop();
      if (lastAssistantMsg && lastAssistantMsg.payload) {
        setDebugData({
          plan: lastAssistantMsg.payload.semantic_plan,
          sql: lastAssistantMsg.payload.sql_query,
          error: lastAssistantMsg.payload.error_message
        });
      } else {
        setDebugData(null);
      }
    } catch (error) {
      console.error("Error loading conversation", error);
    }
  };

  useEffect(() => {
    const initPage = async () => {
      try {
        const convs = await getConversations();
        setConversations(convs);
        if (convs.length > 0) {
          setConversationId(convs[0].id);
          await loadConversationMessages(convs[0].id);
        } else {
          setMessages([{ role: 'assistant', content: "Bonjour ! Je suis AskYourData. Posez-moi une question sur vos données (ex: 'Combien y a-t-il d'utilisateurs ?')." }]);
        }
      } catch (error) {
        console.error("Failed to load conversations", error);
      }
    };
    initPage();
  }, []);

  const handleSelectConversation = async (id) => {
    if (id === conversationId) return;
    setConversationId(id);
    await loadConversationMessages(id);
  };

  const handleNewConversation = async () => {
    try {
      const conv = await createConversation();
      setConversations((current) => [{ id: conv.id, title: conv.title || "Nouvelle conversation" }, ...current]);
      setConversationId(conv.id);
      setMessages([
        { role: 'assistant', content: "Nouvelle conversation démarrée ! Que voulez-vous savoir ?" }
      ]);
      setDebugData(null);
    } catch (error) {
      console.error("Error creating conversation", error);
    }
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
        setConversations((current) => [{ id: newConv.id, title: newConv.title || "Nouvelle conversation" }, ...current]);
      }

      const queuedRun = await sendMessage(currentConvId, userMessage);
      setRunStage('En attente du traitement…');
      try {
        await streamRunEvents(queuedRun.run_id, (event) => {
          const stages = {
            run_started: 'Analyse de votre demande…',
            retrieval_completed: 'Recherche du catalogue de données…',
            planning: 'Préparation de la requête…',
            sql_generating: 'Génération SQL…',
            sql_validating: 'Validation de sécurité…',
            query_executing: 'Exécution de la requête…',
            visualization_generating: 'Préparation de la visualisation…',
            clarification_requested: 'Une précision est nécessaire…',
          };
          setRunStage(stages[event.event_type] || 'Analyse en cours…');
        });
      } catch (streamError) {
        // The persisted run remains authoritative if an intermediary closes SSE.
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
        error_message: response.error_message,
        clarification_options: response.clarification_options
      };
      
      const aiMessage = {
        id: response.final_message_id,
        role: 'assistant',
        content: response.response || "Voici les résultats de votre requête.",
        payload: payload
      };

      setMessages(prev => [...prev, aiMessage]);

      setDebugData({
        plan: payload.semantic_plan,
        sql: payload.sql_query,
        error: payload.error_message || null
      });

      const convs = await getConversations();
      setConversations(convs);

    } catch (error) {
      console.error('Conversation run failed', error);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: "Désolé, une erreur s'est produite." 
      }]);
    } finally {
      setIsLoading(false);
      setRunStage(null);
    }
  };

  const handleClarificationClick = (optionText) => {
    handleSend(null, optionText);
  };

  return (
    <div className="conversations-layout">
      {/* Sidebar: Conversation List */}
      <div className="conv-sidebar">
        <div className="conv-sidebar-header">
          <h3>Historique</h3>
          <button className="icon-btn primary-icon-btn" onClick={handleNewConversation} title="Nouvelle conversation">
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
            conversations.map(conv => (
              <button 
                key={conv.id}
                className={`conv-list-item ${conv.id === conversationId ? 'active' : ''}`}
                onClick={() => handleSelectConversation(conv.id)}
              >
                <div className="conv-item-title">{conv.title || "Nouvelle conversation"}</div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="chat-section">
        <div className="chat-header">
          <h2>Conversation en cours</h2>
          <div style={{ flex: 1 }} />
          <button 
            className="icon-btn"
            onClick={() => setShowDebug(!showDebug)} 
            title={showDebug ? "Masquer le panneau debug" : "Afficher le panneau debug"}
          >
            {showDebug ? <PanelRightClose size={20} /> : <PanelRightOpen size={20} />}
          </button>
        </div>

        <div className="chat-history">
          {messages.map((msg, idx) => (
            <div key={idx}>
              <MessageBubble role={msg.role === 'assistant' ? 'ai' : msg.role} content={msg.content} />
              
              {hasDataResult(msg) && (
                <div className="chat-result-container">
                  {msg.id && <div className="chat-result-actions"><button className="btn-secondary" onClick={() => setSavingMessage({ id: msg.id, title: msg.payload.chart_spec?.title || 'Résultat de conversation' })}><Save size={16} /> Sauvegarder</button></div>}
                  <ChartRenderer 
                    data={msg.payload.results} 
                    intent={msg.payload.semantic_plan?.intent || 'DATA_QUERY'}
                    chartSpec={msg.payload.chart_spec}
                  />
                </div>
              )}
              
              {msg.payload?.clarification_options && (
                <div className="clarification-options">
                   {msg.payload.clarification_options.map((opt, oIdx) => (
                      <button 
                        key={oIdx}
                        className="clarification-btn"
                        onClick={() => handleClarificationClick(opt.text)}
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
              <span>{runStage || 'Analyse en cours…'}</span>
              <div className="typing-dot"></div>
              <div className="typing-dot"></div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-area">
          <form className="input-container" onSubmit={handleSend}>
            <input 
              type="text" 
              className="chat-input"
              placeholder="Posez votre question sur vos données..." 
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

      {/* Right Sidebar: Debug/Context */}
      {showDebug && debugData && (
        <DebugPanel 
          plan={debugData.plan} 
          sql={debugData.sql} 
          error={debugData.error} 
        />
      )}
      {savingMessage && <SaveToDashboardDialog messageId={savingMessage.id} title={savingMessage.title} onClose={() => setSavingMessage(null)} />}
    </div>
  );
}
