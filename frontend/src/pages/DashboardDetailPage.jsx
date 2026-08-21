import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';
import ChartRenderer from '../components/ChartRenderer';

const DashboardDetailPage = () => {
  const { id } = useParams();
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchDashboard();
  }, [id]);

  const fetchDashboard = async () => {
    try {
      const res = await axios.get(`/api/v1/dashboards/${id}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
      });
      setDashboard(res.data);
      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const removeItem = async (itemId) => {
    if (!window.confirm("Remove this item?")) return;
    try {
      await axios.delete(`/api/v1/dashboards/${id}/items/${itemId}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
      });
      fetchDashboard();
    } catch (err) {
      alert("Error removing item: " + err.message);
    }
  };

  const handleExport = async (messageId) => {
    try {
      const res = await axios.get(`/api/v1/results/${messageId}/export?format=csv`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `export_${messageId}.csv`);
      document.body.appendChild(link);
      link.click();
    } catch (err) {
      alert("Error exporting CSV. It might be blocked by a policy or unavailable.");
    }
  };

  if (loading) return <div className="p-4">Loading dashboard...</div>;
  if (error) return <div className="p-4 text-red-500">Error: {error}</div>;
  if (!dashboard) return <div className="p-4">Dashboard not found</div>;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <Link to="/dashboards" className="text-blue-500 hover:underline mb-2 inline-block">&larr; Back to Dashboards</Link>
        <h1 className="text-3xl font-bold">{dashboard.name}</h1>
        <p className="text-gray-600 dark:text-gray-400 mt-2">{dashboard.description}</p>
      </div>

      {dashboard.items.length === 0 ? (
        <div className="text-center py-12 text-gray-500 border rounded-lg bg-gray-50 dark:bg-gray-800">
          This dashboard is empty. Add results from the Chat or Results pages.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {dashboard.items.map(item => (
            <div key={item.id} className="border rounded-lg p-4 bg-white dark:bg-gray-800 shadow flex flex-col">
              <div className="flex justify-between items-center mb-4 pb-2 border-b">
                <h3 className="font-semibold text-lg">{item.title}</h3>
                <div className="flex gap-2">
                  <button onClick={() => handleExport(item.source_message_id)} className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded hover:bg-green-200">Export CSV</button>
                  <button onClick={() => removeItem(item.id)} className="text-xs px-2 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200">Remove</button>
                </div>
              </div>
              <div className="flex-1">
                {item.results ? (
                  <ChartRenderer data={item.results} chartSpec={item.chart_spec} />
                ) : (
                  <div className="text-gray-500 text-sm italic">No data available or loading...</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default DashboardDetailPage;
