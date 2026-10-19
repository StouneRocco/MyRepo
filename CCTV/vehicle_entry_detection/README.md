# Vehicle Entry Detection

Prototype de détection et de suivi de personnes, vélos et véhicules dans un flux vidéo.

## Installation

```bash
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

## Lancer

Déposez une vidéo de test dans `videos/test.mp4`, puis :

```bash
python main.py
```

Le modèle YOLO est téléchargé automatiquement au premier lancement.

Appuyez sur `ESC` pour quitter.

## Classes suivies

- personne
- vélo
- voiture
- moto
- bus
- camion

## Prochaine étape

Ajouter une zone d'entrée/sortie configurable et détecter le franchissement de cette zone.
