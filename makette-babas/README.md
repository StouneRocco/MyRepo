# Webapp de calibration (Raspberry Pi 5)

## Application sur tablette et choix de la journée

Le calendrier **Journée** donne accès aux dates de janvier à juin lorsque
les six CSV sont importés.
Les données et la page d'accueil ne sont pas conservées dans un ancien cache.

Sur le réseau local en HTTP, utilise **Plein écran** après l'ouverture du site
ou de son raccourci. Ce bouton masque la barre du navigateur ; le navigateur
demande un geste utilisateur à chaque nouvelle ouverture. Il est également
disponible sur la page de connexion. **Quitter le plein écran** rétablit le
navigateur normal.

Le manifeste configure une installation PWA en mode `standalone`, avec ses
icônes. Sur tablette Chrome, une véritable installation qui démarre directement
sans barre d'adresse nécessite une adresse HTTPS reconnue par l'appareil ;
un raccourci vers l'adresse IP en HTTP ne garantit pas ce comportement.
Les fichiers et les températures restent servis par le PC, sans copie périmée
des mesures dans le service worker.

Si un certificat HTTPS reconnu est déjà disponible, définir `TLS_CERT_FILE`
et `TLS_KEY_FILE` avant le lancement active HTTPS sur le même port 5000.
Le certificat doit correspondre à l'adresse utilisée sur la tablette.

### HTTPS local et installation sur tablette Android

Depuis la racine, générer les certificats pour l'adresse IPv4 actuelle du PC :
```powershell
powershell -ExecutionPolicy Bypass -File .\setup-https.ps1 -IpAddress 10.21.23.100
powershell -ExecutionPolicy Bypass -File .\start-pc.ps1
```
Le script utilise le binaire officiel mkcert et crée une autorité locale dans
`backend/.tls/ca`. Il ne modifie pas les autorités de confiance de Windows.
Tout `backend/.tls/` est exclu de Git, y compris les clés et les journaux.
Le lanceur détecte ces certificats et démarre ensuite automatiquement en HTTPS.

Sur la tablette, ouvrir `http://10.21.23.100:5080/` et télécharger
**maquette-ca.crt**. Dans les paramètres Android, rechercher **Installer un
certificat**, choisir **Certificat CA** et sélectionner ce fichier. Cette
opération ajoute l'autorité locale du PC aux certificats reconnus par l'appareil.
Comparer son empreinte SHA-256 avec celle affichée au démarrage sur le PC.
Ne partager aucune clé privée, en particulier `rootCA-key.pem` et `server-key.pem`.
La page HTTP sur le port 5080 sert uniquement les instructions et ce certificat
public ; elle ne donne accès ni aux clés, ni aux comptes, ni aux températures.

Fermer puis rouvrir Chrome et accéder à `https://10.21.23.100:5000/`.
Le site doit être reconnu sans avertissement avant de choisir **Installer
l'application** dans le menu Chrome. Ouvrir ensuite la nouvelle icône HTTPS,
qui utilise le manifeste `standalone`. L'ancien raccourci HTTP est distinct.
Il faut se reconnecter car HTTP et HTTPS ne partagent pas le stockage de session.

Pour utiliser également HTTPS dans Chrome sur le PC, importer manuellement le
même certificat public dans les autorités racines de confiance de l'utilisateur.
Si l'adresse IP change, relancer `setup-https.ps1` avec la nouvelle adresse puis
redémarrer le site. Le script conserve l'autorité existante : le certificat CA
installé sur les appareils reste valable. Le serveur de projection reste local
sur `http://127.0.0.1:5001`, sans changement de calibration.

## Lancement sur PC Windows

