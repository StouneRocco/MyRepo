# Maquette thermique ESEO — PC, tablette et projection

Application React/Flask de consultation des températures et de projection sur la maquette N3. La caméra assure le recalage ArUco ; une correction manuelle permet d'ajuster indépendamment les quatre coins du plan. N3 et N4 sont consultables sur le site ; la projection physique reste N3.

## Démarrer sur Windows

Prérequis : **Python 3.11**, **Node.js 22.19 ou plus récent**, MongoDB local ou Docker Desktop avec conteneurs Linux. Une session Windows graphique est nécessaire pour les fenêtres OpenCV.

Toutes les commandes ci-dessous partent de la racine du projet, le dossier contenant `start-pc.ps1`. Utiliser la copie qui contient les dernières corrections : plusieurs dossiers `makette` ne se mettent pas à jour ensemble.

### Première installation

```powershell
py -3.11 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt -r projector-pi/requirements.txt
npm.cmd --prefix frontend ci
```

Si MongoDB n'est pas déjà lancé comme service Windows :

```powershell
docker compose up -d mongo
```

**Si Docker indique que le port 27017 est déjà utilisé**, ne pas démarrer un
deuxième MongoDB : le service Windows peut déjà fonctionner. Lancer directement
`start-pc.ps1` ; il réutilise l'instance disponible. Un contrôle sans modification
des données est possible avec `backend/.venv/Scripts/python.exe backend/healthcheck.py`
(code de sortie 0 : MongoDB répond). Ne pas supprimer de volume pour résoudre ce conflit.

Les comptes et les mesures sont dans `calibration_app_pc` par défaut. `MONGO_URI` et `MONGO_DB` permettent de choisir un autre serveur ou une autre base ; les définir de la même façon pour l'import et le backend. Les mesures, comptes, certificats et réglages locaux ne sont pas transférés par Git.

### Lancement habituel

```powershell
powershell -ExecutionPolicy Bypass -File .\start-pc.ps1 -Projector
```

Sans projection :

```powershell
powershell -ExecutionPolicy Bypass -File .\start-pc.ps1
```

Le lanceur affiche le dossier et le commit utilisés, attend MongoDB et reconstruit le frontend à chaque lancement. Il refuse un deuxième serveur sur le port 5000. Avec `-Projector`, il démarre le récepteur si le port 5001 est libre ; une instance préexistante est conservée.

Ouvrir **l'adresse affichée par le backend** : HTTPS si les certificats locaux sont configurés, sinon `http://localhost:5000/`. Le site utilise le port 5000, le récepteur le port local 5001 et la distribution du certificat public le port 5080.

### Mise à jour et relance

