"""Contours SVG et recalage sur le JPG, sans dépendance matérielle."""
import json
import math
import os
from pathlib import Path

PLAN = json.loads((Path(__file__).resolve().parent.parent / "shared/plan-n3.json").read_text(encoding="utf-8"))
ROOMS = {room["id"]: room for room in PLAN["rooms"]}


def image_points(room_id, width, height):
    """Recalage affine des coordonnées SVG sur les limites du bâtiment du JPG."""
    sx0, sy0, sx1, sy1 = PLAN["svgBounds"]
    bounds = os.getenv("PLAN_IMAGE_BOUNDS")
    ix0, iy0, ix1, iy1 = json.loads(bounds) if bounds else PLAN["imageBounds"]
    return [
        [(ix0 + (x - sx0) / (sx1 - sx0) * (ix1 - ix0)) * width,
         (iy0 + (y - sy0) / (sy1 - sy0) * (iy1 - iy0)) * height]
        for x, y in ROOMS[room_id]["points"]
    ]


def projection_points(room_id, width, height):
    """Aplat centré réduit à 65 % de la surface, sans déplacer le recalage ni les tags."""
    points = image_points(room_id, width, height)
    edges = list(zip(points, points[1:] + points[:1]))
    cross = [a[0] * b[1] - b[0] * a[1] for a, b in edges]
    area_twice = sum(cross)
    if abs(area_twice) < 1e-8:
        return points
    center = [sum((a[axis] + b[axis]) * weight for (a, b), weight in zip(edges, cross))
              / (3 * area_twice) for axis in (0, 1)]
    scale = math.sqrt(0.65)
    return [[center[0] + (x - center[0]) * scale,
             center[1] + (y - center[1]) * scale] for x, y in points]


TEMPERATURE_SCALE = json.loads((Path(__file__).resolve().parent.parent / "shared/temperature-scale.json").read_text(encoding="utf-8"))


def temperature_color(value):
    """Couleur BGR OpenCV : bleu → vert (21 °C) → rouge, noir sans mesure."""
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return (0, 0, 0)
    value = max(TEMPERATURE_SCALE[0]["temperature"], min(TEMPERATURE_SCALE[-1]["temperature"], value))
    for low, high in zip(TEMPERATURE_SCALE, TEMPERATURE_SCALE[1:]):
        if value <= high["temperature"]:
            ratio = (value - low["temperature"]) / (high["temperature"] - low["temperature"])
            rgb = [round(a + (b - a) * ratio) for a, b in zip(low["color"], high["color"])]
            return tuple(reversed(rgb))


def validate_temperatures(data):
    """Ne transmettre que les codes du plan et des nombres finis."""
    if not isinstance(data, dict):
        raise ValueError("Dictionnaire de températures requis.")
    codes = {room["code"] for room in ROOMS.values()}
    for code, value in data.items():
        if code not in codes or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Code de salle ou température invalide.")
    return data