Prérequis : Python 3.11, Node.js et Docker Desktop démarré (conteneurs Linux).
Depuis la racine du projet, dans PowerShell :

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt -r projector-pi/requirements.txt
cd frontend
npm.cmd ci
npm.cmd run build
cd ..
docker compose up -d mongo
$env:MONGO_DB = 'calibration_app_pc'
backend/.venv/Scripts/python.exe backend/import_temperatures.py ressources/temperature_clean.xlsx
powershell -ExecutionPolicy Bypass -File ./start-pc.ps1 -Projector
```

Ouvre http://localhost:5000 et crée un compte local. Les comptes et données du Pi
ne sont pas transférés avec Git ; l'import ci-dessus charge les mesures fournies.
Le lanceur réutilise MongoDB s'il est déjà disponible sur le port 27017.
Il utilise une base séparée `calibration_app_pc` pour préserver les anciennes
données locales, qui peuvent avoir un format différent. `MONGO_DB` permet de
choisir une autre base pour le backend et l'import.
Sans caméra, lance `./start-pc.ps1` sans `-Projector` pour consulter l'interface.

Branche une caméra USB compatible Windows et le projecteur, puis choisis
**Étendre ces affichages** dans les paramètres Windows. Par défaut, la caméra
est à l'index 0 et le projecteur commence à la coordonnée écran `(1920, 0)`.
Exemple avec un écran principal de 2560 pixels et une seconde caméra :
`./start-pc.ps1 -Projector -CameraIndex 1 -ProjectorX 2560`.
`-ProjectorY` permet de régler le décalage vertical. La projection reste en
1920 × 1080 ; configure cette résolution sur le projecteur.
Les paramètres optiques `mtx` et `dist` dans `projector-pi/color_receiver.py`
correspondent à la caméra du Pi : ils doivent être recalibrés si tu changes de
caméra. Le bouton « Calibrer » règle ensuite le recalage ArUco sur la maquette.
La touche `q` dans une fenêtre OpenCV ferme le récepteur.

Navigateur -> Flask (port 5000, auth JWT, sert le front React) -> color_receiver.py (port 5001, POST /calibrate). Comptes dans MongoDB.

## Documentation Swagger de l'API

Après le démarrage du backend, ouvre **http://localhost:5000/api/docs** pour accéder à
Swagger UI. La spécification OpenAPI JSON est disponible sur
**http://localhost:5000/api/openapi.json**. Les routes protégées utilisent un jeton JWT :
appelle `/api/login`, copie la valeur `token`, puis clique sur **Authorize** dans Swagger
et saisis le jeton (sans ajouter le préfixe `Bearer`, Swagger le fait automatiquement).

## Installation (une seule fois, sur le Pi)
```bash
# MongoDB (Docker, image arm64, 64-bit OS requis)
docker compose up -d

# Backend
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Frontend (Node 18+ requis)
cd ../frontend && npm install && npm run build
```

## Lancement
```bash
# 1. Dans la session graphique du Pi (il ouvre des fenêtres OpenCV)
python color_receiver.py

