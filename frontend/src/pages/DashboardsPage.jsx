import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';

const DashboardsPage = () => {
  const [dashboards, setDashboards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newVis, setNewVis] = useState('private');

  useEffect(() => {
    fetchDashboards();
  }, []);

  const fetchDashboards = async () => {
    try {
      const res = await api.get('/v1/dashboards');
      setDashboards(Array.isArray(res.data) ? res.data : []);
      setLoading(false);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
      setLoading(false);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      await api.post('/v1/dashboards', {
        name: newName,
        description: newDesc,
        visibility: newVis
      });
      setShowCreate(false);
      setNewName('');
      setNewDesc('');
      setNewVis('private');
      fetchDashboards();
    } catch (err) {
      alert("Error creating dashboard: " + err.message);
    }
  };

  if (loading) return <div className="p-4">Loading dashboards...</div>;
  if (error) return <div className="p-4 text-red-500">Error: {error}</div>;

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Dashboards</h1>
        <button 
          onClick={() => setShowCreate(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Create Dashboard
        </button>
      </div>

      {showCreate && (
        <div className="mb-6 p-4 border rounded bg-gray-50 dark:bg-gray-800">
          <h2 className="text-xl mb-4">New Dashboard</h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Name</label>
              <input required value={newName} onChange={e=>setNewName(e.target.value)} className="w-full p-2 border rounded dark:bg-gray-700" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Description</label>
              <input value={newDesc} onChange={e=>setNewDesc(e.target.value)} className="w-full p-2 border rounded dark:bg-gray-700" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Visibility</label>
              <select value={newVis} onChange={e=>setNewVis(e.target.value)} className="w-full p-2 border rounded dark:bg-gray-700">
                <option value="private">Private</option>
                <option value="tenant_viewers">Shared with Tenant</option>
              </select>
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setShowCreate(false)} className="px-4 py-2 border rounded hover:bg-gray-100 dark:hover:bg-gray-700">Cancel</button>
              <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Create</button>
            </div>
          </form>
        </div>
      )}

      {dashboards.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          No dashboards found. Create one to get started.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {dashboards.map(d => (
            <Link key={d.id} to={`/dashboards/${d.id}`} className="block p-6 border rounded-lg hover:shadow-lg transition-shadow bg-white dark:bg-gray-800">
              <h3 className="text-xl font-semibold mb-2">{d.name}</h3>
              <p className="text-gray-600 dark:text-gray-400 mb-4">{d.description || 'No description'}</p>
              <div className="flex justify-between items-center text-sm text-gray-500">
                <span>{d.visibility}</span>
                <span>{new Date(d.created_at).toLocaleDateString()}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};

export default DashboardsPage;