1. Arrêter l'ancien backend avec **Ctrl+C** ; fermer le récepteur avec **q** dans une de ses fenêtres OpenCV.
2. Se placer dans le dossier contenant le code mis à jour.
3. Mettre à jour les dépendances puis relancer :

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt -r projector-pi/requirements.txt
powershell -ExecutionPolicy Bypass -File .\start-pc.ps1 -Projector -Update
```

`-Update` exécute `npm ci` ; les dépendances Python se mettent à jour avec la commande précédente. Backend et récepteur doivent utiliser la même version, notamment pour le diagnostic `/health`.

**Ctrl+C** dans le lanceur arrête aussi le récepteur qu'il a créé. Un récepteur qui était déjà lancé doit être fermé séparément. Les journaux de projection sont dans `.runtime/projector.log` et `.runtime/projector-error.log`.

## Caméra et projecteur

Dans les paramètres d'affichage Windows, choisir **Étendre ces affichages** et configurer le projecteur en **1920 × 1080**. Par défaut : caméra index 0, projecteur à la position écran `(1920, 0)`.

Exemple avec une seconde caméra et un écran principal de 2560 pixels :

```powershell
powershell -ExecutionPolicy Bypass -File .\start-pc.ps1 -Projector -CameraIndex 1 -ProjectorX 2560 -ProjectorY 0
```

Les paramètres optiques `mtx` et `dist` du récepteur correspondent à la caméra Pi d'origine. Une autre caméra nécessite sa propre calibration optique ; le recalage ArUco ne remplace pas cette étape.

### Calibration

1. Ouvrir **Calibration**, relancer la calibration automatique et laisser la caméra détecter le marqueur projeté ID 0, puis les quatre repères physiques IDs 1 à 4.
2. Choisir **Ajuster manuellement le plan calibré** pour figer l'alignement obtenu. Le plan et ses quatre poignées apparaissent ; déplacer un coin conserve les coordonnées des trois autres.
3. Ajuster depuis le panneau web ou la fenêtre **Controle PC**. Dans le panneau, les flèches déplacent un coin d'un pixel, ou dix avec Maj.
4. **Enregistrer les réglages** conserve l'alignement au redémarrage et retire le plan et les repères. Fermer le panneau retire aussi les guides, mais ne sauvegarde pas les mouvements temporaires.

**Reprendre l'alignement automatique initial** annule les déplacements manuels. **Revenir au tracking automatique** reprend le suivi et sauvegarde ce mode. Si un autre appareil modifie la calibration, le panneau devenu ancien reçoit un conflit : rouvrir les réglages avant de poursuivre.

La calibration locale est dans `projector-pi/.projection_calibration.json`, exclu de Git. Le tracking utilise une pose complète issue d'une même image ; si un repère manque, la dernière pose cohérente est conservée. La précision réelle doit être vérifiée sur la maquette.

Conserver le dossier `shared/` avec le récepteur : il contient le catalogue N3 et l'échelle thermique. Si la géométrie du plan change, actualiser aussi ce catalogue. `PLAN_IMAGE_BOUNDS` permet de modifier les limites du bâtiment dans le JPG, par exemple `[0.04396, 0.20705, 0.96239, 0.83271]`.

## Tablette, réseau local et HTTPS

PC et tablette doivent être sur le même réseau, avec une connexion entre appareils autorisée. Utiliser l'adresse IPv4 du PC, jamais `localhost` sur la tablette. Autoriser le port 5000 sur le profil réseau approprié du pare-feu Windows ; le port 5080 sert uniquement à installer le certificat public. Ne pas exposer MongoDB ou le récepteur au réseau.

Pour générer le certificat, remplacer l'adresse d'exemple par l'IPv4 actuelle du PC :

```powershell
powershell -ExecutionPolicy Bypass -File .\setup-https.ps1 -IpAddress 10.21.23.100
powershell -ExecutionPolicy Bypass -File .\start-pc.ps1 -Projector
```

Le backend détecte automatiquement les certificats dans `backend/.tls`, y compris lors d'un lancement direct avec `python backend/app.py`. `TLS_CERT_FILE` et `TLS_KEY_FILE` permettent d'utiliser d'autres fichiers, en définissant les deux ensemble.

Sur Android :

1. Ouvrir `http://10.21.23.100:5080/` et télécharger **maquette-ca.crt**.
2. Installer ce fichier comme **certificat CA** dans les paramètres Android. Comparer son empreinte SHA-256 avec celle affichée sur le PC.
3. Rouvrir Chrome sur `https://10.21.23.100:5000/`. Le certificat doit être reconnu sans avertissement.
4. Choisir **Installer l'application** dans Chrome ou avec le bouton proposé, puis utiliser la nouvelle icône HTTPS.

L'installation PWA utilise `standalone` pour ouvrir sans barre d'adresse. Un simple raccourci HTTP ne garantit pas ce comportement ; le bouton **Plein écran** reste disponible si le navigateur le permet.

Pour le PC, importer le même certificat public dans les autorités de confiance de l'utilisateur si nécessaire. `setup-https.ps1` ne fait pas cette installation automatiquement. Ne partager aucune clé privée, notamment `rootCA-key.pem` ou `server-key.pem`.

Si l'IP change, régénérer le certificat avec la nouvelle adresse puis redémarrer. L'autorité existante est conservée ; son certificat n'a pas à être réinstallé tant qu'elle reste identique. Une réservation DHCP facilite l'utilisation d'une adresse stable.

## Données et affichage

