import React, { useEffect, useState } from 'react';
import { CheckCircle2, FolderPlus, Save, X } from 'lucide-react';
import { api } from '../services/api';

export default function SaveToDashboardDialog({ messageId, title, onClose }) {
  const [dashboards, setDashboards] = useState([]);
  const [dashboardId, setDashboardId] = useState('');
  const [newName, setNewName] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    let active = true;
    api.get('/v1/dashboards')
      .then(({ data }) => {
        if (!active) return;
        const items = Array.isArray(data) ? data : [];
        setDashboards(items);
        setDashboardId(items[0]?.id || '');
      })
      .catch((requestError) => active && setError(requestError.response?.data?.detail || 'Impossible de charger les dashboards.'))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  const handleSave = async (event) => {
    event.preventDefault();
    setSaving(true); setError('');
    try {
      let targetId = dashboardId;
      if (!targetId) {
        if (!newName.trim()) throw new Error('Donnez un nom au nouveau dashboard.');
        const { data } = await api.post('/v1/dashboards', { name: newName.trim(), visibility: 'private' });
        targetId = data.id;
      }
      await api.post(`/v1/dashboards/${targetId}/items`, { source_message_id: messageId, title, order: 0 });
      setSuccess(true);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || requestError.message || 'Impossible de sauvegarder ce résultat.');
    } finally { setSaving(false); }
  };

  return <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
    <section className="save-dashboard-dialog card" role="dialog" aria-modal="true" aria-labelledby="save-dashboard-title" onMouseDown={(event) => event.stopPropagation()}>
      <header><div><h2 id="save-dashboard-title">Ajouter au dashboard</h2><p>{title}</p></div><button className="icon-btn" onClick={onClose} aria-label="Fermer"><X size={18} /></button></header>
      {success ? <div className="dialog-success"><CheckCircle2 size={26} /><div><strong>Résultat sauvegardé</strong><p>Il est maintenant disponible dans votre dashboard.</p></div><button className="btn-primary" onClick={onClose}>Terminer</button></div> : <form onSubmit={handleSave}>
        {error && <div className="error-message" role="alert">{error}</div>}
        {loading ? <p className="dialog-status">Chargement des dashboards…</p> : dashboards.length > 0 ? <label>Dashboard existant<select value={dashboardId} onChange={(event) => setDashboardId(event.target.value)}>{dashboards.map((dashboard) => <option key={dashboard.id} value={dashboard.id}>{dashboard.name}</option>)}</select></label> : <label>Nom du dashboard<input autoFocus maxLength="120" value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="Ex. Analyse commerciale" /></label>}
        <footer><button type="button" className="btn-secondary" onClick={onClose} disabled={saving}>Annuler</button><button type="submit" className="btn-primary" disabled={saving || loading}><Save size={16} /> {saving ? 'Sauvegarde…' : dashboards.length > 0 ? 'Ajouter au dashboard' : <><FolderPlus size={16} /> Créer et ajouter</>}</button></footer>
      </form>}
    </section>
  </div>;
}
