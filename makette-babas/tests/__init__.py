"""Tests automatisés du projet, regroupés par partie (backend, projecteur, shared, frontend).

Les modules applicatifs ne sont pas des paquets Python : chaque sous-paquet de
tests ajoute au chemin d'import les dossiers sources de la partie qu'il valide.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / 'fixtures'


def add_source_paths(*folders):
    for folder in folders:
        path = str(ROOT / folder)
        if path not in sys.path:
            sys.path.insert(0, path)
