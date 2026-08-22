# Runbook SRE : Plateforme Ask Your Data

Ce document fournit les procédures pour répondre aux alertes Prometheus et maintenir la santé de la plateforme.

## Alertes et Résolutions

### HighSqlErrorRate
**Description :** Plus de 5% des requêtes SQL échouent.
**Impact :** Les utilisateurs ne peuvent pas obtenir leurs résultats.
**Actions :**
1. Vérifier les logs du service `sql_executor` pour identifier les erreurs (syntaxe, timeouts).
2. Consulter Jaeger / Grafana pour voir si un schéma spécifique provoque des échecs.
3. Le cas échéant, utiliser l'interface d'administration pour bloquer ou corriger la source de données posant problème.

### DeadLetterQueueNotEmpty
**Description :** La DLQ contient des messages. Un ou plusieurs runs ont échoué après le nombre maximal de tentatives (3).
**Impact :** Des analyses ont échoué silencieusement ou sont restées bloquées pour l'utilisateur.
**Actions :**
1. Se connecter à l'interface d'administration "Santé de la plateforme" (`/admin/health`).
2. Identifier les `run_id` présents dans la DLQ.
3. Consulter les traces avec le Trace ID / Correlation ID fourni.
4. Pour rejouer un message (une fois le problème corrigé) :
   ```bash
   # (Exemple via redis-cli)
   XADD stream:tasks:runs * run_id <run_id> tenant_id <tenant_id> ...
   XDEL stream:dlq:runs <message_id>
   ```

### HighWorkerWaitTime
**Description :** Les workers mettent trop de temps à traiter les messages de la file d'attente (> 10s).
**Impact :** Latence élevée ressentie par l'utilisateur lors de la génération de la réponse.
**Actions :**
1. Vérifier la charge CPU/RAM des workers.
2. S'il n'y a pas d'engorgement au niveau base de données ou services dépendants (LLM), augmenter le nombre de réplicas pour le service `orchestrator` (le worker).

### HighPolicyDenialRate
**Description :** Taux élevé de refus de politique lors des requêtes SQL.
**Impact :** Les utilisateurs demandent des données auxquelles ils n'ont pas accès, potentiellement un problème d'hallucination du LLM.
**Actions :**
1. Examiner l'audit log pour vérifier quelles tables/colonnes sont demandées.
2. Mettre à jour le prompt système si le LLM suggère des tables non autorisées, ou ajouter les autorisations si nécessaire.

## Procédures courantes

### Reprise après redémarrage
- Les workers utilisent `XREADGROUP` pour reprendre là où ils s'étaient arrêtés.
- Une tâche asynchrone (`monitor_dlq_depth` et `claim_abandoned_messages`) s'assure que les messages pris en charge par des workers morts sont récupérés (`XCLAIM`) après 60 secondes.
