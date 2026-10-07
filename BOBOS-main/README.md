# BOBOS — Lancement de l'application

Ce README explique les étapes nécessaires pour lancer correctement **l'application web BOBOS**, préparer les données avec l'ETL, démarrer le backend/frontend et connecter le LLM.

> Les commandes ci-dessous supposent que le terminal VS Code est **déjà ouvert dans le dossier BOBOS-main**.

---

# 1. Prérequis

Le projet fonctionne avec **Python 3.11 ou 3.12**, VS Code et PowerShell.

Si les dépendances Python ne sont pas encore installées :

~~~powershell
python -m pip install -r requirements.txt
~~~

---

# 2. Configurer le fichier .env

Créer le fichier de configuration :

~~~powershell
Copy-Item .env.example .env
~~~

Pour utiliser le LLM local avec Ollama, mettre dans .env :

~~~dotenv
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:latest
LLM_TIMEOUT_SECONDS=180

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o

ENERGY_PRICE_EUR_KWH=0.20
AREA_PER_PERSON_M2=4
~~~

Ne jamais mettre une clé API dans le frontend ou dans GitHub.

---

# 3. Préparer le LLM avec Ollama

Vérifier Ollama :

~~~powershell
ollama --version
~~~

Télécharger le modèle :

~~~powershell
ollama pull llama3.2
~~~

Vérifier :

~~~powershell
ollama list
~~~

Puis démarrer Ollama :

~~~powershell
ollama serve
~~~

**Laisser ce terminal ouvert.**

Ollama écoute normalement sur :

~~~text
http://127.0.0.1:11434
~~~

---

# 4. Lancer l'ETL

L'ETL prépare les données nécessaires au fonctionnement de l'application et génère la base SQLite utilisée par le backend.

Dans un **deuxième terminal VS Code**, toujours dans BOBOS-main :

~~~powershell
python -m Backend.etl
~~~

Cette étape peut prendre plusieurs minutes selon les données.

À la fin, la base doit notamment être disponible ici :

~~~text
Backend/bos.db
~~~

### Si les données doivent être réimportées

Arrêter le serveur avec CTRL+C, puis :

~~~powershell
python -m Backend.etl
~~~

**Ne pas lancer deux ETL en même temps.**

---

# 5. Lancer le backend + le frontend

Le projet n'a **pas besoin d'un serveur frontend séparé**.

Le frontend est servi directement par FastAPI depuis :

~~~text
Backend/static/
~~~

Lancer le serveur dans un **troisième terminal VS Code** :

~~~powershell
python -m uvicorn Backend.app:app --host 127.0.0.1 --port 8000
~~~

Vous devriez voir le serveur démarrer sur :

~~~text
http://127.0.0.1:8000
~~~

## Frontend

Ouvrir :

~~~text
http://127.0.0.1:8000
~~~

C'est l'interface web BOBOS.

## Backend / API

Documentation interactive :

~~~text
http://127.0.0.1:8000/docs
~~~

Le backend et le frontend sont donc lancés par **une seule commande**.

---

# 6. Vérifier que le backend fonctionne

Dans un autre terminal :

~~~powershell
Invoke-WebRequest http://127.0.0.1:8000/api/health
~~~

Le résultat doit indiquer :

~~~json
{
  "status": "ok"
}
~~~

---

# 7. Vérifier que le LLM est connecté

Ouvrir :

~~~text
http://127.0.0.1:8000/api/llm/status
~~~

Avec Ollama correctement lancé, le statut doit indiquer notamment :

~~~json
{
  "provider": "ollama",
  "connected": true
}
~~~

Le modèle llama3.2:latest doit apparaître parmi les modèles disponibles.

---

# 8. Vérifier les données et les anomalies

Dashboard :

~~~text
http://127.0.0.1:8000/api/dashboard
~~~

Métadonnées :

~~~text
http://127.0.0.1:8000/api/metadata
~~~

Anomalies détectées :

~~~text
http://127.0.0.1:8000/api/insights/raw
~~~

Recommandations générées par le LLM :

~~~text
http://127.0.0.1:8000/api/insights/smart
~~~

---

# 9. Utiliser l'application web

Une fois les étapes précédentes terminées :

1. ouvrir **http://127.0.0.1:8000** ;
2. vérifier que le dashboard s'affiche ;
3. vérifier les données de présence et d'énergie ;
4. afficher les anomalies ;
5. cliquer sur **Générer les recommandations** ;
6. vérifier que le LLM génère les cartes d'action ;
7. consulter les preuves associées ;
8. éventuellement cliquer sur une action.

