import React, { useState, useRef, useEffect } from 'react';
import { Send, Database, PanelRightClose, PanelRightOpen } from 'lucide-react';
import MessageBubble from './components/MessageBubble';
import ChartRenderer from './components/ChartRenderer';
import DebugPanel from './components/DebugPanel';
import { chatWithData } from './services/api';
import './App.css';

function App() {
  const [messages, setMessages] = useState([
    { role: 'ai', content: "Bonjour ! Je suis AskYourData. Posez-moi une question sur vos données (ex: 'Combien y a-t-il d'utilisateurs ?')." }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [debugData, setDebugData] = useState(null);
  const [showDebug, setShowDebug] = useState(true);

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const userMessage = inputValue.trim();
    setInputValue('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      const response = await chatWithData(userMessage);
      
      // The response is a state dictionary from LangGraph
      // Let's extract what we need to show
      const aiMessage = {
        role: 'ai',
        content: response.response || "Voici les résultats de votre requête.",
        data: response.data_result,
        intent: response.semantic_plan?.intent,
        dimensions: response.sql_draft?.dimensions,
        metric: response.sql_draft?.metric
      };

      if (response.error) {
        aiMessage.content = "Une erreur est survenue lors du traitement.";
      }

      setMessages(prev => [...prev, aiMessage]);

      setDebugData({
        plan: response.semantic_plan,
        sql: response.sql_draft?.sql_query,
        error: response.error
      });

    } catch (error) {
      setMessages(prev => [...prev, { 
        role: 'ai', 
        content: "Désolé, je n'ai pas pu joindre le serveur. Assurez-vous que l'API Gateway est lancée." 
      }]);
    } finally {
      setIsLoading(false);
    }
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
            onClick={() => setShowDebug(!showDebug)} 
            style={{ color: 'var(--text-muted)' }}
            title="Toggle Debug Panel"
          >
            {showDebug ? <PanelRightClose size={20} /> : <PanelRightOpen size={20} />}
          </button>
        </header>

        {/* Chat History */}
        <div className="chat-history">
          {messages.map((msg, idx) => (
            <div key={idx}>
              <MessageBubble role={msg.role} content={msg.content} />
              {msg.data && (
                <div style={{ maxWidth: '85%', alignSelf: 'flex-start', marginTop: '8px' }}>
                  <ChartRenderer 
                    data={msg.data} 
                    intent={msg.intent}
                    dimensions={msg.dimensions}
                    metric={msg.metric}
                  />
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
          <form className="input-container" onSubmit={handleSend}>
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

export default App;
