import React from 'react';
import { User, Bot } from 'lucide-react';
import './MessageBubble.css';

const MessageBubble = ({ role, content, isChart, chartData }) => {
  const isUser = role === 'user';
  
  return (
    <div className={`message-wrapper ${isUser ? 'user' : 'ai'}`}>
      <div className="message-avatar">
        {isUser ? <User size={20} /> : <Bot size={20} />}
      </div>
      <div className={`message-content ${isUser ? 'user-bg' : 'ai-bg'}`}>
        <div className="message-text">
          {content}
        </div>
      </div>
    </div>
  );
};

export default MessageBubble;
