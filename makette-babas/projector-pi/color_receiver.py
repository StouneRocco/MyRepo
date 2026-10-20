"""
Script Pi (caméra + vidéoprojecteur) : calibration ArUco + tracking des 4 tags.

Ajout : POST /calibrate (port 5001) relance la calibration, comme la touche 'c'.
C'est cette route que la webapp appelle avec le bouton "Calibrer".
"""

import os
import threading
import json
import sys
from pathlib import Path

# OpenCV (pip) n'embarque que le pilote X11 : évite l'erreur Qt "wayland" sur le Pi.
# Doit être défini AVANT l'import de cv2.
if os.name != "nt":
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

import cv2
import numpy as np
from flask import Flask, jsonify, request, Response
from room_projection import PLAN, ROOMS, validate_temperatures, render_temperature_canvas, render_calibration_plan, render_projection_info
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'shared'))
from projection_context import validate_context
from projection_calibration import default_settings, validate_settings, projection_matrix, manual_from_automatic

# ==========================================
# 1. INITIALISATION CAMÉRA & PROJECTEUR
# ==========================================

# === COORDONNÉES OPTIQUES DE TA CAMÉRA ===
mtx = np.array([[640.8361346446267, 0.0, 642.1970179505878], [0.0, 640.6834131097554, 400.7343753725461], [0.0, 0.0, 1.0]], dtype=np.float32)
dist = np.array([[-0.053435528597298304, 0.059917653308379185, -0.0007565761946435137, 0.0024947196011283136, -0.018920873009399417]], dtype=np.float32)

# Numéro de /dev/videoN (testCam.py indique lequel répond). Un entier est
# nécessaire avec l'OpenCV du Pi : le chemin "/dev/video4" est refusé.
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0" if os.name == "nt" else "4"))

cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_V4L2)
if not cap.isOpened():
    print(f"Caméra {CAMERA_INDEX} indisponible : utilise la calibration manuelle ou vérifie CAMERA_INDEX.")
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

