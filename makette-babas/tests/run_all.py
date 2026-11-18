"""Lance les tests de toutes les parties, ou seulement celles indiquées.

    python tests/run_all.py                      # tout
    python tests/run_all.py backend projector    # une sélection

Chaque partie tourne dans son propre processus, comme dans la CI. Le code de
sortie est non nul si une partie échoue ou ne peut pas être lancée.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARTS = {
    'backend': 'API Flask, données journalières, imports, badgeages, outils locaux',
    'projector': 'récepteur de projection, calibration, tracking, rendu',
    'shared': 'catalogue N3, échelle thermique, contexte projeté',
    'frontend': 'logique du site React (Node.js)',
}


def command(part):
    if part == 'frontend':
        node = shutil.which('node')
        if node is None:
            return None
        return [node, '--test', *sorted(str(path) for path in (ROOT / 'tests' / 'frontend').glob('*.test.js'))]
    return [sys.executable, '-m', 'unittest', 'discover', '-s', f'tests/{part}', '-t', '.']


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('parts', nargs='*', metavar='partie', help='Parmi : ' + ', '.join(PARTS))
    selected = parser.parse_args().parts or list(PARTS)
    unknown = [part for part in selected if part not in PARTS]
    if unknown:
        parser.error('Partie inconnue : ' + ', '.join(unknown))
    results = {}
    for part in selected:
        print(f'\n=== {part} : {PARTS[part]} ===', flush=True)
        arguments = command(part)
        if arguments is None:
            print('Node.js introuvable : installe Node 22 ou plus récent.', flush=True)
            results[part] = False
            continue
        results[part] = subprocess.run(arguments, cwd=ROOT).returncode == 0
    print('\n=== Résumé ===')
    for part, success in results.items():
        print(f"{'OK    ' if success else 'ÉCHEC '} {part}")
    return 0 if all(results.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
