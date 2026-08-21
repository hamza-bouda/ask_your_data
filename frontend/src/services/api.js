import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const login = async (username, password) => {
  const response = await api.post('/api/v1/auth/login', { username, password });
  return response.data;
};

export const registerDatabase = async (connectionString) => {
  const response = await api.post('/api/v1/catalog/register', { connection_string: connectionString });
  return response.data;
};

export const getConversations = async () => {
  const response = await api.get('/v1/conversations');
  return response.data;
};

export const createConversation = async (title = null) => {
  const response = await api.post('/v1/conversations', { title });
  return response.data;
};

export const getConversation = async (id) => {
  const response = await api.get(`/v1/conversations/${id}`);
  return response.data;
};

export const sendMessage = async (conversationId, message) => {
  try {
    const response = await api.post(`/v1/conversations/${conversationId}/messages`, { message });
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

export const getTables = async () => {
  const response = await api.get('/api/v1/catalog/tables');
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

export const getAdminAudit = async () => {
  const response = await api.get('/v1/datasources/audit');
  return response.data;
};

export const getAdminMetrics = async (sourceId) => {
  const response = await api.get(`/v1/datasources/${sourceId}/metrics`);
  return response.data;
};

export const createAdminMetric = async (sourceId, metricData) => {
  const response = await api.post(`/v1/datasources/${sourceId}/metrics`, metricData);
  return response.data;
};