def render_calibration_plan(width, height, zone):
    """Plan architectural existant, murs blancs sur noir, limité au bâtiment."""
    import cv2
    import numpy as np
    image = cv2.imread(str(Path(__file__).resolve().parent / 'plan_N3_test.jpg'), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError('Le plan projector-pi/plan_N3_test.jpg est introuvable.')
    x, y, zone_width, zone_height = zone
    resized = cv2.resize(image, (zone_width, zone_height), interpolation=cv2.INTER_AREA)
    _, walls = cv2.threshold(255-resized, 25, 255, cv2.THRESH_BINARY)
    result = np.zeros((height, width, 3), dtype=np.uint8)
    result[y:y+zone_height, x:x+zone_width] = cv2.cvtColor(walls, cv2.COLOR_GRAY2BGR)
    return result


def render_temperature_canvas(width, height, zone, temperatures, selected_room_id=None, show_guide=False):
    """Aplats thermiques et surbrillance de la sélection, sur fond noir."""
    import cv2
    import numpy as np

    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    x, y, zone_width, zone_height = zone
    for room_id, room in ROOMS.items():
        color = temperature_color(temperatures.get(room["code"]))
        selected = room_id == selected_room_id
        if color == (0, 0, 0) and not selected and not show_guide:
            continue
        points = np.rint(projection_points(room_id, zone_width, zone_height)).astype(np.int32)
        points += np.array([x, y])
        if selected:
            color = tuple(round(c * .55 + 255 * .45) for c in color) if color != (0, 0, 0) else (255, 255, 255)
        cv2.fillPoly(canvas, [points], color)
        if selected or show_guide:
            cv2.polylines(canvas, [points], True, (255, 255, 255) if selected else (100, 100, 100), 4 if selected else 1)
    return canvas


def projection_summary(temperatures, selected_room_id=None):
    values = [temperatures[room['code']] for room in ROOMS.values() if room['code'] in temperatures]
    room = ROOMS.get(selected_room_id)
    return {'count': len(values), 'missing': len(ROOMS)-len(values),
            'min': min(values) if values else None, 'max': max(values) if values else None,
            'mean': sum(values)/len(values) if values else None,
            'room': room, 'temperature': temperatures.get(room['code']) if room else None}


def render_projection_info(image, temperatures, selected_room_id=None, context=None):
    """Légende et informations lisibles, hors de la déformation du plan."""
    import cv2
    context = context or {}
    summary = projection_summary(temperatures, selected_room_id)
    height, width = image.shape[:2]
    sx, sy = width/1920, height/1080

    def rectangle(x0, y0, x1, y1, color, thickness=-1):
        cv2.rectangle(image, (round(x0*sx), round(y0*sy)), (round(x1*sx), round(y1*sy)), color, thickness)

    def text(label, x, y, size=.65, color=(255,255,255)):
        import unicodedata
        label = unicodedata.normalize('NFKD', label).encode('ascii', 'ignore').decode()
        cv2.putText(image, label, (round(x*sx),round(y*sy)), cv2.FONT_HERSHEY_SIMPLEX,
                    size*min(sx,sy), color, max(1,round(2*min(sx,sy))), cv2.LINE_AA)

    def number(value):
        return 'sans mesure' if value is None else f'{value:.1f} C'

    # Bandes libres entre les tags : x=250..1670, au-dessus et au-dessous du bâtiment.
    rectangle(260, 50, 1660, 245, (0,0,0))
    day = context.get('day') or 'Date indisponible'
    if len(day) == 10 and day[4] == '-':
        day = '/'.join(reversed(day.split('-')))
    minute = context.get('minute',0)
    text(f"N3   {day}   {minute//60:02d}:{minute%60:02d}",300,100,1.15)
    text(f"Etage : {number(summary['mean'])}   Min {number(summary['min'])}   Max {number(summary['max'])}   {summary['count']}/{len(ROOMS)} salles",300,150,.85)
    if summary['room']:
        room = summary['room']
        origin = 'absente' if summary['temperature'] is None else 'interpolee' if room['code'] in context.get('estimated',[]) else 'mesuree'
        label = f"{room['code']} : {number(summary['temperature'])} ({origin})"
        text(label,300,205,1)
    else:
        text(f"{summary['missing']} sans valeur   /   {len(context.get('estimated',[]))} interpolees",300,205,.8)
    rectangle(260,850,1660,1030,(0,0,0))
    text('TEMPERATURE (C)',300,900,.75)
    for offset in range(900):
        value = 12 + offset/899*18
        rectangle(480+offset,920,481+offset,950,temperature_color(value))
    for stop in TEMPERATURE_SCALE:
        x = 480 + (stop['temperature']-12)/18*900
        text(str(stop['temperature']),x-12,995,.7)
    rectangle(1470,920,1500,950,(255,255,255),2)
    text('Sans mesure',1430,995,.55)
    return image