Le calendrier donne accès à janvier–juin lorsque les six CSV mensuels ont été importés. L'import historique `temperature_clean.xlsx` ne contient qu'une partie de janvier : le copier seul ne donne pas les six mois.

### Import et contrôle

```powershell
backend/.venv/Scripts/python.exe backend/import_temperatures.py ressources/fichier.csv --dry-run
backend/.venv/Scripts/python.exe backend/import_temperatures.py ressources/fichier.csv
```

Remplacer `ressources/fichier.csv` par le chemin réel. Le mode `--dry-run` analyse sans se connecter à MongoDB. Les rapports dans `.runtime/imports` contiennent l'empreinte SHA-256, la couverture mois/salle, les volumes et des exemples de numéros de lignes rejetées. `--report chemin.json` choisit un autre emplacement.

Pour les fichiers mensuels présents dans le dossier de données du PC :

```powershell
Get-ChildItem 'C:\Axel\School\ESEO I3\makette\ressources' -Filter 'temperature_2026-*.csv' |
    Sort-Object Name | ForEach-Object {
        & backend/.venv/Scripts/python.exe backend/import_temperatures.py $_.FullName
        if ($LASTEXITCODE -ne 0) { throw 'Import interrompu' }
    }
```

CSV virgule/point-virgule/tabulation et XLSX sont acceptés, avec les colonnes `timestamp`, `value`, `room`, `floor`, `zone`. Pour XLSX, la feuille active est utilisée ; `--sheet Nom` en choisit une autre. Le format historique CSV dans les cellules A est aussi accepté.

L'index unique `(room, timestamp)` empêche les doublons. Par défaut, une valeur déjà importée est conservée ; **`--replace-existing` remplace explicitement les valeurs existantes**. Faire une sauvegarde avant un import correctif. Les valeurs invalides/non finies sont rejetées.

Les dates sans offset sont interprétées en `Europe/Paris`, configurable par `TEMPERATURE_TIMEZONE` lors de l'import, puis stockées en UTC. Une heure locale inexistante ou ambiguë sans offset est rejetée.

Les caches expirent après trente secondes ; l'interface recharge périodiquement les données. Les nouveaux relevés deviennent visibles sans redémarrage, avec un délai pouvant atteindre environ une minute dans le site.

### Consultation et projection

- Vue globale : moyenne des salles disponibles à chaque horaire et courbe des moyennes sur la journée. La couverture indique combien de salles contribuent.
- Salle sélectionnée : température du créneau et courbe journalière ; les statistiques de salle portent sur la journée, celles de la vue globale sur l'horaire choisi.
- Un créneau dure cinq minutes et conserve sa dernière observation. **Combler les trous** interpole uniquement entre deux mesures espacées d'au plus 180 minutes ; `≈` et les segments orange indiquent les estimations. Les longues lacunes ne sont pas remplies.
- L'heure inexistante au passage à l'heure d'été n'est pas interpolée. Les deux occurrences de l'heure d'automne ne sont pas encore distinguées dans la grille.
- La lecture avance de 15 minutes toutes les 500 ms et boucle à minuit ; Pause conserve l'heure. La plage du curseur va de 00:00 à 23:55.

PC et tablette partagent date, étage, heure, sélection et options via `/api/view-state`. Les pages au premier plan se synchronisent toutes les 500 ms, plus lentement lorsqu'elles sont masquées. La lecture est pilotée par le serveur et reprend en pause après un redémarrage. Si plusieurs opérateurs commandent simultanément, la dernière commande reçue est appliquée.

Sur la projection N3, les informations entre les ArUco du haut sont l'étage, la date, l'heure et la température sélectionnée, ou la moyenne instantanée en vue globale. L'échelle est entre les deux ArUco du bas. La sélection a un contour doré renforcé ; le plan disparaît après calibration. Désactiver la heatmap conserve les chiffres du bandeau.

L'échelle commune dans `shared/temperature-scale.json` va de 12 °C bleu à 30 °C rouge, avec vert à 21 °C. Les salles sans mesure restent blanches sur le site et noires sur la projection, sauf la sélection. Les aplats projetés occupent 65 % de la surface des salles. Consulter N4 retire la sélection N3, mais le projecteur continue à présenter les températures **N3** à la date et l'heure partagées.