Les commandes sont **simulées** : aucun équipement réel n'est commandé.

---

# 10. Ordre exact des terminaux

Pour une démonstration, utiliser idéalement **3 terminaux VS Code**.

## Terminal 1 — Ollama

~~~powershell
ollama serve
~~~

Garder ce terminal ouvert.

## Terminal 2 — ETL

Lancer une fois au démarrage, si la base n'est pas encore créée :

~~~powershell
python -m Backend.etl
~~~

Attendre la fin de l'import.

## Terminal 3 — Backend + Frontend

~~~powershell
python -m uvicorn Backend.app:app --host 127.0.0.1 --port 8000
~~~

Puis ouvrir :

~~~text
http://127.0.0.1:8000
~~~

---

# 11. Alternative : utiliser start.ps1

Le projet possède également un script de démarrage automatique :

~~~powershell
.\start.ps1
~~~

Il peut :

- préparer l'environnement Python ;
- installer les dépendances ;
- lancer l'ETL si la base n'existe pas ;
- démarrer FastAPI.

Pour comprendre et contrôler chaque étape pendant une soutenance, il est recommandé d'utiliser la procédure manuelle **Ollama → ETL → Backend/Frontend** décrite ci-dessus.

---

# 12. Réimporter les données

Si les données dans Data/ ont été modifiées :

1. arrêter FastAPI avec CTRL+C ;
2. lancer :

~~~powershell
python -m Backend.etl
~~~

3. attendre la fin de l'ETL ;
4. relancer le backend :

~~~powershell
python -m uvicorn Backend.app:app --host 127.0.0.1 --port 8000
~~~

Puis ouvrir :

~~~text
http://127.0.0.1:8000
~~~

---

# 13. Si Ollama ne fonctionne pas

Vérifier qu'Ollama est lancé :

~~~powershell
ollama list
~~~

Tester son API :

~~~powershell
Invoke-WebRequest http://127.0.0.1:11434/api/tags
~~~

Si nécessaire :

~~~powershell
ollama serve
~~~

Puis vérifier dans BOBOS :

~~~text
http://127.0.0.1:8000/api/llm/status
~~~

---

# 14. Si la base de données n'existe pas

Erreur :

~~~text
Base absente
~~~

Lancer :

~~~powershell
python -m Backend.etl
~~~

Puis relancer :

~~~powershell
python -m uvicorn Backend.app:app --host 127.0.0.1 --port 8000
~~~

---

# 15. Si le port 8000 est déjà utilisé

Vérifier :

~~~powershell
netstat -ano | findstr :8000
~~~

Arrêter le processus concerné :

~~~powershell
taskkill /PID NUMERO_DU_PID /F
~~~

Puis relancer FastAPI.

---

# 16. Tests

Tests Python :

~~~powershell
python -m unittest discover -s tests -v
~~~

Vérification JavaScript :

~~~powershell
node --check Backend/static/app.js
~~~

---

# 17. Architecture du lancement

~~~text
                 ┌─────────────────┐
                 │     Ollama      │
                 │   llama3.2      │
                 │   :11434        │
                 └────────┬────────┘
                          │
                          │ LLM
                          ▼
┌─────────────┐     ┌─────────────────┐
│    Data/    │────▶│   Backend.etl   │
│ IFC + IoT   │     │      ETL        │
└─────────────┘     └────────┬────────┘
                             │
                             ▼
                       Backend/bos.db
                             │
                             ▼
                    ┌─────────────────┐
                    │     FastAPI     │
                    │      :8000      │
                    └───────┬─────────┘
                            │
                 ┌──────────┴──────────┐
                 ▼                     ▼
             Frontend                API
          Backend/static/        /api/...
                 │
                 ▼
             Navigateur
       http://127.0.0.1:8000
~~~

---

# 18. Commandes essentielles — résumé

Si Python et les dépendances sont **déjà installés**, la séquence de lancement est simplement :

### Terminal 1 — LLM

~~~powershell
ollama serve
~~~

### Terminal 2 — ETL

~~~powershell
python -m Backend.etl
~~~

Attendre la fin de l'ETL.

### Terminal 3 — Backend + Frontend

~~~powershell
python -m uvicorn Backend.app:app --host 127.0.0.1 --port 8000
~~~

### Navigateur

~~~text
http://127.0.0.1:8000
~~~

### Vérification du LLM

~~~text
http://127.0.0.1:8000/api/llm/status
~~~

### Documentation du backend

~~~text
http://127.0.0.1:8000/docs
~~~

**Ordre recommandé : Ollama → ETL → Backend/Frontend → navigateur.**