# 2. Webapp
cd backend && source .venv/bin/activate
python app.py
```
Ouvre http://<ip-du-pi>:5000. Développement du front : `npm run dev` dans frontend/ (proxy vers :5000).

## Sélection et projection des salles N3

### Surbrillance et calibration manuelle

La salle N3 sélectionnée apparaît avec un contour doré renforcé sur le
projecteur, y compris lorsqu'elle n'a pas de température. Revenir à la vue
globale retire la surbrillance ; passer à N4 efface la sélection projetée.

Le bouton **Calibration** conserve la calibration et le tracking automatiques.
Une fois le marqueur projeté et les quatre repères physiques détectés, clique
sur **Ajuster manuellement le plan calibré** : le dernier alignement automatique
est copié puis figé, et le plan complet avec ses contours est affiché.
Les quatre points rouges encadrent uniquement le plan. Déplacer un point ne
change pas les trois autres coordonnées. Les positions des poignées ne sont
pas remplacées par la caméra ni par l'aperçu pendant l'édition.

La projection suit les mouvements en direct, comme dans `ProjoManuel.py`.
La fenêtre **Controle PC** permet également de déplacer directement les points.
Dans le panneau web, les flèches déplacent un point d'un pixel (dix avec Maj).
**Reprendre l'alignement automatique initial** annule les déplacements manuels
et retrouve le résultat automatique figé au début du réglage.
**Revenir au tracking automatique** reprend le suivi et les réglages automatiques.
Les coins croisés et les quadrilatères dégénérés sont refusés.

Quand le plan est aligné, clique sur **Enregistrer les réglages** : le plan et
les repères sont retirés automatiquement, et l'alignement corrigé est conservé
au prochain démarrage. Le plan réapparaît à l'ouverture du réglage manuel.
Les mouvements en direct ne sauvegardent pas le fichier à chaque fois.

Les réglages sont sauvegardés dans `projector-pi/.projection_calibration.json`
(fichier local exclu de Git). Le mode manuel est restauré au redémarrage ;
le mode automatique refait la détection ArUco et réutilise les corrections.
Après cette mise à jour, reconstruis le frontend et redémarre le backend et
le récepteur de projection.

Après connexion, le plan `plan_N3_Structure_modifie.svg` est cliquable (33 salles).
Calibre le projecteur puis sélectionne une salle sur le plan ou dans la liste.
La sélection est confirmée dans la webapp lorsque le Pi accepte la demande ;
elle reste visible dans la webapp. Le projecteur affiche les aplats de
température et la surbrillance de la sélection. Le tracking ArUco est actif
en mode automatique.
Pendant la calibration, les températures sont conservées pour le retour au tracking.

Conserve le dossier `shared/` sur le Pi : `plan-n3.json` contient les contours
extraits du SVG et leur recalage sur le JPG. Si les contours SVG changent,
actualise aussi ce catalogue. Le recalage initial utilise les limites du bâtiment
dans les deux fichiers ; son alignement physique doit être vérifié sur le Pi.
Pour ajuster les marges du JPG, lance le récepteur avec
`PLAN_IMAGE_BOUNDS='[0.04396, 0.20705, 0.96239, 0.83271]' python color_receiver.py`.
Ces quatre valeurs sont les coordonnées gauche, haut, droite et bas du bâtiment,
exprimées en fractions de la largeur et de la hauteur de l’image.

Vérification des contours et du recalage :
`projector-pi/.venv/bin/python -m unittest discover -s projector-pi -p 'test_*.py'`.

## Températures sur le plan

Depuis la racine du projet :
```bash
backend/.venv/bin/pip install -r backend/requirements.txt
backend/.venv/bin/python backend/import_temperatures.py
cd frontend && npm run build
```
MongoDB doit être lancé (`docker compose up -d`). L'import utilise `MONGO_URI`
comme le backend, et la collection `calibration_app_pc.temperature_measurements`
par défaut. `MONGO_DB` permet de choisir une autre base explicitement. Backend,
import et lanceur Windows utilisent la même base, y compris lorsque le backend
est lancé directement avec Python.
Le fichier CSV/XLSX de `ressources/` est détecté automatiquement ; si plusieurs
fichiers existent, passez le chemin voulu en argument. Le XLSX fourni contient
une ligne CSV par cellule, format également pris en charge. Les valeurs vides,
non numériques et les dates invalides sont ignorées. L'index unique `(room,
timestamp)` conserve les mesures existantes et permet de relancer l'import sans doublons.

Pour importer les CSV mensuels sur Windows dans la base utilisée par `start-pc.ps1` :
```powershell
$env:MONGO_DB = 'calibration_app_pc'
Get-ChildItem 'C:\Axel\School\ESEO I3\makette\ressources' -Filter 'temperature_2026-*.csv' |
    Sort-Object Name | ForEach-Object {
        & backend/.venv/Scripts/python.exe backend/import_temperatures.py $_.FullName
        if ($LASTEXITCODE -ne 0) { throw 'Import interrompu' }
    }