## Présence : intégration de la partie badgeages de `babas`

Le sélecteur **Donnée affichée** en haut de page propose **Températures** et
**Présence**, avec le mode actif mis en évidence. Il remplace le bloc de marque
et les anciens boutons de navigation isolés.
Les mêmes plans N3/N4, styles, comptes, droits et commandes de plein écran sont utilisés.

Choisir un étage et une journée, puis déplacer la **timeline de 00:00 à 23:00**,
par pas d'une heure. **Lire la journée**, **Pause** et **Recommencer** reprennent
le fonctionnement de la vue thermique ; la lecture avance d'une heure toutes
les 500 ms et boucle après 23 h. Cliquer une barre du graphique choisit aussi
son heure et interrompt la lecture. Changer de jour ou d'étage revient à 00 h.

Le plan et le nombre principal indiquent les badgeages pendant l'heure choisie.
La recherche de salle, la vue globale et l'historique journalier sont communs
aux deux présentations. Pour l'étage comme pour une salle, le panneau affiche
le total du jour, la moyenne sur les 24 heures et le pic horaire, ainsi que
la répartition horaire. **Revenir à la vue globale** retire la sélection.
L'option **Code et nom des salles** affiche les libellés sur le plan.

La source intégrée depuis `babas` est `ressources/badgeages.csv` et couvre mars
2026. Le lecteur accepte aussi d'autres mois présents dans ce fichier : il ne
limite pas artificiellement le calendrier à mars. Les colonnes requises sont
`DateHeure` et `Code salle` ; les codes sont rapprochés des plans existants.
Les salles des autres étages ne contribuent pas aux totaux N3/N4.
`BADGEAGES_FILE` permet de choisir un autre fichier local. Un remplacement du
CSV invalide son cache à la requête suivante ; recharger le module après remplacement.
Aucun téléchargement externe n'est nécessaire au lancement.

Les routes authentifiées de consultation sont
`GET /api/badgeages/days/<floor>` et `GET /api/badgeages/day/<floor>/<day>`.
Elles retournent uniquement des agrégats par salle et par heure.
**Un badgeage est un passage enregistré, pas une mesure de l'occupation ni un
compte de personnes uniques.** Un zéro signifie qu'aucun badgeage n'est enregistré
pour ce filtre.

Le mode **Températures / Présence**, la date, l'heure, la salle sélectionnée et
la lecture sont partagés entre appareils via `/api/view-state`. Le projecteur
N3 suit le mode actif : même palette bleu–cyan–vert–jaune–orange–rouge, en °C ou en badgeages
par heure. En présence, l'échelle commune à l'application et au projecteur est
fixée à **1–15 badgeages par salle et par heure** dans `shared/presence-scale.json`.
Les valeurs supérieures saturent la couleur maximale. Les salles à zéro ou sans
valeur ne sont pas colorées ; seul le contour de sélection reste visible.
Le nombre principal est le total de l'étage ou le comptage de la salle
sélectionnée. Une journée sans données efface les anciennes couleurs.
Le passage à la présence arrête la lecture et arrondit l'horaire à l'heure entière.
Si la date courante n'a pas de badgeages, la première journée disponible est choisie.
N4 reste consultable, la maquette physique représente toujours N3. La calibration
est conservée. Les lecteurs suivent la vue partagée ; les opérateurs la pilotent.
Les commandes de calibration automatique et manuelle sont disponibles dans les
deux vues, **Températures** et **Présence**, avec les mêmes réglages et droits.

## Comptes et droits

Les comptes existants restent opérateurs. Après création du premier compte, les inscriptions sont fermées. Pour les ouvrir temporairement, définir `$env:ALLOW_REGISTRATION = 'true'` avant de lancer le backend : les nouveaux comptes sont des lecteurs, sans commandes de projection.

Gestion locale :

