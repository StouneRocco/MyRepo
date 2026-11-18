"""Gestion locale des droits et révocation des sessions, sans mot de passe en argument."""
import argparse
import getpass
import os
from pymongo import MongoClient
from werkzeug.security import generate_password_hash


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('username')
    parser.add_argument('--role',choices=['viewer','operator'])
    state=parser.add_mutually_exclusive_group()
    state.add_argument('--disable',action='store_true')
    state.add_argument('--enable',action='store_true')
    parser.add_argument('--revoke-sessions',action='store_true')
    parser.add_argument('--password',action='store_true',help='Demande le nouveau mot de passe sans l’afficher')
    args=parser.parse_args()
    changes={}
    if args.role:changes['role']=args.role
    if args.disable or args.enable:changes['disabled']=args.disable
    if args.password:
        password=getpass.getpass('Nouveau mot de passe : ')
        if not 8<=len(password)<=256:parser.error('Mot de passe de 8 à 256 caractères requis.')
        if password!=getpass.getpass('Confirmer : '):parser.error('Les mots de passe diffèrent.')
        changes['password']=generate_password_hash(password)
    if not changes and not args.revoke_sessions:parser.error('Choisis une modification.')
    with MongoClient(os.getenv('MONGO_URI','mongodb://127.0.0.1:27017'),serverSelectionTimeoutMS=3000) as client:
        users=client[os.getenv('MONGO_DB','calibration_app_pc')].users
        account=users.find_one({'username':args.username.strip().lower()})
        if not account:parser.error('Compte inconnu.')
        if (args.disable or args.role=='viewer') and account.get('role','operator') in ('operator','admin'):
            if users.count_documents({'disabled':{'$ne':True},'role':{'$nin':['viewer']}})<=1:
                parser.error('Impossible de retirer le dernier opérateur actif.')
        operation={'$inc':{'session_version':1}}
        if changes:operation['$set']=changes
        users.update_one({'_id':account['_id']},operation)
    print('Compte modifié. Ses anciennes sessions sont révoquées.')


if __name__=='__main__':main()
