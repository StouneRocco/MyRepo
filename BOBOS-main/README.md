# BOBOS — Copilote d'optimisation des espaces

Application web de Facility Management pour le Campus Dijon.  
Le projet croise les données BIM/IFC et IoT, détecte les consommations pendant les périodes sans présence et utilise un LLM pour générer des recommandations d'actions.

> **Objectif de ce README :** permettre à une personne qui ouvre le projet dans VS Code de lancer l'application web correctement, avec la base de données, l'interface et le LLM.

---

## 1. Prérequis

Le projet est prévu pour **Windows + VS Code + PowerShell**.

Installer au minimum :

- **Python 3.11 ou 3.12**
- **Git**
- **VS Code**
- **Ollama** si vous voulez utiliser le LLM localement

Vérifier Python et Git dans le terminal VS Code :

```powershell
py --version
git --version
```

Python doit être en version 3.11 ou 3.12.

---

## 2. Récupérer le projet

Si le projet n'est pas encore présent sur le PC :

```powershell
git clone https://github.com/StouneRocco/MyRepo.git
cd MyRepo\BOBOS-main
```

Si le dépôt est déjà cloné :

```powershell
cd chemin\vers\MyRepo\BOBOS-main
git pull
```

Vérifier que vous êtes bien dans le dossier contenant notamment :

```
Backend/
requirements.txt
start.ps1
.env.example
```

---

## 3. Créer l'environnement Python

### Méthode recommandée

Dans le terminal PowerShell de VS Code :

```powershell
py -3.11 -m venv .runtime
```

Activer l'environnement :

```powershell
.\.runtime\Scripts\Activate.ps1
```

Si PowerShell refuse l'activation à cause de la politique d'exécution :

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Puis :

```powershell
.\.runtime\Scripts\Activate.ps1
```

Vérifier :

```powershell
python --version
```

---

## 4. Installer les dépendances

Toujours dans le dossier `BOBOS-main` :

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Les principales dépendances sont :

- FastAPI
- Uvicorn
- Pandas
- NumPy
- HTTPX
- python-multipart

---

## 5. Configurer l'environnement

Créer le fichier `.env` à partir du modèle :

```powershell
Copy-Item .env.example .env
```

Le fichier `.env` doit rester local et **ne doit jamais être envoyé sur GitHub**.

---

# 6. LLM LOCAL AVEC OLLAMA — RECOMMANDÉ POUR LA DÉMO

Le projet sait utiliser Ollama directement depuis le backend.

Avantage : **aucune clé API n'est nécessaire** et le LLM tourne localement sur le PC.

## 6.1 Vérifier Ollama

Dans un nouveau terminal VS Code :

```powershell
ollama --version
```

Si la commande n'existe pas, installer Ollama avant de continuer.

## 6.2 Télécharger le modèle

Le projet est configuré par défaut avec :

```text
llama3.2:latest
```

Télécharger le modèle :

```powershell
ollama pull llama3.2
```

Vérifier qu'il est présent :

```powershell
ollama list
```

## 6.3 Démarrer Ollama

Si Ollama n'est pas déjà lancé :

```powershell
ollama serve
```

**Laisser ce terminal ouvert.**

Dans un deuxième terminal VS Code, vérifier que le modèle répond :

```powershell
ollama run llama3.2
```

Tester avec une question simple, puis quitter le modèle avec :

```text
/bye
```

> Si Ollama est déjà lancé par Windows, `ollama serve` peut indiquer que le port est déjà utilisé. Ce n'est pas forcément une erreur : Ollama est probablement déjà actif.

---

## 7. Configurer BOBOS pour utiliser Ollama

Dans `.env`, mettre :

```dotenv
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:latest
LLM_TIMEOUT_SECONDS=180

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o

ENERGY_PRICE_EUR_KWH=0.20
AREA_PER_PERSON_M2=4
```

Avec cette configuration :

- le frontend appelle le backend ;
- le backend appelle Ollama ;
- Ollama génère les recommandations ;
- le backend valide la réponse du LLM ;
- aucune commande réelle n'est envoyée à un équipement ;
- les actions sont uniquement **simulées**.

---

# 8. Préparer les données

Le backend utilise une base SQLite générée à partir des données du projet.

Le script de démarrage sait automatiquement créer cette base si elle n'existe pas.

### Lancement automatique

```powershell
.\start.ps1
```

Le script :

1. vérifie/crée `.runtime` ;
2. installe les dépendances si nécessaire ;
3. lance l'ETL si `Backend/bos.db` n'existe pas ;
4. crée/reconstruit les données nécessaires ;
5. démarre le serveur FastAPI.

> **Important :** les données sources nécessaires au projet doivent être présentes dans le dossier `Data/`. Si ce dossier n'est pas présent sur votre copie, l'import ETL ne pourra pas fonctionner correctement.

---

# 9. LANCER L'APPLICATION WEB

## Option A — la plus simple

Depuis :