```
Le lecteur accepte les CSV séparés par des points-virgules et les colonnes
supplémentaires des exports mensuels. Les données restent dans leurs fichiers
source ; seules les mesures valides sont ajoutées à MongoDB. Redémarrer le
serveur après l'import pour rafraîchir les journées mises en cache.

La projection N3 affiche deux lignes agrandies entre les ArUco du haut : étage,
date et heure, puis la moyenne de l'étage à cet instant en vue globale, ou
uniquement la température instantanée lorsqu'une salle est sélectionnée.
L'échelle commune de 12 à 30 °C apparaît entre les ArUco du bas. Ces éléments
suivent la calibration. La projection n'affiche pas de repère « Sans mesure ».
Sur le site, ce repère est un échantillon rectangulaire hachuré, sans interaction.
En vue globale, le graphique montre la moyenne des salles à chaque horaire de
la journée. Seules les salles disposant d'une valeur contribuent à chaque point ;
les segments incluant une interpolation sont signalés en orange.

Tous les appareils connectés utilisent une vue commune via `/api/view-state` :
date, étage, horaire, salle, heatmap, interpolation et lecture sont synchronisés.
Le serveur pilote seul la lecture et la projection ; les pages récupèrent les
changements toutes les 500 ms. Un nouvel appareil reprend la vue existante.
La vue est conservée dans `viewer_state` dans la base du backend. Actualiser
une fois les pages déjà ouvertes après cette mise à jour pour activer la
synchronisation ; les anciennes commandes de projection sont ignorées lorsque
la vue commune est active.

Les dates sans fuseau sont interprétées en `Europe/Paris` (modifiable avec
`TEMPERATURE_TIMEZONE` lors de l'import), puis stockées en UTC. Le slider
présente la période des mesures importées et affiche l'heure de Paris.
`GET /api/temperatures/range` renvoie les bornes ;
`GET /api/temperatures?timestamp=2026-01-01T00:00:00%2B01:00` renvoie une
mesure par code de salle, la plus proche à ±10 minutes (la plus ancienne en
cas d'égalité). Les deux endpoints utilisent la session JWT existante.
Les codes sont associés exactement : les salles N3 sans mesure `03-…`
affichent `-- °C`. La projection conserve ses identifiants internes.

Vérifications :
```bash
backend/.venv/bin/python -m unittest discover -s backend -p 'test_*.py'
projector-pi/.venv/bin/python -m unittest discover -s projector-pi -p 'test_*.py'
cd frontend && npm run build
```
Le fichier fourni contient 2 944 mesures valides ; 111 lignes sont ignorées
(valeurs absentes ou lignes tronquées). Les données couvrent 24 des 33 codes N3.

## Couleurs des températures sur le projecteur

Le slider envoie automatiquement les mesures des salles N3 au récepteur Pi via
`POST /api/project-temperatures` (session JWT), puis `POST /project-temperatures`
sur le port 5001. Une absence de mesure efface la couleur de la salle.
L'échelle commune au web et au Pi est dans `shared/temperature-scale.json` :
12 °C bleu, 15 °C cyan, 18 °C turquoise, 21 °C vert, 24 °C jaune,
27 °C orange et 30 °C rouge, interpolation continue et saturation aux extrêmes.
Sur le projecteur, les salles sans mesure restent noires sauf la salle sélectionnée.
Les aplats colorés et la surbrillance sont projetés,
sur fond noir, sans plan JPG. La sélection ajoute un contour doré avec une bordure
sombre contrastée et conserve la couleur thermique au centre de la salle ;
les contours et repères peuvent être activés pendant le réglage. Le plan web
conserve le blanc pour les salles sans mesure. Le marqueur de calibration
ArUco et sa marge blanche restent affichés pendant la calibration.

Après mise à jour, reconstruisez le frontend et redémarrez **les deux** scripts :
`backend/app.py` et `projector-pi/color_receiver.py` (ce dernier dans la session
graphique du Pi). Conservez tout le dossier `shared/` sur le Pi.

Le backend démarre sans définir `JWT_SECRET` : au premier lancement, il génère
une clé dans `backend/.jwt_secret` (permissions 600, exclue de Git), puis la
réutilise aux redémarrages. Une variable `JWT_SECRET` explicitement définie
reste prioritaire. Gardez ce fichier pour conserver les sessions ; si la clé
change, reconnectez-vous (les comptes MongoDB restent inchangés).


Pour importer le fichier complet ajouté dans `ressources/` (les deux sources
sont désormais présentes), depuis la racine :
```bash
backend/.venv/bin/python backend/import_temperatures.py ressources/temperature_clean.xlsx
```
Import du fichier complet : 1 006 896 nouvelles mesures, 2 944 déjà présentes,
38 735 lignes ignorées. La collection contient 1 009 840 mesures, couvrant du
1er janvier 2026 à 00:00 au 30 janvier 2026 à 00:10, heure de Paris.
Le fichier conserve des trous dans les mesures : le slider reste continu et
les salles sans mesure dans la tolérance affichent `-- °C`.

Le plan propose un sélecteur de jour limité aux bornes des données et un slider
journalier de 00:00 à 23:59 (heure de Paris). La lecture automatique avance de
15 minutes toutes les demi-secondes, puis s'arrête à 23:59. Pause conserve l'heure ;
« Revenir à 00:00 » réinitialise la journée. Changer de jour remet l'heure à
00:00 ; déplacer le slider interrompt la lecture. Les journées partielles et
les trous dans les données affichent les salles sans mesure en blanc.

L'échelle est commune au web et au Pi : bleu à 12 °C, vert à 21 °C
et rouge à 30 °C, avec un dégradé continu entre ces valeurs.
Les aplats projetés sont réduits à 65 % de la surface de chaque salle autour
de son centre ; le recalage ArUco reste fixe.
La sélection se fait sur le plan ; le panneau affiche le nom, le code puis la
température de la salle à l'heure choisie.

## Interface reprise de la branche Axel

L'interface React reprend les plans N3/N4, la vue globale, la recherche et les
détails des salles, les statistiques, le graphique journalier et son historique,
ainsi que l'option « Combler les trous » et la lecture en boucle (15 minutes
chaque 500 ms). Les estimations sont marquées `≈` et en pointillés orange ;
l'interpolation est limitée aux trous bornés par deux mesures distantes d'au plus
180 minutes. Les observations importées ne sont pas modifiées.

Les routes supplémentaires `GET /api/plans`, `/api/days/<floor>` et
`/api/day/<floor>/<day>` lisent la collection MongoDB existante, avec les dates
BSON et les codes `room`, en heure de Paris. Les journées sont mises en cache
(maximum 16) ; redémarrez le backend après un nouvel import.
Les routes d'authentification, de calibration et de projection sont conservées.
Le frontend transmet directement les codes N3 à `/api/project-temperatures`
et les identifiants du catalogue à `/api/project-room`, avec des commandes
sérialisées qui gardent uniquement le dernier état en attente.
L'échelle garde le vert à 21 °C. Le Pi affiche les aplats à 65 %
sur fond noir avec la surbrillance de sélection ; une salle sans mesure reste
noire sauf si elle est sélectionnée. **N4 est consultable uniquement**, car le projecteur existant
reste configuré pour N3. Passer à N4 efface couleurs et sélection N3 ; aucun
identifiant N4 n'est envoyé au projecteur. L'indication « Récepteur Pi joignable »
confirme la dernière commande acceptée, sans prétendre mesurer le tracking ArUco.

Après mise à jour : reconstruisez le frontend (`cd frontend && npm run build`),
redémarrez `backend/app.py`, puis rechargez la page. Redémarrez également `projector-pi/color_receiver.py` pour appliquer les
changements de projection. Tests frontend : `node --test frontend/tests/heatmap.test.js`.


## Développement de l’interface

MongoDB et le backend doivent déjà tourner. Dans un terminal supplémentaire, depuis la racine :

```bash
npm --prefix frontend run dev
```

Sous Windows :

```powershell
npm.cmd --prefix frontend run dev
```

Ouvrez l’adresse indiquée par Vite (habituellement `http://localhost:5173`). Les requêtes `/api` sont transférées au backend sur le port 5000.

