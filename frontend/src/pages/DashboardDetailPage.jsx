import React, { useCallback, useEffect, useState, useMemo } from 'react';
import { ArrowLeft, Download, FileWarning, Globe2, LockKeyhole, Pencil, RefreshCw, Trash2, Archive, Copy, Printer, GripHorizontal, Settings2 } from 'lucide-react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import ChartRenderer from '../components/ChartRenderer';
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { arrayMove, SortableContext, sortableKeyboardCoordinates, rectSortingStrategy, useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

const SortableItem = ({ id, item, handleExport, removeItem, isOwner, updateItemConfig }) => {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id });
  const [showConfig, setShowConfig] = useState(false);
  const [localTitle, setLocalTitle] = useState(item.title);
  const [localNotes, setLocalNotes] = useState(item.notes || '');
  const [localWidth, setLocalWidth] = useState(item.display_config?.width || 'full');

  const style = { transform: CSS.Transform.toString(transform), transition };
  const widgetClass = `dashboard-item-card widget-${item.display_config?.width || 'full'}`;

  const saveConfig = () => {
    updateItemConfig(item.id, {
      title: localTitle,
      notes: localNotes,
      display_config: { ...item.display_config, width: localWidth }
    });
    setShowConfig(false);
  };

  return (
    <article ref={setNodeRef} style={style} className={widgetClass}>
      <header>
        <div className="widget-header-left">
          {isOwner && <div className="drag-handle" {...attributes} {...listeners}><GripHorizontal size={16} /></div>}
          <div>
            <h2>{item.title}</h2>
            <div className="widget-provenance">
              {item.source_id && <span title="Source de la base de données">Source: {item.source_id}</span>}
              {item.execution_date && <span title="Date d'exécution originale"> • Exécuté le {new Date(item.execution_date).toLocaleString('fr-FR')}</span>}
            </div>
            {item.notes && <p className="widget-notes">{item.notes}</p>}
          </div>
        </div>
        <div className="dashboard-item-actions no-print">
          {isOwner && <button className="icon-btn" title="Configurer le widget" onClick={() => setShowConfig(true)}><Settings2 size={17} /></button>}
          <button className="icon-btn" title="Exporter le CSV" onClick={() => handleExport(item.source_message_id)}><Download size={17} /></button>
          {isOwner && <button className="icon-btn danger-icon" title="Retirer du dashboard" onClick={() => removeItem(item.id)}><Trash2 size={17} /></button>}
        </div>
      </header>
      
      {showConfig && (
        <div className="widget-config-panel no-print">
          <label>Titre <input value={localTitle} onChange={e => setLocalTitle(e.target.value)} /></label>
          <label>Notes <textarea value={localNotes} onChange={e => setLocalNotes(e.target.value)} rows="2" /></label>
          <label>Largeur 
            <select value={localWidth} onChange={e => setLocalWidth(e.target.value)}>
              <option value="full">Pleine largeur</option>
              <option value="half">Moitié (1/2)</option>
            </select>
          </label>
          <div className="form-actions" style={{ marginTop: '0.5rem' }}>
            <button className="btn-secondary" onClick={() => setShowConfig(false)}>Annuler</button>
            <button className="btn-primary" onClick={saveConfig}>Appliquer</button>
          </div>
        </div>
      )}

      {item.results?.length ? (
        <ChartRenderer data={item.results} chartSpec={item.chart_spec} />
      ) : (
        <div className="dashboard-item-unavailable">Les données de ce résultat ne sont plus disponibles.</div>
      )}
      {item.semantic_context?.intent && <div className="widget-context no-print">Contexte : {item.semantic_context.intent}</div>}
      {item.sql_query && (
        <details className="widget-sql no-print">
          <summary>Requête SQL</summary>
          <pre>{item.sql_query}</pre>
        </details>
      )}
    </article>
  );
};

const DashboardDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState({ name: '', description: '', visibility: 'private' });
  
  const [globalFilter, setGlobalFilter] = useState('');
  const [items, setItems] = useState([]);

  // Setup DnD sensors
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const currentUser = useMemo(() => {
    try { return JSON.parse(localStorage.getItem('user') || '{}'); } catch { return {}; }
  }, []);

  const isOwner = dashboard?.owner_user_id === currentUser.id;

  const fetchDashboard = useCallback(async () => { 
    setLoading(true); 
    setError(''); 
    try { 
      const { data } = await api.get(`/v1/dashboards/${id}`); 
      setDashboard(data);
      setItems(data.items || []);
      setDraft({ name: data.name, description: data.description || '', visibility: data.visibility }); 
    } catch (requestError) { 
      setError(requestError.response?.data?.detail || 'Impossible de charger ce dashboard.'); 
    } finally { 
      setLoading(false); 
    } 
  }, [id]);
  
  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);
  
  const saveDashboard = async (event) => { 
    event.preventDefault(); 
    setSaving(true); 
    setError(''); 
    try { 
      await api.patch(`/v1/dashboards/${id}`, draft); 
      setEditing(false); 
      await fetchDashboard(); 
    } catch (requestError) { 
      setError(requestError.response?.data?.detail || 'Impossible d’enregistrer le dashboard.'); 
    } finally { 
      setSaving(false); 
    } 
  };
  
  const toggleArchive = async () => {
    try {
      await api.patch(`/v1/dashboards/${id}`, { archived: !dashboard.archived });
      await fetchDashboard();
    } catch (requestError) {
      setError('Impossible d\'archiver/désarchiver ce dashboard.');
    }
  };

  const duplicateDashboard = async () => {
    try {
      const { data } = await api.post(`/v1/dashboards/${id}/duplicate`);
      navigate(`/dashboards/${data.id}`);
    } catch (requestError) {
      setError('Impossible de dupliquer ce dashboard.');
    }
  };

  const deleteDashboard = async () => { 
    if (!window.confirm('Supprimer définitivement ce dashboard ? Cette action est irréversible.')) return; 
    try { 
      await api.delete(`/v1/dashboards/${id}`); 
      navigate('/dashboards'); 
    } catch (requestError) { 
      setError(requestError.response?.data?.detail || 'Impossible de supprimer le dashboard.'); 
    } 
  };
  
  const removeItem = async (itemId) => { 
    if (!window.confirm('Retirer ce résultat du dashboard ?')) return; 
    try { 
      await api.delete(`/v1/dashboards/${id}/items/${itemId}`); 
      setItems(items.filter(item => item.id !== itemId));
    } catch (requestError) { 
      setError(requestError.response?.data?.detail || 'Impossible de retirer ce résultat.'); 
    } 
  };

  const updateItemConfig = async (itemId, config) => {
    try {
      await api.patch(`/v1/dashboards/${id}/items/${itemId}`, config);
      setItems(items.map(item => item.id === itemId ? { ...item, ...config } : item));
    } catch (requestError) {
      setError('Impossible de mettre à jour le widget.');
    }
  };

  const handleDragEnd = async (event) => {
    const { active, over } = event;
    if (active.id !== over?.id) {
      const oldIndex = items.findIndex((i) => i.id === active.id);
      const newIndex = items.findIndex((i) => i.id === over.id);
      const newItems = arrayMove(items, oldIndex, newIndex);
      setItems(newItems);
      
      // Update order in backend sequentially or rely on order in array
      try {
        await api.patch(`/v1/dashboards/${id}/items/${active.id}`, { order: newIndex });
        // NOTE: A robust implementation would update all items between oldIndex and newIndex
      } catch (err) {
        console.error("Failed to persist order", err);
      }
    }
  };

  const handleExport = async (messageId) => { 
    try { 
      const response = await api.get(`/v1/results/${messageId}/export`, { params: { format: 'csv' }, responseType: 'blob' }); 
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/csv' })); 
      const link = document.createElement('a'); 
      link.href = url; link.download = `askyourdata-${messageId}.csv`; 
      document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url); 
    } catch (requestError) { 
      setError(requestError.response?.data?.detail || 'L’export CSV est indisponible pour ce résultat.'); 
    } 
  };
  
  if (loading) return <div className="page-loading"><RefreshCw size={22} className="spinner" /> Chargement du dashboard…</div>;
  if (error && !dashboard) return <div className="page-container"><div className="error-message" role="alert">{error}</div><Link className="btn-secondary" to="/dashboards"><ArrowLeft size={16} /> Retour aux dashboards</Link></div>;
  if (!dashboard) return null;
  
  // Simple local filter logic
  const filteredItems = items.map(item => {
    if (!globalFilter) return item;
    const filterLower = globalFilter.toLowerCase();
    // Filter rows in item.results where any value matches the global filter string
    const filteredResults = (item.results || []).filter(row => 
      Object.values(row).some(val => String(val).toLowerCase().includes(filterLower))
    );
    return { ...item, results: filteredResults };
  });

  return (
    <div className="page-container dashboard-detail-page">
      <Link to="/dashboards" className="back-link no-print"><ArrowLeft size={16} /> Tous les dashboards</Link>
      {error && <div className="error-message no-print" role="alert">{error}</div>}
      
      <header className="dashboard-detail-header">
        {editing ? (
          <form className="dashboard-edit-form" onSubmit={saveDashboard}>
            <label>Nom<input value={draft.name} required maxLength="120" onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
            <label>Description<textarea rows="2" maxLength="500" value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} /></label>
            <label>Visibilité
              <select value={draft.visibility} onChange={(event) => setDraft({ ...draft, visibility: event.target.value })}>
                <option value="private">Privé</option>
                <option value="tenant_viewers">Partagé avec l’organisation</option>
              </select>
            </label>
            <div className="form-actions">
              <button type="button" className="btn-secondary" disabled={saving} onClick={() => setEditing(false)}>Annuler</button>
              <button type="submit" className="btn-primary" disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</button>
            </div>
          </form>
        ) : (
          <>
            <div>
              <span className={`visibility-badge ${dashboard.visibility}`}>
                {dashboard.visibility === 'tenant_viewers' ? <Globe2 size={14} /> : <LockKeyhole size={14} />}
                {dashboard.visibility === 'tenant_viewers' ? 'Partagé avec l’organisation' : 'Privé'}
              </span>
              {dashboard.archived && <span className="visibility-badge archived">Archivé</span>}
              <h1>{dashboard.name}</h1>
              {dashboard.description && <p>{dashboard.description}</p>}
            </div>
            
            <div className="dashboard-detail-actions no-print">
              <input 
                type="text" 
                placeholder="Filtrer les données (Dates, Source, Valeurs...)" 
                value={globalFilter} 
                onChange={(e) => setGlobalFilter(e.target.value)}
                className="dashboard-filter-input"
              />
              <button className="btn-secondary" onClick={() => window.print()} title="Imprimer ou Exporter en PDF"><Printer size={16} /> Imprimer</button>
              <button className="btn-secondary" onClick={duplicateDashboard} title="Dupliquer"><Copy size={16} /> Dupliquer</button>
              
              {isOwner && (
                <>
                  <button className="btn-secondary" onClick={toggleArchive} title={dashboard.archived ? "Désarchiver" : "Archiver"}>
                    <Archive size={16} /> {dashboard.archived ? "Désarchiver" : "Archiver"}
                  </button>
                  <button className="btn-secondary" onClick={() => setEditing(true)}><Pencil size={16} /> Modifier</button>
                  <button className="btn-danger" onClick={deleteDashboard}><Trash2 size={16} /> Supprimer</button>
                </>
              )}
            </div>
          </>
        )}
      </header>
      
      {items.length === 0 ? (
        <section className="empty-state dashboard-empty no-print">
          <div className="empty-state-icon"><FileWarning size={30} /></div>
          <h2>Ce dashboard ne contient aucun résultat</h2>
          <p>Depuis la conversation ou les résultats, utilisez « Sauvegarder » pour ajouter un graphique ou un tableau ici.</p>
        </section>
      ) : (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={filteredItems.map(i => i.id)} strategy={rectSortingStrategy}>
            <section className="dashboard-item-grid" aria-label="Résultats du dashboard">
              {filteredItems.map((item) => (
                <SortableItem 
                  key={item.id} 
                  id={item.id} 
                  item={item} 
                  handleExport={handleExport} 
                  removeItem={removeItem}
                  isOwner={isOwner}
                  updateItemConfig={updateItemConfig}
                />
              ))}
            </section>
          </SortableContext>
        </DndContext>
      )}
    </div>
  );
};

export default DashboardDetailPage;