```text
MyRepo/BOBOS-main
```

lancer :

```powershell
.\start.ps1
```

Vous devriez voir un message similaire à :

```text
Copilote : http://127.0.0.1:8000
API : http://127.0.0.1:8000/docs
```

Ouvrir ensuite dans le navigateur :

```text
http://127.0.0.1:8000
```

La page web est servie directement par FastAPI.

---

# 10. Vérifier que le backend fonctionne

Dans un deuxième terminal VS Code :

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/health
```

Vous devez obtenir une réponse indiquant notamment :

```json
{
  "status": "ok"
}
```

Vous pouvez également ouvrir :

```text
http://127.0.0.1:8000/docs
```

Cette page affiche la documentation interactive de l'API FastAPI.

---

# 11. Vérifier que le LLM est connecté

Ouvrir :

```text
http://127.0.0.1:8000/api/llm/status
```

Avec Ollama correctement configuré, le résultat doit indiquer :

```json
{
  "provider": "ollama",
  "connected": true
}
```

Le modèle installé doit également apparaître dans la liste des modèles disponibles.

---

# 12. Tester les recommandations LLM

Une fois l'application démarrée :

```text
http://127.0.0.1:8000
```

Dans l'interface :

1. ouvrir le tableau de bord ;
2. afficher les anomalies ;
3. cliquer sur **Générer les recommandations** ;
4. vérifier que la source indique Ollama ;
5. consulter les preuves utilisées ;
6. appliquer une action si nécessaire.

La commande d'action est **simulée**.

Aucun équipement réel n'est piloté par cette version du projet.

---

# 13. Commandes utiles pour la démo

## Santé du serveur

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/health
```

## Statut du LLM

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/llm/status
```

## Métadonnées

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/metadata
```

## Anomalies brutes

```powershell
Invoke-WebRequest "http://127.0.0.1:8000/api/insights/raw"
```

## Recommandations intelligentes

```powershell
Invoke-WebRequest "http://127.0.0.1:8000/api/insights/smart"
```

## Recommandations avec une date précise

Exemple :

```powershell
Invoke-WebRequest "http://127.0.0.1:8000/api/insights/smart?from=2026-01-12&to=2026-01-12"
```

## Documentation API

```text
http://127.0.0.1:8000/docs
```

---

# 14. Utiliser un autre modèle Ollama

Lister les modèles installés :

```powershell
ollama list
```

Télécharger un autre modèle :

```powershell
ollama pull NOM_DU_MODELE
```

Puis modifier `.env` :

```dotenv
LLM_PROVIDER=ollama
OLLAMA_MODEL=NOM_DU_MODELE
```

Redémarrer ensuite BOBOS :

1. arrêter FastAPI avec `CTRL+C` ;
2. relancer :

```powershell
.\start.ps1
```

Le modèle installé doit apparaître dans le sélecteur du copilote.

---

# 15. Utiliser OpenAI à la place d'Ollama

Une autre possibilité est d'utiliser l'API OpenAI.

Dans `.env` :

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=VOTRE_CLE_API
OPENAI_MODEL=gpt-4o

OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:latest

LLM_TIMEOUT_SECONDS=180
ENERGY_PRICE_EUR_KWH=0.20
AREA_PER_PERSON_M2=4
```

Puis redémarrer le serveur :

```powershell
CTRL+C
.\start.ps1
```

**Ne jamais mettre la clé API dans `Backend/static/` ou dans le JavaScript frontend.**

---

# 16. Mode automatique du LLM

Il existe également :

```dotenv
LLM_PROVIDER=auto
```

Dans ce mode, l'application choisit automatiquement un fournisseur selon la configuration disponible.

Pour une soutenance, il est cependant préférable d'utiliser explicitement :

```dotenv
LLM_PROVIDER=ollama
```

si vous voulez une démonstration entièrement locale.

---

# 17. Réimporter les données

Si les données sources ont changé et qu'il faut reconstruire la base :

Arrêter le serveur :

```text
CTRL+C
```

Puis :

```powershell
.\start.ps1 -ImportData
```

Cela relance l'ETL avant de redémarrer le serveur.

**Ne pas lancer deux imports simultanément.**

---

# 18. Lancement manuel sans `start.ps1`

Si le script PowerShell pose problème, lancer chaque étape manuellement.

Créer le venv :

```powershell
py -3.11 -m venv .runtime
```

Installer les dépendances :

```powershell
.\.runtime\Scripts\python.exe -m pip install -r requirements.txt
```

Importer les données :

```powershell
.\.runtime\Scripts\python.exe -m Backend.etl
```

Démarrer FastAPI :

```powershell
.\.runtime\Scripts\python.exe -m uvicorn Backend.app:app --host 127.0.0.1 --port 8000
```

Puis ouvrir :

```text
http://127.0.0.1:8000
```

---

# 19. Tests

Lancer les tests Python :

```powershell
.\.runtime\Scripts\python.exe -m unittest discover -s tests -v
```

Vérifier la syntaxe JavaScript :

```powershell
node --check Backend/static/app.js
```

---

# 20. Architecture du projet

```
BOBOS-main/
│
├── Backend/
│   ├── app.py              # API FastAPI + serveur web
│   ├── config.py           # configuration et variables .env
│   ├── etl.py              # import et préparation des données
│   ├── bim.py              # traitement IFC / surfaces
│   ├── dashboard.py        # données du tableau de bord
│   ├── insights.py         # détection des anomalies
│   ├── smart.py            # LLM + recommandations + validation
│   ├── db.py               # connexion SQLite
│   ├── sql/                # requêtes SQL
│   └── static/
│       ├── index.html      # interface web
│       ├── app.js          # logique frontend
│       └── style.css       # style frontend
│
├── Data/                   # données locales nécessaires à l'ETL
├── tests/                  # tests
├── exports/                # exports BIM
├── requirements.txt
├── .env.example
├── .gitignore
├── start.ps1
└── README.md
```

Il n'y a pas besoin de lancer un serveur frontend séparé : **FastAPI sert directement l'interface située dans `Backend/static/`.**

---

# 21. Flux complet de l'application

```
Navigateur
    │
    ▼
