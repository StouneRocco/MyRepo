import cv2
import subprocess
import sys
import os
from ultralytics import YOLO


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_PATH = "yolo11n.pt"
VIDEOS_FOLDER = "videos"

CLASSES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


# ============================================================
# CHOIX DE LA SOURCE
# ============================================================

print()
print("==========================================")
print("      VEHICLE ENTRY DETECTION")
print("==========================================")
print()
print("1 - Vidéo locale")
print("2 - Live YouTube")
print()

choice = input("Choisissez la source (1/2) : ").strip()


# ============================================================
# VIDÉO LOCALE
# ============================================================

if choice == "1":

    if not os.path.exists(VIDEOS_FOLDER):
        raise RuntimeError(
            f"Le dossier '{VIDEOS_FOLDER}' n'existe pas."
        )

    video_files = [
        file
        for file in os.listdir(VIDEOS_FOLDER)
        if file.lower().endswith(
            (".mp4", ".avi", ".mov", ".mkv", ".webm")
        )
    ]

    if not video_files:
        raise RuntimeError(
            f"Aucune vidéo trouvée dans '{VIDEOS_FOLDER}'."
        )

    print()
    print("Vidéos disponibles :")
    print()

    for i, video in enumerate(video_files, start=1):
        print(f"{i} - {video}")

    print()

    try:
        video_choice = int(
            input("Choisissez une vidéo : ")
        )

        if video_choice < 1 or video_choice > len(video_files):
            raise ValueError

    except ValueError:
        raise RuntimeError(
            "Choix de vidéo invalide."
        )

    selected_video = video_files[video_choice - 1]

    VIDEO_SOURCE = os.path.join(
        VIDEOS_FOLDER,
        selected_video
    )

    print()
    print(f"Vidéo sélectionnée : {VIDEO_SOURCE}")

    WINDOW_TITLE = "Vehicle Detection - Video"


# ============================================================
# LIVE YOUTUBE
# ============================================================

elif choice == "2":

    YOUTUBE_URL = input(
        "\nEntrez l'URL du live YouTube : "
    ).strip()

    if not YOUTUBE_URL:
        raise RuntimeError(
            "Aucune URL YouTube fournie."
        )

    print()
    print("Récupération du flux YouTube...")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "yt_dlp",
            "-g",
            YOUTUBE_URL,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError(
            "Impossible de récupérer le flux YouTube."
        )

    urls = result.stdout.strip().splitlines()

    if not urls:
        raise RuntimeError(
            "Aucun flux vidéo trouvé."
        )

    VIDEO_SOURCE = urls[0]

    print("Flux YouTube récupéré.")

    WINDOW_TITLE = "Vehicle Detection - YouTube Live"


# ============================================================
# MAUVAIS CHOIX
# ============================================================

else:

    raise RuntimeError(
        "Choix invalide. Utilisez 1 ou 2."
    )


# ============================================================
# CHARGEMENT DU MODÈLE YOLO
# ============================================================

print()
print("Chargement du modèle YOLO...")

model = YOLO(MODEL_PATH)

print("Modèle chargé.")


# ============================================================
# OUVERTURE DE LA SOURCE
# ============================================================

print("Ouverture de la source vidéo...")

cap = cv2.VideoCapture(VIDEO_SOURCE)

if not cap.isOpened():
    raise RuntimeError(
        f"Impossible d'ouvrir la source : {VIDEO_SOURCE}"
    )

# Réduit le buffer pour limiter le retard
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

print("Vidéo ouverte.")
print()
print("Appuyez sur ESC pour quitter.")
print()


# ============================================================
# BOUCLE DE TRAITEMENT
# ============================================================

frame_count = 0
annotated_frame = None

while True:

    ret, frame = cap.read()

    if not ret:

        if choice == "1":
            print("Fin de la vidéo.")
            break

        else:
            print("Flux vidéo interrompu.")
            break

    frame_count += 1

    # ========================================================
    # REDIMENSIONNEMENT
    # ========================================================

    frame = cv2.resize(
        frame,
        (1280, 720)
    )

    # ========================================================
    # YOLO
    #
    # Détection toutes les 3 images
    # pour améliorer les performances.
    # ========================================================

    if frame_count % 3 == 0:

        results = model.track(
            frame,
            persist=True,
            classes=list(CLASSES.keys()),
            verbose=False,
            imgsz=640,
            conf=0.4,
        )

        result = results[0]

        annotated_frame = result.plot()

        # ====================================================
        # INFORMATIONS SUR LES OBJETS
        # ====================================================

        if result.boxes is not None:

            for box in result.boxes:

                class_id = int(box.cls[0])

                if class_id not in CLASSES:
                    continue

                object_type = CLASSES[class_id]

                confidence = float(
                    box.conf[0]
                )

                object_id = None

                if box.id is not None:
                    object_id = int(
                        box.id[0]
                    )

                x1, y1, x2, y2 = map(
                    int,
                    box.xyxy[0]
                )

                print(
                    f"ID={object_id} "
                    f"type={object_type} "
                    f"confidence={confidence:.2f} "
                    f"position="
                    f"({x1},{y1},{x2},{y2})"
                )

    # ========================================================
    # AFFICHAGE
    # ========================================================

    if annotated_frame is not None:
        display_frame = annotated_frame
    else:
        display_frame = frame

    cv2.imshow(
        WINDOW_TITLE,
        display_frame
    )

    # ========================================================
    # ESC POUR QUITTER
    # ========================================================

    if cv2.waitKey(1) & 0xFF == 27:
        break


# ============================================================
# NETTOYAGE
# ============================================================

cap.release()
cv2.destroyAllWindows()

print()
print("Programme terminé.")