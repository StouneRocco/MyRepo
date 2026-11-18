"""Import CSV ou XLSX depuis ressources, sans modifier les comptes utilisateurs."""
import argparse
import csv
import datetime as dt
import math
import os
import hashlib
import json
from collections import Counter
from pathlib import Path
from zoneinfo import ZoneInfo

from pymongo import MongoClient, ReplaceOne
from pymongo.errors import BulkWriteError

RESOURCE_DIR = Path(__file__).resolve().parent.parent / 'ressources'
REQUIRED = {'timestamp', 'value', 'room', 'floor', 'zone'}


def read_rows(path, sheet=None):
    if path.suffix.lower() == '.csv':
        with path.open(encoding='utf-8-sig', newline='') as stream:
            sample = stream.read(4096)
            stream.seek(0)
            reader = csv.DictReader(stream, dialect=csv.Sniffer().sniff(sample, delimiters=',;\t'))
            if not REQUIRED.issubset(reader.fieldnames or []):
                raise ValueError('Colonnes requises : ' + ', '.join(sorted(REQUIRED)))
            yield from reader
        return
    from openpyxl import load_workbook
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        worksheet = workbook[sheet] if sheet else workbook.active
        rows = iter(worksheet.iter_rows(values_only=True))
        header = next(rows, ())
        # Le fichier fourni contient une ligne CSV complète dans chaque cellule A.
        embedded_csv = (bool(header) and isinstance(header[0], str) and ',' in header[0]
                        and all(value is None for value in header[1:]))
        if embedded_csv:
            header = next(csv.reader([header[0]]))
        header = [str(value or '').strip().lstrip('\ufeff') for value in header]
        if not REQUIRED.issubset(header):
            raise ValueError('Colonnes requises : ' + ', '.join(sorted(REQUIRED)))
        for row in rows:
            if all(value is None for value in row):
                continue
            if embedded_csv:
                row = next(csv.reader([str(row[0] or '')]))
            yield dict(zip(header, row))
    finally:
        workbook.close()


def measurement(row):
    if not REQUIRED.issubset(row):
        return None
    try:
        value = float(str(row['value']).strip().replace(',', '.'))
        if not math.isfinite(value):
            return None
        timestamp = row['timestamp']
        if not isinstance(timestamp, dt.datetime):
            timestamp = dt.datetime.fromisoformat(str(timestamp).strip().replace('Z', '+00:00'))
        if timestamp.tzinfo is None:
            local = timestamp.replace(tzinfo=ZoneInfo(os.getenv('TEMPERATURE_TIMEZONE', 'Europe/Paris')))
            # Sans offset, ni heure inexistante ni heure ambiguë ne peut être importée sûrement.
            if local.astimezone(dt.timezone.utc).astimezone(local.tzinfo).replace(tzinfo=None)!=timestamp:
                return None
            if local.utcoffset()!=local.replace(fold=1).utcoffset():
                return None
            timestamp = local
        room = str(row['room'] or '').strip()
        if not room:
            return None
        return {'room': room, 'timestamp': timestamp.astimezone(dt.timezone.utc),
                'temperature': value, 'floor': str(row['floor'] or '').strip(),
                'zone': str(row['zone'] or '').strip()}
    except (ValueError, TypeError, OverflowError):
        return None


def insert_measurements(collection, batch, replace=False):
    """Insertion groupée ; l'index unique conserve les mesures déjà importées."""
    if replace:
        result=collection.bulk_write([ReplaceOne({'room':doc['room'],'timestamp':doc['timestamp']},doc,upsert=True) for doc in batch],ordered=False)
        return result.upserted_count+result.modified_count
    try:
        return len(collection.insert_many(batch, ordered=False).inserted_ids)
    except BulkWriteError as error:
        if error.details.get('writeConcernErrors') or any(item['code'] != 11000 for item in error.details.get('writeErrors', [])):
            raise
        return error.details.get('nInserted', 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', nargs='?', type=Path, help='Fichier facultatif si plusieurs sources sont présentes')
    parser.add_argument('--sheet', help='Nom de feuille XLSX ; par défaut la feuille active')
    parser.add_argument('--dry-run', action='store_true', help='Analyse uniquement, sans connexion ni écriture MongoDB')
    parser.add_argument('--replace-existing', action='store_true', help='Remplace explicitement les valeurs existantes ayant la même salle/date')
    parser.add_argument('--report',type=Path,help='Rapport JSON ; par défaut dans .runtime/imports')
    args = parser.parse_args()
    files = sorted(p for p in RESOURCE_DIR.iterdir() if p.suffix.lower() in {'.csv', '.xlsx'} and not p.name.startswith('~$'))
    if args.file:
        path = args.file
    elif len(files) == 1:
        path = files[0]
    else:
        parser.error('Indiquez un fichier : ' + ', '.join(str(p) for p in files))
    inserted = ignored = valid = 0
    digest=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):
            digest.update(block)
    coverage=Counter();rejected=[]
    started=dt.datetime.now(dt.timezone.utc)
    report_path=args.report or RESOURCE_DIR.parent/'.runtime'/'imports'/f'{started.strftime("%Y%m%dT%H%M%S%f")}.json'
    def analysed():
        nonlocal ignored,valid
        for line,row in enumerate(read_rows(path,args.sheet),2):
            doc=measurement(row)
            if doc is None:
                ignored+=1
                if len(rejected)<100:rejected.append(line)
                continue
            valid+=1
            local=doc['timestamp'].astimezone(ZoneInfo(os.getenv('TEMPERATURE_TIMEZONE','Europe/Paris')))
            coverage[(local.strftime('%Y-%m'),doc['room'])]+=1
            yield doc
    def write_report():
        report={'file':path.name,'sha256':digest.hexdigest(),'startedAt':started.isoformat(),
                'dryRun':args.dry_run,'replaceExisting':args.replace_existing,'sheet':args.sheet,
                'valid':valid,'rejected':ignored,'insertedOrUpdated':inserted,
                'unchangedOrDuplicate':valid-inserted if not args.dry_run else None,
                'rejectedLineExamples':rejected,
                'coverage':[{'month':month,'room':room,'measurements':count} for (month,room),count in sorted(coverage.items())]}
        report_path.parent.mkdir(parents=True,exist_ok=True)
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'Rapport : {report_path}')
    if args.dry_run:
        for _ in analysed():pass
        write_report()
        return
    with MongoClient(os.getenv('MONGO_URI', 'mongodb://127.0.0.1:27017'), serverSelectionTimeoutMS=3000) as client:
        collection = client[os.getenv('MONGO_DB', 'calibration_app_pc')]['temperature_measurements']
        collection.create_index([('room', 1), ('timestamp', 1)], unique=True)
        collection.create_index('timestamp')
        batch = []
        for doc in analysed():
            batch.append(doc)
            if len(batch) == 5000:
                inserted += insert_measurements(collection, batch,replace=args.replace_existing)
                batch = []
                if valid % 50000 == 0:
                    print(f'{valid} mesures valides traitées, {inserted} insérées…', flush=True)
        if batch:
            inserted += insert_measurements(collection, batch,replace=args.replace_existing)
    write_report()
    print(f'{path.name} : {inserted} insérées/modifiées, {valid - inserted} inchangées ou doublons, {ignored} ignorées.')


if __name__ == '__main__':
    main()