Après une modification, reconstruisez l’interface avec `npm --prefix frontend run build` (`npm.cmd` sous Windows) pour la consulter via Flask sur le port 5000. Après une mise à jour du code Python, redémarrez le backend et, si concerné, le récepteur Pi. Après un nouvel import, redémarrez le backend pour vider le cache des journées.

## Consultation des badgeages

Après le lancement habituel, connecte-toi puis clique sur **Badgeages** en haut de l'écran.
Choisis le niveau N3 ou N4, une journée de mars et éventuellement une heure.
Les données sont agrégées par salle et par heure ; aucun badgeage individuel n'est affiché.
Si `ressources/badgeages.csv` n'est pas présent, le backend tente de le récupérer automatiquement depuis la branche publique du dépôt GitHub lors du premier accès aux badgeages. Une connexion Internet est donc nécessaire à ce premier chargement.


## Prédiction des températures (CSV + API météo)

Une page **Prédictions IA** est disponible depuis la barre supérieure après connexion.
Elle expose aussi les routes protégées suivantes :

- `GET /api/predictions/temperatures?days=7` : prévisions par salle sur 1 à 14 jours, avec températures météo extérieure.
- `GET /api/predictions/temperatures?room=CODE_SALLE&days=7` : prévisions d'une salle.
- `GET /api/predictions/missing-days` : jours absents entre deux dates observées, estimés par interpolation.
- `GET /api/predictions/missing-days?room=CODE_SALLE` : même analyse pour une salle.

Le modèle lit les mesures depuis `ressources/temperature_clean.xlsx` (le fichier fourni, dont les lignes contiennent le CSV d'origine) et utilise l'API Open-Meteo : archive météo pour entraîner le modèle sur les périodes historiques, prévisions météo pour les dates futures. Le modèle Random Forest est utilisé lorsque suffisamment de données météo/historiques se recouvrent ; sinon une moyenne récente de repli est renvoyée. Les jours interpolés et les prédictions sont étiquetés comme estimations, jamais comme mesures brutes.

### Configuration

Les coordonnées par défaut correspondent à Angers et peuvent être changées avec :

```bash
WEATHER_LATITUDE=47.4784
WEATHER_LONGITUDE=-0.5632
```

Pour utiliser un CSV plutôt que le fichier XLSX inclus, définissez `TEMPERATURE_CSV=/chemin/vers/temperature.csv`. Il doit contenir les colonnes `timestamp,value,room,floor,zone`. Le backend doit avoir accès à Internet pour appeler `https://api.open-meteo.com` et `https://archive-api.open-meteo.com`.

Après mise à jour, installez les dépendances backend depuis `backend/requirements.txt`, puis reconstruisez le frontend :

```bash
cd frontend && npm install && npm run build
```

Le premier appel peut être plus lent, car le modèle prépare l'historique et récupère l'archive météo. Le cache mémoire garde le parsing du fichier source en mémoire jusqu'au redémarrage du backend.
