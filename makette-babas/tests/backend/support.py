"""Chargement unique de backend/app.py sans MongoDB réel ni clé JWT locale."""
import importlib
import os
import sys
from unittest.mock import patch

TEST_SECRET = 'test-secret-for-unit-tests-only-32-bytes'


def load_app():
    """Importe app.py une seule fois ; MongoClient est remplacé par un double."""
    if 'app' not in sys.modules:
        with patch.dict(os.environ, {'JWT_SECRET': TEST_SECRET}), patch('pymongo.MongoClient'):
            importlib.import_module('app')
    module = sys.modules['app']
    # Chaque test repart d'une vue non partagée et d'un compteur d'authentification vide.
    module.shared_view.active = False
    module.auth_attempts.clear()
    return module


def bearer(module, username='test', version=0):
    return {'Authorization': 'Bearer ' + module.make_token(username, version)}