cv2.namedWindow('Projecteur', cv2.WINDOW_NORMAL)
cv2.moveWindow('Projecteur', int(os.getenv("PROJECTOR_X", "1920")), int(os.getenv("PROJECTOR_Y", "0")))
cv2.setWindowProperty('Projecteur', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

proj_w, proj_h = 1920, 1080

# ==========================================
# 2. CONFIGURATION DES ARUCOS
# ==========================================
dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
parameters = cv2.aruco.DetectorParameters()
parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
parameters.adaptiveThreshWinSizeMin = 3
parameters.adaptiveThreshWinSizeStep = 3

detector = cv2.aruco.ArucoDetector(dictionary, parameters)

# --- TES IDs PHYSIQUES (Mis à jour) ---
ID_HAUT_GAUCHE = 1
ID_HAUT_DROITE = 2
ID_BAS_DROITE = 3
ID_BAS_GAUCHE = 4

# --- ArUco de Calibration (ID 0) ---
calib_size = 400
calib_img = cv2.aruco.generateImageMarker(dictionary, 0, calib_size)
calib_img = cv2.cvtColor(calib_img, cv2.COLOR_GRAY2BGR)
projector_calib_screen = np.zeros((proj_h, proj_w, 3), dtype=np.uint8)
calib_x = int((proj_w - calib_size) / 2)
calib_y = int((proj_h - calib_size) / 2)
marge_blanche = 100
cv2.rectangle(projector_calib_screen,
              (calib_x - marge_blanche, calib_y - marge_blanche),
              (calib_x + calib_size + marge_blanche, calib_y + calib_size + marge_blanche),
              (255, 255, 255), -1)
projector_calib_screen[calib_y:calib_y+calib_size, calib_x:calib_x+calib_size] = calib_img
pts_proj_calib = np.float32([
    [calib_x, calib_y], [calib_x + calib_size, calib_y],
    [calib_x + calib_size, calib_y + calib_size], [calib_x, calib_y + calib_size]
])

# ==========================================
# 3. LE CANEVAS (Aplats de température entre les tags)
# ==========================================
canvas = np.zeros((proj_h, proj_w, 3), dtype=np.uint8)
aruco_physique_size = 200
marge = 50

# Coordonnées virtuelles du tag Haut-Gauche
x_hg, y_hg = marge, marge
# Coordonnées virtuelles du tag Bas-Droite
x_bd = proj_w - aruco_physique_size - marge
y_bd = proj_h - aruco_physique_size - marge

x_bg = marge
y_bg = proj_h - aruco_physique_size - marge

x_hd = proj_w - aruco_physique_size - marge
y_hd = marge

# Les limites englobent maintenant l'INTÉGRALITÉ des tags
zone_x_debut = int(x_hg)
zone_x_fin = int(x_bd + aruco_physique_size)
y_debut = int(y_hg)
y_fin = int(y_bd + aruco_physique_size)

largeur_zone = zone_x_fin - zone_x_debut
hauteur_zone = y_fin - y_debut
calibration_plan = render_calibration_plan(proj_w, proj_h, (zone_x_debut, y_debut, largeur_zone, hauteur_zone))

# ==========================================
# 3 bis. SERVEUR FLASK (reçoit l'ordre de la webapp)
# ==========================================
state_lock = threading.Lock()
calibration_requested = False  # mis à True par /calibrate, consommé par la boucle principale
selected_room_id = None
room_temperatures = {}
projection_context = {}
temperature_version = 0
rendered_temperature_version = -1
settings_path = Path(__file__).resolve().parent / '.projection_calibration.json'
try:
    calibration_settings = validate_settings(json.loads(settings_path.read_text(encoding='utf-8')))
except (OSError, ValueError):
    calibration_settings = default_settings()
automatic_matrix = None
preview_frame = np.zeros((540, 960, 3), dtype=np.uint8)
ix0, iy0, ix1, iy1 = json.loads(os.getenv('PLAN_IMAGE_BOUNDS', 'null')) or PLAN['imageBounds']
plan_corners = [[(zone_x_debut + x * largeur_zone)/(proj_w-1),
                 (y_debut + y * hauteur_zone)/(proj_h-1)]
                for x, y in [(ix0, iy0), (ix1, iy0), (ix1, iy1), (ix0, iy1)]]
control_corner = None
settings_revision = 0
automatic_settings = calibration_settings if calibration_settings['mode'] == 'automatic' else default_settings()


def control_mouse(event, x, y, flags, param):
    """Même manipulation directe que ProjoManuel.py, sur l'image 960 × 540."""
    global control_corner, calibration_settings, temperature_version, settings_revision
    with state_lock:
        if calibration_settings['mode'] != 'manual':
            control_corner = None
            return
        if event == cv2.EVENT_LBUTTONDOWN:
            points = np.array(calibration_settings['corners']) * [959, 539]
            distances = np.linalg.norm(points - [x, y], axis=1)
            nearest = int(np.argmin(distances))
            control_corner = nearest if distances[nearest] < 30 else None
        elif event == cv2.EVENT_MOUSEMOVE and control_corner is not None:
            points = [p[:] for p in calibration_settings['corners']]
            points[control_corner] = [max(-.5, min(1.5, x/959)), max(-.5, min(1.5, y/539))]
            try:
                calibration_settings = validate_settings({**calibration_settings, 'corners': points})
                temperature_version += 1
                settings_revision += 1
            except ValueError:
                pass
        elif event == cv2.EVENT_LBUTTONUP:
            control_corner = None


cv2.namedWindow('Controle PC')
cv2.setMouseCallback('Controle PC', control_mouse)

app = Flask(__name__)


@app.route("/calibrate", methods=["POST"])
def calibrate():
    global calibration_requested
    with state_lock:
        calibration_requested = True
    return jsonify({"status": "ok"})


@app.post("/project-room")
def project_room():
    global selected_room_id, temperature_version
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or "roomId" not in data:
        return jsonify({"error": "Salle manquante."}), 400
    room_id = data["roomId"]
    if room_id is not None and (not isinstance(room_id, str) or room_id not in ROOMS):
        return jsonify({"error": "Salle inconnue."}), 400
    with state_lock:
        selected_room_id = room_id
        temperature_version += 1
    return jsonify({"status": "ok", "roomId": room_id})


@app.post("/project-temperatures")
def project_temperatures():
    global room_temperatures, temperature_version, projection_context, selected_room_id
    try:
        data = request.get_json(silent=True)
        context = {}
        if isinstance(data, dict) and 'temperatures' in data:
            context = validate_context(data.get('context', {}), {room['code'] for room in ROOMS.values()})
            data = data['temperatures']
        values = validate_temperatures(data)
        payload = request.get_json(silent=True)
        room_id = payload.get('roomId') if isinstance(payload, dict) else None
        if room_id is not None and room_id not in ROOMS:
            raise ValueError('Salle inconnue.')
    except (ValueError, TypeError) as error:
        return jsonify({"error": str(error)}), 400
    with state_lock:
        room_temperatures = values
        projection_context = context
        if isinstance(payload, dict) and 'roomId' in payload:
            selected_room_id = room_id
        temperature_version += 1
    return jsonify({"status": "ok"})


@app.route('/calibration-settings', methods=['GET', 'POST'])
def calibration_controls():
    global calibration_settings, temperature_version, settings_revision, automatic_settings
    if request.method == 'POST':
        data = request.get_json(silent=True)
        if isinstance(data, dict) and data.get('action') in ('adjust-automatic', 'resume-automatic'):
            with state_lock:
                try:
                    settings = manual_from_automatic(automatic_settings, plan_corners, proj_w, proj_h, automatic_matrix) if data['action'] == 'adjust-automatic' else automatic_settings
                except ValueError as error:
                    return jsonify({'error':str(error)}), 409
                calibration_settings = settings
                temperature_version += 1
                settings_revision += 1
                return jsonify({**settings, 'automaticReady':automatic_matrix is not None, 'settingsRevision':settings_revision})
        try:
            settings = validate_settings(data)
            if not isinstance(data.get('persist', True), bool):
                raise ValueError('Option de sauvegarde invalide.')
        except ValueError as error:
            return jsonify({'error': str(error)}), 400
        with state_lock:
            if data.get('persist', True):
                temporary = settings_path.with_suffix('.tmp')
                try:
                    temporary.write_text(json.dumps(settings), encoding='utf-8')
                    temporary.replace(settings_path)
                except OSError:
                    return jsonify({'error': 'Impossible de sauvegarder la calibration.'}), 500
            calibration_settings = settings
            if settings['mode'] == 'automatic':
                automatic_settings = settings
            temperature_version += 1
            settings_revision += 1
    with state_lock:
        return jsonify({**calibration_settings, 'automaticReady': automatic_matrix is not None, 'planCorners': plan_corners, 'settingsRevision': settings_revision})


@app.get('/projection-preview')
def projection_preview():
    with state_lock:
        frame = preview_frame.copy()
        settings = {**calibration_settings, 'settingsRevision': settings_revision}
    ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        return jsonify({'error': 'Aperçu indisponible.'}), 503
    return Response(encoded.tobytes(), mimetype='image/jpeg', headers={'Cache-Control': 'no-store', 'X-Calibration-Settings': json.dumps(settings)})


def run_flask():
    # 127.0.0.1 : la webapp tourne sur le même Pi, la route n'est pas exposée au réseau.
    app.run(host="127.0.0.1", port=5001)


threading.Thread(target=run_flask, daemon=True).start()

# ==========================================
# 4. BOUCLE PRINCIPALE
# ==========================================
ETAT = "CALIBRATION"
H_cam_vers_proj = None

# Mémoire des positions et de la dernière image projetée
last_corners = {ID_HAUT_GAUCHE: None, ID_HAUT_DROITE: None, ID_BAS_GAUCHE: None, ID_BAS_DROITE: None}
last_projector_output = np.zeros((proj_h, proj_w, 3), dtype=np.uint8)
ALPHA = 0.15

while True:
    with state_lock:
        values = room_temperatures
        version = temperature_version
        selected = selected_room_id
        settings = calibration_settings
        context = projection_context
    if version != rendered_temperature_version:
        canvas = render_temperature_canvas(
            proj_w, proj_h,
            (zone_x_debut, y_debut, largeur_zone, hauteur_zone), values, selected, settings['showGuide'],
        )
        render_projection_info(canvas, values, selected, context)
        rendered_temperature_version = version
    ret, frame = cap.read()
    if not ret:
        frame = np.zeros((proj_h, proj_w, 3), dtype=np.uint8)
        cv2.putText(frame, 'CAMERA INDISPONIBLE - MODE MANUEL POSSIBLE', (30, 160), cv2.FONT_HERSHEY_SIMPLEX, .8, (0, 165, 255), 2)
    else:
        frame = cv2.undistort(frame, mtx, dist)

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, rejected = detector.detectMarkers(gray)

    if ids is not None:
        cv2.aruco.drawDetectedMarkers(frame, corners, ids)

    projector_output = np.zeros((proj_h, proj_w, 3), dtype=np.uint8)
    if settings['mode'] == 'manual':
        if settings['showGuide']:
            # Grille ancrée au plan, avec les quatre poignées dessinées APRÈS la déformation.
            source = np.array(settings.get('sourceCorners', [[0, 0], [1, 0], [1, 1], [0, 1]])) * [proj_w-1, proj_h-1]
            left, top = np.rint(source[0]).astype(int)
            right, bottom = np.rint(source[2]).astype(int)
            guided_canvas = np.maximum(canvas, calibration_plan)
            cv2.polylines(guided_canvas, [np.rint(source).astype(np.int32)], True, (0, 255, 255), 2)
        else:
            guided_canvas = canvas
        matrix = projection_matrix(settings, proj_w, proj_h)
        projector_output = cv2.warpPerspective(guided_canvas, matrix, (proj_w, proj_h))
        if settings['showGuide']:
            for point in settings['corners']:
                cv2.circle(projector_output, tuple(np.rint(np.array(point)*[proj_w-1, proj_h-1]).astype(int)), 15, (0, 0, 255), -1)
        cv2.putText(frame, 'CALIBRATION MANUELLE', (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    elif ETAT == "CALIBRATION":
        projector_output = projector_calib_screen
        cv2.putText(frame, "RECHERCHE ARUCO PROJETE (ID 0)...", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        if ids is not None:
            for i, marker_id in enumerate(ids.flatten()):
                if marker_id == 0:
                    pts_cam_calib = np.float32(corners[i][0])
                    H_cam_vers_proj = cv2.getPerspectiveTransform(pts_cam_calib, pts_proj_calib)
                    print("Calibration réussie ! Passage en mode TRACKING.")
                    ETAT = "TRACKING"
                    cv2.waitKey(1000)
                    break

    elif ETAT == "TRACKING":
        cv2.putText(frame, "TRACKING (GEOMETRIE PROJECTEUR)", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        if ids is not None:
            for i, marker_id in enumerate(ids.flatten()):
                if marker_id in last_corners:
                    raw = corners[i][0]
                    previous = last_corners[marker_id]
                    last_corners[marker_id] = raw if previous is None else ALPHA * raw + (1.0 - ALPHA) * previous

        physical_ids = (ID_HAUT_GAUCHE, ID_HAUT_DROITE, ID_BAS_DROITE, ID_BAS_GAUCHE)
        if all(last_corners[marker_id] is not None for marker_id in physical_ids):
            centers = np.float32([np.mean(last_corners[marker_id], axis=0) for marker_id in physical_ids])
            for center in centers:
                cv2.circle(frame, tuple(np.int32(center)), 5, (0, 255, 0), -1)
            pts_proj_physique_centers = cv2.perspectiveTransform(centers[None], H_cam_vers_proj)[0]
            demi = aruco_physique_size / 2.0
            pts_src_centers = np.float32([[x_hg + demi, y_hg + demi], [x_hd + demi, y_hd + demi],
                                          [x_bd + demi, y_bd + demi], [x_bg + demi, y_bg + demi]])
            matrix_finale = cv2.getPerspectiveTransform(pts_src_centers, pts_proj_physique_centers)
            with state_lock:
                automatic_matrix = matrix_finale
            projector_output = cv2.warpPerspective(canvas, projection_matrix(settings, proj_w, proj_h, matrix_finale), (proj_w, proj_h))
            last_projector_output = projector_output.copy()
        else:
            matrix = projection_matrix(settings, proj_w, proj_h, automatic_matrix)
            projector_output = cv2.warpPerspective(canvas, matrix, (proj_w, proj_h)) if matrix is not None else last_projector_output

        if last_corners[ID_HAUT_GAUCHE] is not None and last_corners[ID_BAS_DROITE] is not None:
            visible_ids = set() if ids is None else set(ids.flatten())
            if ID_HAUT_GAUCHE not in visible_ids or ID_BAS_DROITE not in visible_ids:
                cv2.putText(frame, "SIGNAL PERDU - MAINTIEN DERNIERE POSE", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)

    cv2.imshow('Interface PC', frame)
    cv2.imshow('Projecteur', projector_output)
    with state_lock:
        preview_frame = cv2.resize(projector_output, (960, 540))
        control_image = preview_frame.copy()
    if settings['mode'] == 'manual' and settings['showGuide']:
        for point in settings['corners']:
            cv2.circle(control_image, tuple(np.rint(np.array(point)*[959, 539]).astype(int)), 15, (0, 0, 255), -1)
    cv2.imshow('Controle PC', control_image)

    # Demande de recalibrage venue de la webapp (bouton "Calibrer")
    with state_lock:
        demande_web = calibration_requested
        calibration_requested = False

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'): break
    if key == ord('c') or demande_web:
        with state_lock:
            # Recalibrer bascule sur l'automatique mais conserve les ajustements.
            calibration_settings = automatic_settings
            settings_revision += 1
            automatic_matrix = None
        ETAT = "CALIBRATION"
        last_corners = {ID_HAUT_GAUCHE: None, ID_HAUT_DROITE: None, ID_BAS_GAUCHE: None, ID_BAS_DROITE: None}
        last_projector_output = np.zeros((proj_h, proj_w, 3), dtype=np.uint8)
        print("Relance de la calibration...")

cap.release()
cv2.destroyAllWindows()
