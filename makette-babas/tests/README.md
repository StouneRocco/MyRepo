# Tests automatisés

Tous les tests du projet, rangés par partie. Ils tournent sans MongoDB, sans
caméra, sans projecteur et sans réseau : la base, le matériel OpenCV et les
appels HTTP sont remplacés par des doubles. Aucun fichier du dépôt n'est
modifié (les tests écrivent uniquement dans des dossiers temporaires).

## Lancer les tests

Depuis la racine du projet, avec l'environnement Python du backend :

```powershell
backend/.venv/Scripts/python.exe tests/run_all.py                    # toutes les parties
backend/.venv/Scripts/python.exe tests/run_all.py backend shared     # une sélection
```

Une partie seule, comme dans la CI :

```powershell
backend/.venv/Scripts/python.exe -m unittest discover -s tests/backend -t .
backend/.venv/Scripts/python.exe -m unittest discover -s tests/projector -t .
backend/.venv/Scripts/python.exe -m unittest discover -s tests/shared -t .
npm.cmd --prefix frontend test
```

Un seul fichier : `python -m unittest tests.backend.test_view_state`, ou
`node --test tests/frontend/api.test.js`.

## Organisation

| Dossier | Partie validée | Tests |
|---|---|---|
| `backend/` | `backend/` : API Flask, données, outils en ligne de commande | 148 |
| `projector/` | `projector-pi/` : récepteur, géométrie, calibration, tracking | 60 |
| `shared/` | `shared/` et cohérence entre site et projecteur | 17 |
| `frontend/` | `frontend/src` et `frontend/public` (Node.js, sans navigateur) | 37 |
| `fixtures/` | Données de référence communes aux tests Python et JavaScript | — |

### backend

- `test_api_auth.py` : JWT (expiré, falsifié, sans expiration, algorithme `none`), comptes désactivés ou révoqués, rôle lecteur sans commande, inscription (premier compte opérateur, fermeture, doublon), connexion, limitation à 20 tentatives/min par adresse, en-têtes de sécurité, 503 si MongoDB tombe, taille maximale des requêtes, service du site compilé sans fuite de fichiers hors `dist`.
- `test_api_projection.py` : relais vers le récepteur (calibration, salle, températures, réglages, aperçu), validation avant tout envoi, codes 502 quand le récepteur est absent, priorité de la vue partagée.
- `test_api_temperatures.py` : fenêtre de ±10 min autour de l'instant demandé, conversion des fuseaux, dates invalides, plage disponible, routes protégées.
- `test_temperature_day.py` : journées de Paris (23 h et 25 h aux changements d'heure), créneaux de 5 min, interpolation limitée à 180 min, cache de 30 s, plans N3/N4.
- `test_import_temperatures.py` : CSV (`,` `;` tabulation, BOM), XLSX (feuille choisie, CSV dans la colonne A), heures locales inexistantes/ambiguës, virgule décimale, doublons, `--replace-existing`, rapport `--dry-run`.
- `test_badgeage_views.py` : agrégats horaires des badgeages, rapprochement avec les plans, cache invalidé au remplacement du CSV, cohérence des totaux sur le vrai fichier.
- `test_view_state.py` : vue partagée PC/tablette, révisions, lecture pilotée par le serveur, redémarrage, pannes MongoDB/récepteur, contenu envoyé au projecteur.
- `test_api_docs.py` : Swagger local, sans connexion requise, et routes documentées comparées aux routes Flask.
- `test_backup_data.py`, `test_tls_setup.py`, `test_manage_users.py`, `test_healthcheck.py` : sauvegarde/restauration, HTTPS local, gestion des comptes, contrôle de MongoDB au lancement.

### projector

- `test_room_projection.py` : recalage du plan SVG sur le JPG, aplats à 65 %, couleurs, sélection, bandeau projeté.
- `test_projection_calibration.py` : validation des quatre coins, matrices automatique et manuelle.
- `test_marker_tracking.py` : pose complète, lissage, rejet des poses croisées ou incomplètes.
- `test_receiver_api.py` : le vrai `color_receiver.py`, avec caméra et fenêtres simulées : routes HTTP, conflits de révision, sauvegarde atomique, aperçu JPEG, manipulation à la souris.

### shared

- `test_projection_context.py` : contexte du bandeau accepté par le backend et le récepteur.
- `test_shared_data.py` : catalogue N3 identique dans le plan du site et pour le projecteur, codes N3/N4 distincts, échelle 12–30 °C, mêmes couleurs que le site (`fixtures/temperature-colors.json`).

### frontend

`api`, `temperatureTime`, `heatmap`, `calendar`, `presence`, `viewSync`, `calibrationSender`, `pwa` (manifeste, icônes, service worker hors ligne) et `openapi` (spécification valide, jeton Swagger jamais conservé). `openapi.test.js` utilise une dépendance npm : lancer `npm ci` dans `frontend/` au préalable.

## Limites

- Les composants React (`*.jsx`) ne sont pas rendus dans les tests : `npm run build` vérifie leur compilation, leur comportement se vérifie dans le navigateur.
- La détection ArUco réelle, l'image projetée, la tablette et la stabilité prolongée restent à valider sur la maquette.
- `calibration.py` et `testCam.py` sont des outils interactifs de matériel, sans test automatisé.
