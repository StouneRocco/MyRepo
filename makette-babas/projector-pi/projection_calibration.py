"""Réglage géométrique indépendant de la caméra et de la fenêtre OpenCV."""
import math

DEFAULT_CORNERS = [[0, 0], [1, 0], [1, 1], [0, 1]]


def default_settings():
    return {'mode': 'automatic', 'corners': [p[:] for p in DEFAULT_CORNERS], 'showGuide': False}


def validate_settings(data):
    if not isinstance(data, dict) or data.get('mode') not in ('automatic', 'manual'):
        raise ValueError('Mode automatique ou manuel requis.')
    points = data.get('corners')
    if not isinstance(points, list) or len(points) != 4:
        raise ValueError('Quatre coins requis : haut gauche, haut droit, bas droit, bas gauche.')
    for point in points:
        if not isinstance(point, list) or len(point) != 2 or any(
            isinstance(v, bool) or not isinstance(v, (int, float))
            or not math.isfinite(v) or not -.5 <= v <= 1.5 for v in point
        ):
            raise ValueError('Coordonnées des coins comprises entre -50 % et 150 % requises.')
    # Un quadrilatère convexe dans le bon ordre évite les miroirs et les matrices singulières.
    for i in range(4):
        a, b, c = (points[(i + j) % 4] for j in range(3))
        cross = (b[0]-a[0])*(c[1]-b[1]) - (b[1]-a[1])*(c[0]-b[0])
        if cross < .0001:
            raise ValueError('Les coins doivent former un quadrilatère convexe sans se croiser.')
    if not isinstance(data.get('showGuide'), bool):
        raise ValueError('Affichage du repère requis.')
    result = {'mode': data['mode'], 'corners': [p[:] for p in points], 'showGuide': data['showGuide']}
    for field in ('sourceCorners', 'initialCorners'):
        if field not in data:
            continue
        # Les anciens réglages restent ancrés au cadre de l'écran.
        source = validate_settings({'mode':data['mode'], 'corners':data[field], 'showGuide':data['showGuide']})['corners']
        result[field] = source
    return result


def manual_from_automatic(settings, plan_corners, width, height, automatic_matrix):
    """Fige l'alignement obtenu automatiquement aux quatre coins du plan."""
    import cv2
    import numpy as np
    if automatic_matrix is None:
        raise ValueError('Termine la calibration automatique et la détection des quatre repères avant le réglage manuel.')
    scale = np.float32([width-1, height-1])
    matrix = projection_matrix(settings, width, height, automatic_matrix)
    target = (cv2.perspectiveTransform((np.float32(plan_corners)*scale)[None], matrix)[0]/scale).tolist()
    return validate_settings({'mode':'manual', 'sourceCorners':plan_corners,
                              'corners':target, 'initialCorners':target, 'showGuide':True})


def projection_matrix(settings, width, height, automatic_matrix=None):
    import cv2
    import numpy as np

    scale = np.float32([width - 1, height - 1])
    source = np.float32(settings.get('sourceCorners', DEFAULT_CORNERS) if settings['mode'] == 'manual' else DEFAULT_CORNERS) * scale
    target = np.float32(settings['corners']) * scale
    correction = cv2.getPerspectiveTransform(source, target)
    if settings['mode'] == 'manual':
        return correction
    return None if automatic_matrix is None else correction @ automatic_matrix