```powershell
backend/.venv/Scripts/python.exe backend/manage_users.py nom --role operator
backend/.venv/Scripts/python.exe backend/manage_users.py nom --role viewer
backend/.venv/Scripts/python.exe backend/manage_users.py nom --revoke-sessions
backend/.venv/Scripts/python.exe backend/manage_users.py nom --password
backend/.venv/Scripts/python.exe backend/manage_users.py nom --disable
```

`--enable` réactive un compte. Les changements révoquent ses anciennes sessions ; le mot de passe est demandé sans être affiché. L'outil refuse de retirer le dernier opérateur actif. Les tentatives de connexion sont limitées.

La clé JWT est générée dans `backend/.jwt_secret`, exclue de Git. Conserver ce fichier pour conserver les sessions ; le remplacer les invalide sans supprimer les comptes. Une variable `JWT_SECRET` personnalisée doit contenir au moins 32 octets aléatoires.

## Sauvegarde et restauration

```powershell
New-Item -ItemType Directory -Force backups
backend/.venv/Scripts/python.exe backend/backup_data.py backup backups/maquette.json.gz
backend/.venv/Scripts/python.exe backend/backup_data.py restore backups/maquette.json.gz --database calibration_restore_test
```

Un export existant n'est pas écrasé. La restauration refuse la base active et toute base déjà remplie ; après une interruption, recommencer dans une nouvelle base vide. Arrêter commandes et imports pendant la sauvegarde : ce n'est pas un snapshot transactionnel.

L'export contient mesures, comptes avec mots de passe hachés et état partagé : protéger son accès. Sauvegarder séparément la calibration locale, la clé JWT et les certificats/clés TLS dans un emplacement protégé. Les dossiers `backups`, `.runtime` et `backend/.tls` sont exclus de Git.

## Dépannage

| Symptôme | Vérification |
|---|---|
| `start-pc.ps1` introuvable | Se placer à la racine ou utiliser le chemin absolu du script. |
| Port 5000 occupé | Arrêter l'ancien backend ; vérifier quelle copie du projet a été lancée. |
| Docker : port 27017 déjà utilisé | Utiliser MongoDB Windows déjà lancé et démarrer directement avec `start-pc.ps1`. |
| Projection indisponible | Lire les journaux, vérifier le récepteur sur 5001 puis utiliser **Réessayer la projection**. |
| Caméra indisponible | Vérifier index, branchement et application utilisant déjà la caméra. |
| Repères masqués | Dégager les quatre ArUco ; la dernière pose cohérente est conservée. |
| Écran projeté au mauvais endroit | Vérifier affichage étendu, résolution, `-ProjectorX` et `-ProjectorY`. |
| Seulement janvier | Vérifier l'import des six fichiers, la base choisie et leur rapport de couverture. |
| Site inaccessible sur tablette | Même réseau, IP actuelle, pare-feu et éventuelle isolation Wi-Fi entre appareils. |
| Erreur HTTPS | Utiliser HTTPS si activé, contrôler IP du certificat et confiance dans l'autorité locale. |
| Ancienne interface | Vérifier le dossier lancé puis recharger la page ; le lanceur reconstruit le frontend. |

Le diagnostic distingue récepteur joignable, caméra, calibration, visibilité des marqueurs et activité du rendu. Il ne prouve pas qu'une image sort physiquement du projecteur. Le pilote réessaie après panne ; le renvoi périodique restaure la vue après redémarrage du récepteur.

## Développement et tests

```powershell
backend/.venv/Scripts/python.exe -m unittest discover -s backend -p 'test_*.py'
backend/.venv/Scripts/python.exe -m unittest discover -s projector-pi -p 'test_*.py'
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
```

Pour le frontend en développement, lancer le backend puis `npm.cmd --prefix frontend run dev`. Vite affiche son adresse, généralement `http://localhost:5173`, et transfère `/api` au backend. Il détecte la configuration HTTPS locale ; `DEV_API_URL` choisit une cible explicite. Node doit reconnaître le CA : si nécessaire, définir `NODE_EXTRA_CA_CERTS` avec le chemin absolu de `backend/.tls/maquette-ca.crt` avant de lancer Vite. La vérification TLS reste activée.

