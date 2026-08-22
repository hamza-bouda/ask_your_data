import React, { useCallback, useEffect, useState } from 'react';
import { BarChart3, Globe2, LockKeyhole, Plus, RefreshCw, Archive, Copy } from 'lucide-react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';

const visibilityLabel = (visibility) => visibility === 'tenant_viewers' ? 'Partagé avec l’organisation' : 'Privé';

const DashboardsPage = () => {
  const [dashboards, setDashboards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState({ name: '', description: '', visibility: 'private' });
  const [activeTab, setActiveTab] = useState('active');

  const fetchDashboards = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const { data } = await api.get('/v1/dashboards', { params: { include_archived: true } });
      setDashboards(Array.isArray(data) ? data : []);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Impossible de charger les dashboards.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDashboards(); }, [fetchDashboards]);

  const closeCreate = () => {
    setShowCreate(false);
    setDraft({ name: '', description: '', visibility: 'private' });
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    setCreating(true);
    setError('');
    try {
      await api.post('/v1/dashboards', draft);
      closeCreate();
      await fetchDashboards();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Impossible de créer le dashboard.');
    } finally {
      setCreating(false);
    }
  };

  const activeDashboards = dashboards.filter(d => !d.archived);
  const archivedDashboards = dashboards.filter(d => d.archived);
  const displayedDashboards = activeTab === 'active' ? activeDashboards : archivedDashboards;

  return (
    <div className="page-container dashboard-page">
      <header className="page-header dashboard-header">
        <div>
          <p className="eyebrow"><BarChart3 size={15} /> Analyse partagée</p>
          <h1>Dashboards</h1>
          <p>Regroupez les résultats fiables de vos conversations pour les consulter ou les partager.</p>
        </div>
        <div className="dashboard-header-actions">
          <button type="button" className="icon-btn" title="Actualiser" aria-label="Actualiser les dashboards" onClick={fetchDashboards} disabled={loading}>
            <RefreshCw size={18} className={loading ? 'spinner' : ''} />
          </button>
          <button type="button" className="btn-primary" onClick={() => setShowCreate(true)}><Plus size={18} /> Nouveau dashboard</button>
        </div>
      </header>

      <div className="dashboard-tabs">
        <button className={activeTab === 'active' ? 'active' : ''} onClick={() => setActiveTab('active')}>Actifs ({activeDashboards.length})</button>
        <button className={activeTab === 'archived' ? 'active' : ''} onClick={() => setActiveTab('archived')}>Archivés ({archivedDashboards.length})</button>
      </div>

      {error && <div className="error-message" role="alert">{error}</div>}
      
      {showCreate && <section className="dashboard-create card" aria-labelledby="dashboard-create-title"><div><h2 id="dashboard-create-title">Créer un dashboard</h2><p>Vous pourrez y ajouter les résultats sauvegardés depuis une conversation.</p></div><form className="dashboard-form" onSubmit={handleCreate}><label>Nom<input required maxLength="120" autoFocus value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} placeholder="Ex. Vue commerciale hebdomadaire" /></label><label>Description <span className="field-optional">optionnelle</span><textarea maxLength="500" value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} placeholder="Objectif et périmètre de l’analyse" rows="3" /></label><fieldset className="visibility-options"><legend>Visibilité</legend><label className="visibility-option"><input type="radio" name="visibility" value="private" checked={draft.visibility === 'private'} onChange={(event) => setDraft({ ...draft, visibility: event.target.value })} /><LockKeyhole size={17} /><span><strong>Privé</strong><small>Visible uniquement par vous.</small></span></label><label className="visibility-option"><input type="radio" name="visibility" value="tenant_viewers" checked={draft.visibility === 'tenant_viewers'} onChange={(event) => setDraft({ ...draft, visibility: event.target.value })} /><Globe2 size={17} /><span><strong>Organisation</strong><small>Visible par les membres autorisés de votre organisation.</small></span></label></fieldset><div className="form-actions"><button type="button" className="btn-secondary" onClick={closeCreate} disabled={creating}>Annuler</button><button type="submit" className="btn-primary" disabled={creating}>{creating ? 'Création…' : 'Créer le dashboard'}</button></div></form></section>}
      
      {loading ? <div className="page-loading"><RefreshCw size={22} className="spinner" /> Chargement des dashboards…</div> : displayedDashboards.length === 0 ? <section className="empty-state dashboard-empty"><div className="empty-state-icon"><BarChart3 size={30} /></div><h2>{activeTab === 'active' ? 'Votre espace d’analyse est prêt' : 'Aucun dashboard archivé'}</h2>{activeTab === 'active' && <><p>Créez un dashboard, puis ajoutez-y un résultat depuis une conversation ou la page Résultats.</p><button type="button" className="btn-primary" onClick={() => setShowCreate(true)}><Plus size={18} /> Créer mon premier dashboard</button></>}</section> : <section className="dashboard-grid" aria-label="Liste des dashboards">{displayedDashboards.map((dashboard) => <Link key={dashboard.id} to={`/dashboards/${dashboard.id}`} className="dashboard-card"><div className="dashboard-card-top"><span className={`visibility-badge ${dashboard.visibility}`}>{dashboard.visibility === 'tenant_viewers' ? <Globe2 size={14} /> : <LockKeyhole size={14} />}{visibilityLabel(dashboard.visibility)}</span><BarChart3 size={22} className="dashboard-card-icon" /></div><h2>{dashboard.name}</h2><p>{dashboard.description || 'Aucune description.'}</p><footer>Créé le {new Date(dashboard.created_at).toLocaleDateString('fr-FR')}</footer></Link>)}</section>}
    </div>
  );
};

export default DashboardsPage;
