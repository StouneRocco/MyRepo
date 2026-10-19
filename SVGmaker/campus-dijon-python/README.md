# Campus Dijon — V0 Python

## Backend
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Raspberry Pi: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000

## Frontend
Le frontend est volontairement sans framework pour être copié/collé facilement.
Depuis `frontend/`, servir les fichiers avec:
python -m http.server 5500 --bind 0.0.0.0

Puis ouvrir http://localhost:5500

API: http://localhost:8000/docs
