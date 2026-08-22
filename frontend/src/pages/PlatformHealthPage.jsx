import React, { useState, useEffect } from 'react';
import { getAdminStuckRuns, getAdminDlqRuns } from '../services/api';

const PlatformHealthPage = () => {
  const [stuckRuns, setStuckRuns] = useState([]);
  const [dlqRuns, setDlqRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchHealthData();
  }, []);

  const fetchHealthData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [stuck, dlq] = await Promise.all([
        getAdminStuckRuns(),
        getAdminDlqRuns()
      ]);
      setStuckRuns(stuck?.stuck_runs || []);
      setDlqRuns(dlq?.dlq || []);
    } catch (err) {
      console.error(err);
      setError('Erreur lors de la récupération des données de santé.');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-gray-500">Chargement des données...</div>;
  }

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold text-gray-800">Santé de la plateforme</h1>
        <button 
          onClick={fetchHealthData}
          className="px-4 py-2 bg-blue-50 text-blue-600 rounded-md hover:bg-blue-100 transition-colors"
        >
          Rafraîchir
        </button>
      </div>
      
      {error && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4 text-red-700">
          <p>{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow border border-gray-100 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50">
            <h2 className="text-lg font-medium text-gray-800">Runs bloqués</h2>
            <span className="bg-amber-100 text-amber-800 text-xs font-semibold px-2.5 py-0.5 rounded-full">
              {stuckRuns.length}
            </span>
          </div>
          <div className="p-6">
            {stuckRuns.length === 0 ? (
              <p className="text-gray-500 text-sm">Aucun run bloqué.</p>
            ) : (
              <ul className="divide-y divide-gray-100">
                {stuckRuns.map((run, i) => (
                  <li key={i} className="py-3">
                    <div className="flex justify-between">
                      <span className="text-sm font-medium font-mono text-gray-700">{run.id}</span>
                      <span className="text-xs text-gray-500">{new Date(run.created_at).toLocaleString()}</span>
                    </div>
                    <div className="text-sm text-gray-500 mt-1">Status: {run.status} | Tentatives: {run.attempts}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow border border-gray-100 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50">
            <h2 className="text-lg font-medium text-gray-800">File d'attente des lettres mortes (DLQ)</h2>
            <span className="bg-red-100 text-red-800 text-xs font-semibold px-2.5 py-0.5 rounded-full">
              {dlqRuns.length}
            </span>
          </div>
          <div className="p-6">
            {dlqRuns.length === 0 ? (
              <p className="text-gray-500 text-sm">La DLQ est vide.</p>
            ) : (
              <ul className="divide-y divide-gray-100">
                {dlqRuns.map((msg, i) => (
                  <li key={i} className="py-3">
                    <div className="flex flex-col">
                      <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">ID Message: {msg.message_id}</span>
                      <span className="text-sm font-medium text-gray-800">Run ID: {msg.data?.run_id}</span>
                      <span className="text-sm font-mono text-gray-500 mt-1 truncate">Question: {msg.data?.question}</span>
                      <span className="text-xs text-red-500 mt-1">Trace ID / Correlation: {msg.data?.correlation_id}</span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PlatformHealthPage;
