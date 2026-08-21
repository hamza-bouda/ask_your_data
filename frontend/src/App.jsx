import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './components/Login';
import AppLayout from './components/layout/AppLayout';

// Pages
import ConversationsPage from './pages/ConversationsPage';
import DataExplorerPage from './pages/DataExplorerPage';
import ResultsPage from './pages/ResultsPage';
import DataSourcesPage from './pages/DataSourcesPage';
import AdminDataPage from './pages/AdminDataPage';
import ProfilePage from './pages/ProfilePage';
import DashboardsPage from './pages/DashboardsPage';
import DashboardDetailPage from './pages/DashboardDetailPage';

import './App.css';

const PrivateRoute = ({ children }) => {
  const token = localStorage.getItem('token');
  return token ? children : <Navigate to="/login" />;
};

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        
        <Route path="/" element={<PrivateRoute><AppLayout /></PrivateRoute>}>
          <Route index element={<Navigate to="/chat" replace />} />
          <Route path="chat" element={<ConversationsPage />} />
          <Route path="explorer" element={<DataExplorerPage />} />
          <Route path="results" element={<ResultsPage />} />
          <Route path="dashboards" element={<DashboardsPage />} />
          <Route path="dashboards/:id" element={<DashboardDetailPage />} />
          <Route path="admin/data" element={<AdminDataPage />} />
          <Route path="profile" element={<ProfilePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
