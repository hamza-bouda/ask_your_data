# Guide Qualité & Tests (QA)

Ce document décrit comment exécuter et valider la couverture de tests du projet **Ask Your Data**.

## 1. Tests Unitaires & Couverture

### Frontend
Le frontend utilise `vitest` et `react-testing-library`.
```bash
cd frontend
npm run test           # Lancer les tests
npm run test:coverage  # Générer un rapport de couverture
```

### Backend
Le backend utilise `pytest` et `pytest-cov`.
```bash
# Lancer les tests de tous les services avec couverture
python -m pytest --cov=backend/services --cov=packages --cov-report=term-missing
```

## 2. Tests d'Intégration et de Résilience
Les tests avancés se trouvent dans `tests/`.
- `tests/integration/` : Isolation multi-tenant et cycle de vie DB.
- `tests/resilience/` : Tolérance aux pannes (timeouts SQL, pannes LLM/Redis).
- `tests/contract/` : Validation des contrats inter-services.

Exécuter des marqueurs spécifiques :
```bash
python -m pytest -m integration
python -m pytest -m resilience
```

## 3. Tests de Non-Régression sur base Chinook
Nous avons un script pour initialiser une base d'exemple (`chinook_test.db`) avec une politique de sécurité prédéfinie.
```bash
python tests/fixtures/setup_chinook_allowlist.py
python -m pytest tests/e2e/test_chinook_regression.py
```

## 4. Tests E2E Navigateur (Playwright)
Un composant `e2e-browser` simule les interactions utilisateurs critiques de bout en bout.
```bash
cd e2e-browser
npm install
npx playwright install
npm run test
```

En cas d'échec dans la CI, un rapport HTML contenant les traces et screenshots est généré dans `playwright-report/` et uploadé comme artefact.
