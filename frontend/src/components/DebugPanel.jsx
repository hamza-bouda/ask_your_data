import React from 'react';
import { Terminal } from 'lucide-react';

const DebugPanel = ({ plan, sql, error }) => {
  if (!plan && !sql && !error) return null;

  return (
    <div className="debug-panel-container">
      <div className="debug-header">
        <Terminal size={18} />
        <span>Debug & Trace</span>
      </div>
      
      <div className="debug-content">
        {plan && (
          <div className="debug-card">
            <div className="debug-card-header">Semantic Plan</div>
            <div className="debug-card-body">
              {JSON.stringify(plan, null, 2)}
            </div>
          </div>
        )}
        
        {sql && (
          <div className="debug-card">
            <div className="debug-card-header">Generated SQL</div>
            <div className="debug-card-body sql">
              {sql}
            </div>
          </div>
        )}

        {error && (
          <div className="debug-card">
            <div className="debug-card-header" style={{color: '#ef4444'}}>Error Log</div>
            <div className="debug-card-body" style={{color: '#fca5a5'}}>
              {error}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default DebugPanel;
