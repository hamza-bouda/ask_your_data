import React from 'react';
import { HelpCircle, Database, Lock, Search, PlayCircle } from 'lucide-react';

export default function HelpPage() {
  return (
    <div className="page-container">
      <header className="page-header">
        <h1>Centre d'aide & Documentation</h1>
        <p>Découvrez comment exploiter pleinement Ask Your Data en toute sécurité.</p>
      </header>

      <div className="page-content" style={{ display: 'grid', gap: '32px' }}>
        
        <section className="glass-panel" style={{ padding: '32px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '24px', color: 'var(--text-main)' }}>
            <PlayCircle size={24} color="var(--accent)" /> Premiers pas
          </h2>
          <div style={{ display: 'grid', gap: '16px', lineHeight: '1.6' }}>
            <p><strong>1. Connectez votre base :</strong> Allez dans <em>Sources de données</em> pour lier votre base SQL en lecture seule.</p>
            <p><strong>2. Gouvernez les accès :</strong> Dans <em>Administration des données</em>, autorisez uniquement les tables contenant des données métier utiles et non-sensibles.</p>
            <p><strong>3. Posez vos questions :</strong> Demandez à l'IA d'analyser vos données en langage naturel (ex: "Quel est le revenu par mois pour l'année 2023 ?").</p>
            <p><strong>4. Sauvegardez et Partagez :</strong> Enregistrez les graphiques générés dans des Dashboards pour les consulter plus tard.</p>
          </div>
        </section>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '32px' }}>
          <section className="glass-panel" style={{ padding: '32px' }}>
            <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '24px', color: 'var(--text-main)' }}>
              <Search size={24} color="var(--accent)" /> Exemples de questions
            </h2>
            <ul style={{ display: 'grid', gap: '12px', listStyle: 'none', padding: 0 }}>
              <li style={{ padding: '12px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>"Quel est le top 5 des clients ayant le plus commandé en 2023 ?"</li>
              <li style={{ padding: '12px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>"Montre-moi l'évolution du chiffre d'affaires par mois sur les 12 derniers mois."</li>
              <li style={{ padding: '12px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>"Combien d'utilisateurs actifs avons-nous par pays (sous forme de camembert) ?"</li>
            </ul>
          </section>

          <section className="glass-panel" style={{ padding: '32px' }}>
            <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '24px', color: 'var(--text-main)' }}>
              <Lock size={24} color="var(--accent)" /> Sécurité & Limites
            </h2>
            <div style={{ display: 'grid', gap: '16px', lineHeight: '1.6' }}>
              <div style={{ padding: '16px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: '8px' }}>
                <strong style={{ color: 'var(--danger-color)', display: 'block', marginBottom: '8px' }}>Toutes les requêtes sont en lecture seule (Read-Only)</strong>
                Le système est configuré pour ne jamais modifier, supprimer ou altérer vos données. Les requêtes générées utilisent systématiquement `SELECT`.
              </div>
              <div style={{ padding: '16px', background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.2)', borderRadius: '8px' }}>
                <strong style={{ color: 'var(--warning-color)', display: 'block', marginBottom: '8px' }}>Limite de lignes (1000)</strong>
                Pour des raisons de performance, toutes les requêtes sont limitées à 1000 lignes de résultat par défaut. Si vous avez besoin d'agréger plus de données, demandez à l'agent de calculer la somme ou la moyenne directement.
              </div>
            </div>
          </section>
        </div>

      </div>
    </div>
  );
}