La CI GitHub exécute les tests et la compilation. Validation locale des corrections : **92 tests réussis** et compilation réussie. Les tests matériels, tactiles et de stabilité prolongée restent distincts.

Le lancement actuel utilise **un seul processus backend**. Un déploiement WSGI à plusieurs workers nécessite encore de séparer le pilote ; importer `app:app` ne démarre pas le thread de projection.

### Raspberry Pi

Utiliser un système 64 bits et une session graphique. Installer MongoDB, Node 22.19+ et Python 3.11, puis depuis la racine :

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt -r projector-pi/requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
docker compose up -d mongo
```

Dans deux terminaux, lancer `backend/.venv/bin/python projector-pi/color_receiver.py` et `backend/.venv/bin/python backend/app.py`. La caméra Linux est à l'index 4 par défaut ; `CAMERA_INDEX`, `PROJECTOR_X` et `PROJECTOR_Y` permettent de choisir le matériel et sa position.

## Documentation interactive de l'API (Swagger)

La page **`/api/docs`** présente toutes les routes du backend et permet de les
tester. La spécification OpenAPI 3.0.3 est disponible à **`/api/openapi.json`**.
Ces adresses utilisent le même serveur HTTP/HTTPS que l'application.

1. Dans **Connexion**, ouvrir `POST /api/login`, cliquer **Try it out**, renseigner
   son identifiant/mot de passe puis **Execute**.
2. Le jeton de la réponse est appliqué automatiquement. On peut aussi le coller
   dans **Authorize**, sans le préfixe `Bearer`.
3. Tester les GET de consultation. Les POST protégés nécessitent un compte
   `operator` ou `admin` et exécutent réellement les commandes demandées.

Swagger documente températures, présences, vue partagée, calibration et projection.
Les jetons de Swagger ne sont pas persistés après rechargement de la page.

Les fichiers officiels Swagger UI sont installés via npm puis copiés dans
`frontend/dist/swagger/` lors de `npm run build` : **aucun CDN ni connexion
Internet n'est nécessaire à l'utilisation**. Après un pull : `npm ci` puis
`npm run build` dans `frontend`, ou `start-pc.ps1 -Update`. Le proxy `/api`
permet aussi de consulter la page depuis le serveur de développement Vite.

Le contrat `backend/openapi.json` est validé automatiquement et ses routes sont
comparées aux routes Flask dans les tests, pour détecter les oublis.

## Audit et limites restantes

Voir [l'audit initial](AUDIT-2026-10-20.md) et [le suivi des corrections](CORRECTIONS-AUDIT.md). Les principaux chantiers restants concernent les profils optiques, le déploiement permanent, la gestion des conflits entre opérateurs, la double heure d'automne et les validations physiques/accessibilité. La projection N4 n'est pas implémentée.

### Consommation électrique (BOS)

L’onglet Électricité lit en lecture seule la base SQLite produite par le projet BOS. Configurez le chemin absolu dans la variable d’environnement `BOS_DB_PATH`, ou inscrivez-le seul dans `.runtime/bos-db-path.txt` (fichier local non suivi par Git). À défaut, l’application cherche `ressources/bos.db`. La base doit contenir le référentiel et les mesures électriques importés par BOS. Redémarrez le backend après modification de la configuration.

La heatmap estime la consommation horaire de chaque salle en ajoutant les mesures dédiées et une part égale de chaque départ partagé entre toutes ses salles, y compris celles hors du plan affiché. Cette hypothèse ne reflète pas forcément les usages réels. Une salle reste sans valeur si un compteur relié manque pour cette heure. La projection N3 reprend ces estimations. Les départs et leurs mesures restent visibles dans le détail du bâtiment. L’échelle commune va de 0 à 0,5 kWh par heure (les valeurs supérieures sont saturées). La somme utilise le statut de comptabilisation de BOS : les compteurs parents et doublons exclus ne sont pas additionnés, et les départs partagés sont répartis à parts égales uniquement dans la heatmap estimée. Une journée sans mesure est affichée comme non mesurée. Ce sous-comptage n’est pas la consommation totale facturée.
