import React, { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './components/Login';
import AppLayout from './components/layout/AppLayout';

// Keep analytics-heavy pages out of the first paint. ECharts is loaded
// only when the user opens a conversation, result, or dashboard.
const ConversationsPage = lazy(() => import('./pages/ConversationsPage'));
const DataExplorerPage = lazy(() => import('./pages/DataExplorerPage'));
const ResultsPage = lazy(() => import('./pages/ResultsPage'));
const DataSourcesPage = lazy(() => import('./pages/DataSourcesPage'));
const AdminDataPage = lazy(() => import('./pages/AdminDataPage'));
const ProfilePage = lazy(() => import('./pages/ProfilePage'));
const DashboardsPage = lazy(() => import('./pages/DashboardsPage'));
const PlatformHealthPage = lazy(() => import('./pages/PlatformHealthPage'));
const DashboardDetailPage = lazy(() => import('./pages/DashboardDetailPage'));
const OnboardingPage = lazy(() => import('./pages/OnboardingPage'));
const HelpPage = lazy(() => import('./pages/HelpPage'));

import './App.css';

const PrivateRoute = ({ children }) => {
  const token = localStorage.getItem('token');
  return token ? children : <Navigate to="/login" />;
};

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<div className="app-route-loader" role="status">Chargement de l’espace de travail…</div>}>
        <Routes>
        <Route path="/login" element={<Login />} />
        
        <Route path="/" element={<PrivateRoute><AppLayout /></PrivateRoute>}>
          <Route index element={<Navigate to="/chat" replace />} />
          <Route path="chat" element={<ConversationsPage />} />
          <Route path="explorer" element={<DataExplorerPage />} />
          <Route path="sources" element={<DataSourcesPage />} />
          <Route path="results" element={<ResultsPage />} />
          <Route path="dashboards" element={<DashboardsPage />} />
          <Route path="dashboards/:id" element={<DashboardDetailPage />} />
          <Route path="admin/data" element={<AdminDataPage />} />
          <Route path="admin/health" element={<PlatformHealthPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="onboarding" element={<OnboardingPage />} />
          <Route path="help" element={<HelpPage />} />
        </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

export default App;
