"""Validation du contexte affiché avec les températures projetées."""
import datetime
import math


def validate_context(data, codes):
    if not isinstance(data, dict):
        raise ValueError('Contexte de projection invalide.')
    metric = data.get('metric', 'temperatures')
    maximum = data.get('scaleMax', 0)
    available = data.get('dataAvailable', True)
    if metric not in ('temperatures', 'presence', 'electricity') or type(available) is not bool:
        raise ValueError('Donnée projetée invalide.')
    if isinstance(maximum, bool) or not isinstance(maximum, (int, float)) or not math.isfinite(maximum) or maximum < 0:
        raise ValueError('Échelle de présence invalide.')
    day = data.get('day', '')
    if day:
        datetime.date.fromisoformat(day)
    minute = data.get('minute', 0)
    if isinstance(minute, bool) or not isinstance(minute, int) or not 0 <= minute < 1440:
        raise ValueError('Horaire invalide.')
    estimated = data.get('estimated', [])
    if not isinstance(estimated, list) or any(code not in codes for code in estimated):
        raise ValueError('Salles interpolées invalides.')
    room = data.get('roomCode')
    if room is not None and room not in codes:
        raise ValueError('Salle inconnue.')
    stats = data.get('roomStats', {})
    if not isinstance(stats, dict):
        raise ValueError('Statistiques invalides.')
    for key, value in stats.items():
        if key not in ('min', 'mean', 'max') or (value is not None and
                (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value))):
            raise ValueError('Statistiques invalides.')
    result = {'day': day, 'minute': minute, 'estimated': estimated,
              'roomCode': room, 'roomStats': stats}
    if metric == 'presence' or 'metric' in data:
        result.update(metric=metric, scaleMax=maximum, dataAvailable=available)
    return result
