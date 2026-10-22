"""Import CSV ou XLSX depuis ressources, sans modifier les comptes utilisateurs."""
import argparse
import csv
import datetime as dt
import math
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from pymongo import MongoClient
from pymongo.errors import BulkWriteError

RESOURCE_DIR = Path(__file__).resolve().parent.parent / 'ressources'
REQUIRED = {'timestamp', 'value', 'room', 'floor', 'zone'}


def read_rows(path):
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
        rows = iter(workbook.active.iter_rows(values_only=True))
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
            timestamp = timestamp.replace(tzinfo=ZoneInfo(os.getenv('TEMPERATURE_TIMEZONE', 'Europe/Paris')))
        room = str(row['room'] or '').strip()
        if not room:
            return None
        return {'room': room, 'timestamp': timestamp.astimezone(dt.timezone.utc),
                'temperature': value, 'floor': str(row['floor'] or '').strip(),
                'zone': str(row['zone'] or '').strip()}
    except (ValueError, TypeError, OverflowError):
        return None


def insert_measurements(collection, batch):
    """Insertion groupée ; l'index unique conserve les mesures déjà importées."""
    try:
        return len(collection.insert_many(batch, ordered=False).inserted_ids)
    except BulkWriteError as error:
        if error.details.get('writeConcernErrors') or any(item['code'] != 11000 for item in error.details.get('writeErrors', [])):
            raise
        return error.details.get('nInserted', 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', nargs='?', type=Path, help='Fichier facultatif si plusieurs sources sont présentes')
    args = parser.parse_args()
    files = sorted(p for p in RESOURCE_DIR.iterdir() if p.suffix.lower() in {'.csv', '.xlsx'} and not p.name.startswith('~$'))
    if args.file:
        path = args.file
    elif len(files) == 1:
        path = files[0]
    else:
        parser.error('Indiquez un fichier : ' + ', '.join(str(p) for p in files))
    inserted = ignored = valid = 0
    with MongoClient(os.getenv('MONGO_URI', 'mongodb://127.0.0.1:27017'), serverSelectionTimeoutMS=3000) as client:
        collection = client[os.getenv('MONGO_DB', 'calibration_app_pc')]['temperature_measurements']
        collection.create_index([('room', 1), ('timestamp', 1)], unique=True)
        collection.create_index('timestamp')
        batch = []
        for row in read_rows(path):
            doc = measurement(row)
            if doc is None:
                ignored += 1
                continue
            valid += 1
            batch.append(doc)
            if len(batch) == 5000:
                inserted += insert_measurements(collection, batch)
                batch = []
                if valid % 50000 == 0:
                    print(f'{valid} mesures valides traitées, {inserted} insérées…', flush=True)
        if batch:
            inserted += insert_measurements(collection, batch)
    print(f'{path.name} : {inserted} insérées, {valid - inserted} déjà présentes, {ignored} ignorées.')


if __name__ == '__main__':
    main()
