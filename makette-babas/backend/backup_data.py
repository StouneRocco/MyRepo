"""Sauvegarde BSON en JSON compressé ; restauration dans une base vide uniquement."""
import argparse
import datetime as dt
import gzip
import os
from pathlib import Path

from bson import json_util
from pymongo import MongoClient

COLLECTIONS=('temperature_measurements','users','viewer_state','import_runs')


def backup(database, target):
    target=Path(target)
    if target.exists():
        raise ValueError('Le fichier de sauvegarde existe déjà.')
    temporary=target.with_suffix(target.suffix+'.partial')
    # Pas d'écrasement d'un export précédent interrompu.
    with temporary.open('xb') as raw:
        with gzip.GzipFile(fileobj=raw,mode='wb') as stream:
            header={'format':'maquette-backup-v1','createdAt':dt.datetime.now(dt.timezone.utc)}
            stream.write((json_util.dumps(header)+'\n').encode('utf-8'))
            for collection in COLLECTIONS:
                for doc in database[collection].find({}).batch_size(1000):
                    stream.write((json_util.dumps({'collection':collection,'document':doc})+'\n').encode('utf-8'))
    temporary.rename(target)


def restore(database, source):
    if database.list_collection_names():
        raise ValueError('La base de destination doit être entièrement vide.')
    batches={name:[] for name in COLLECTIONS}
    with gzip.open(source,'rt',encoding='utf-8') as stream:
        if json_util.loads(next(stream)).get('format')!='maquette-backup-v1':
            raise ValueError('Format de sauvegarde inconnu.')
        for line in stream:
            item=json_util.loads(line)
            name=item['collection']
            if name not in batches:
                raise ValueError('Collection non autorisée dans la sauvegarde.')
            batches[name].append(item['document'])
            if len(batches[name])==1000:
                database[name].insert_many(batches[name]);batches[name]=[]
    for name,docs in batches.items():
        if docs:database[name].insert_many(docs)
    database.users.create_index('username',unique=True)
    database.temperature_measurements.create_index([('room',1),('timestamp',1)],unique=True)
    database.temperature_measurements.create_index('timestamp')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['backup','restore'])
    parser.add_argument('file',type=Path)
    parser.add_argument('--database',help='Obligatoire pour restaurer ; nom différent de la base active.')
    args=parser.parse_args()
    active=os.getenv('MONGO_DB','calibration_app_pc')
    if args.action=='restore' and (not args.database or args.database==active):
        parser.error('Restauration autorisée uniquement vers une autre base explicitement nommée.')
    with MongoClient(os.getenv('MONGO_URI','mongodb://127.0.0.1:27017'),serverSelectionTimeoutMS=3000) as client:
        database=client[args.database or active]
        if args.action=='backup':backup(database,args.file)
        else:restore(database,args.file)
    print('Opération terminée. Les certificats et clés privées ne font pas partie de cette sauvegarde.')


if __name__=='__main__':main()
