import axios from 'axios';

// Development keeps the standalone Vite workflow. Production is same-origin:
// Nginx proxies API and SSE requests to the private Gateway container.
const API_URL = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');

export const api = axios.create({
  baseURL: API_URL
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  const sourceId = localStorage.getItem('activeSourceId');
  if (sourceId && !config.headers['X-Source-Id']) {
    config.headers['X-Source-Id'] = sourceId;
  }
  return config;
});

export const login = async (username, password) => {
  const response = await api.post('/api/v1/auth/login', { username, password });
  return response.data;
};

export const getActiveSourceId = () => localStorage.getItem('activeSourceId');

export const setActiveSourceId = (sourceId) => {
  if (sourceId) localStorage.setItem('activeSourceId', sourceId);
  else localStorage.removeItem('activeSourceId');
};

export const registerDatabase = async (connectionString, { name, sourceId } = {}) => {
  const response = await api.post('/api/v1/catalog/register', {
    connection_string: connectionString,
    name: name || undefined,
    source_id: sourceId || undefined,
  });
  return response.data;
};

export const getConversations = async () => {
  const response = await api.get('/v1/conversations');
  return response.data;
};

export const createConversation = async (title = null, sourceId = null) => {
  const headers = {};
  if (sourceId) headers['X-Source-Id'] = sourceId;
  const response = await api.post('/v1/conversations', { title }, { headers });
  return response.data;
};

export const getConversation = async (id) => {
  const response = await api.get(`/v1/conversations/${id}`);
  return response.data;
};

export const getResults = async (offset = 0, limit = 50) => {
  const response = await api.get('/v1/results', { params: { offset, limit } });
  return response.data;
};

export const getRun = async (runId) => {
  const response = await api.get(`/v1/runs/${runId}`);
  return response.data;
};

export const waitForRun = async (runId, timeoutMs = 60000) => {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const run = await getRun(runId);
    if (['completed', 'awaiting_clarification', 'failed', 'error'].includes(run.status)) {
      return run;
    }
    await new Promise(resolve => setTimeout(resolve, 750));
  }
  throw new Error("L'analyse prend plus de temps que prévu. Réessayez dans quelques instants.");
};

/**
 * Consume the run SSE stream with fetch so the JWT remains in the
 * Authorization header. Native EventSource cannot send that header.
 */
export const streamRunEvents = async (runId, onEvent, signal, lastEventId = null) => {
  const token = localStorage.getItem('token');
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (lastEventId) headers['Last-Event-ID'] = lastEventId;
  
  const response = await fetch(`${API_URL}/v1/runs/${runId}/events`, {
    headers,
    signal,
  });
  if (!response.ok || !response.body) {
    throw new Error('Le flux temps réel est indisponible.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let terminal = false;

  while (!terminal) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const messages = buffer.split('\n\n');
    buffer = messages.pop() || '';
    for (const message of messages) {
      const payload = message
        .split('\n')
        .filter(line => line.startsWith('data:'))
        .map(line => line.slice(5).trim())
        .join('');
      if (!payload) continue;
      const event = JSON.parse(payload);
      const msgIdMatch = message.match(/id:\s*(.+)/);
      const msgId = msgIdMatch ? msgIdMatch[1] : null;
      if (msgId) {
        event.lastEventId = msgId;
      }
      onEvent(event);
      terminal = ['result_ready', 'run_failed'].includes(event.event_type);
      if (terminal) break;
    }
  }
};

export const sendMessage = async (conversationId, message, sourceId = null) => {
  try {
    const headers = {};
    if (sourceId) headers['X-Source-Id'] = sourceId;
    const response = await api.post(`/v1/conversations/${conversationId}/messages`, { message }, { headers });
    return response.data;
  } catch (error) {
    console.error('Error sending message:', error);
    throw error;
  }
};

export const getDataSource = async () => {
  const response = await api.get('/api/v1/catalog/source');
  return response.data;
};

export const getDataSources = async () => {
  const response = await api.get('/api/v1/catalog/sources');
  return response.data.sources || [];
};

export const getTables = async () => {
  const response = await api.get('/api/v1/catalog/tables');
  return response.data;
};

export const getTablePreview = async (tableName, limit = 10, offset = 0) => {
  const response = await api.get(`/api/v1/catalog/tables/${encodeURIComponent(tableName)}/preview`, { params: { limit, offset } });
  return response.data;
};


// Admin Endpoints
export const getAdminDatasources = async () => {
  const response = await api.get('/v1/datasources');
  return response.data;
};

export const syncAdminDatasource = async (id) => {
  const response = await api.post(`/v1/datasources/${id}/sync`);
  return response.data;
};

export const updateAdminDatasource = async (id, changes) => {
  const response = await api.patch(`/v1/datasources/${id}`, changes);
  return response.data;
};

export const getAdminCatalog = async (id) => {
  const response = await api.get(`/v1/datasources/${id}/catalog`);
  return response.data;
};

export const updateTablePolicy = async (sourceId, tableId, isAllowed) => {
  const response = await api.patch(`/v1/datasources/${sourceId}/catalog/tables/${tableId}`, { is_allowed: isAllowed });
  return response.data;
};

export const updateColumnPolicy = async (sourceId, tableId, columnId, isAllowed) => {
  const response = await api.patch(`/v1/datasources/${sourceId}/catalog/tables/${tableId}/columns/${columnId}`, { is_allowed: isAllowed });
  return response.data;
};

export async function getAdminAudit() {
  const response = await api.get('/v1/audit');
  return response.data;
};

export const getAdminMetrics = async (sourceId) => {
  const response = await api.get('/api/v1/catalog/metrics', { headers: { 'X-Source-Id': sourceId } });
  return response.data;
};

export const createAdminMetric = async (sourceId, metricData) => {
  const response = await api.post('/api/v1/catalog/metrics', metricData, { headers: { 'X-Source-Id': sourceId } });
  return response.data;
};

export const updateAdminMetric = async (sourceId, metricId, changes) => {
  const response = await api.patch(`/api/v1/catalog/metrics/${metricId}`, changes, { headers: { 'X-Source-Id': sourceId } });
  return response.data;
};

export const getAdminStuckRuns = async () => {
  const response = await api.get('/v1/admin/health/runs/stuck');
  return response.data;
};

export const getAdminDlqRuns = async () => {
  const response = await api.get('/v1/admin/health/runs/dlq');
  return response.data;
};

export const globalSearch = async (q, limit = 10) => {
  const response = await api.get('/api/v1/search', { params: { q, limit } });
  return response.data;
};
