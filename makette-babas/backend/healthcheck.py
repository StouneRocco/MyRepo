"""Vérifie MongoDB sans afficher l'URI ni ses éventuels identifiants."""
import os
import sys
from pymongo import MongoClient
from pymongo.errors import PyMongoError


if __name__ == '__main__':
    try:
        with MongoClient(os.getenv('MONGO_URI','mongodb://127.0.0.1:27017'), serverSelectionTimeoutMS=1000) as client:
            client.admin.command('ping')
    except PyMongoError:
        sys.exit(1)