FastAPI : 127.0.0.1:8000
    │
    ├── Frontend : Backend/static/
    │
    ├── API Dashboard
    │
    ├── API Insights
    │
    └── API Smart
             │
             ▼
        Backend smart.py
             │
             ├── Ollama local
             │       └── llama3.2
             │
             └── ou OpenAI
                     │
                     ▼
              Recommandations JSON
                     │
                     ▼
             Validation backend
                     │
                     ▼
              Interface web
```

Le LLM ne contrôle donc pas directement l'application.  
Il propose des actions dans un format structuré, puis le backend valide les preuves, les types de commandes et les références avant de les afficher.

---

# 22. Ce que fait réellement le bouton « Appliquer »

Les commandes sont **simulées**.

Une action appliquée est enregistrée dans SQLite, mais aucun équipement réel n'est commandé.

Le backend retourne notamment :

```text
Commande simulée et enregistrée.
Aucun équipement réel modifié.
```

Cela permet de démontrer le workflow sans connexion BACnet, MQTT ou automate.

---

# 23. Dépannage

## « python n'est pas reconnu »

Essayer :

```powershell
py --version
```

Si `py` fonctionne, utiliser :

```powershell
py -3.11 -m venv .runtime
```

---

## « l'application affiche Base absente »

Lancer :

```powershell
.\.runtime\Scripts\python.exe -m Backend.etl
```

Puis :

```powershell
.\start.ps1
```

Si l'ETL échoue, vérifier que le dossier `Data/` contient bien les données nécessaires.

---

## « Ollama inaccessible »

Vérifier :

```powershell
ollama list
```

Puis, si nécessaire :

```powershell
ollama serve
```

Tester ensuite :

```powershell
Invoke-WebRequest http://127.0.0.1:11434/api/tags
```

Enfin vérifier :

```text
http://127.0.0.1:8000/api/llm/status
```

---

## « le modèle n'apparaît pas »

Vérifier :

```powershell
ollama list
```

Puis télécharger le modèle :

```powershell
ollama pull llama3.2
```

Et vérifier dans `.env` :

```dotenv
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2:latest
```

Redémarrer BOBOS.

---

## « le port 8000 est déjà utilisé »

Trouver le processus :

```powershell
netstat -ano | findstr :8000
```

Puis arrêter le processus concerné si nécessaire :

```powershell
taskkill /PID NUMERO_DU_PID /F
```

Relancer :

```powershell
.\start.ps1
```

---

# 24. Démarrage express — pour une soutenance

Si tout est déjà installé :

### Terminal 1 — Ollama

```powershell
ollama serve
```

### Terminal 2 — BOBOS

```powershell
cd chemin\vers\MyRepo\BOBOS-main
.\.runtime\Scripts\Activate.ps1
.\start.ps1
```

### Navigateur

```text
http://127.0.0.1:8000
```

### Vérification LLM

```text
http://127.0.0.1:8000/api/llm/status
```

### Documentation API

```text
http://127.0.0.1:8000/docs
```

---

## Résumé

Pour une installation neuve avec Ollama :

```powershell
git clone https://github.com/StouneRocco/MyRepo.git
cd MyRepo\BOBOS-main

py -3.11 -m venv .runtime
.\.runtime\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Copy-Item .env.example .env
```

Configurer `.env` avec :

```dotenv
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:latest
LLM_TIMEOUT_SECONDS=180
```

Puis, dans un terminal dédié :

```powershell
ollama pull llama3.2
ollama serve
```

Et dans un autre :

```powershell
.\start.ps1
```

Enfin ouvrir :

```text
http://127.0.0.1:8000
```

**C'est le lancement recommandé pour avoir l'interface web + la base + le LLM local fonctionnels ensemble.**
