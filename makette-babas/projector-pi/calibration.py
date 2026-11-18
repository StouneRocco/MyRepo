import os
import cv2
import numpy as np

# ==========================================
# 1. CONFIGURATION DE TON DAMIER PHYSIQUE
# ==========================================
# Renseigne ici le nombre de coins internes (intersections) de ton damier
colonnes = 10  # <-- À adapter selon ton impression
lignes = 7    # <-- À adapter selon ton impression

# Préparation des points 3D mathématiques parfaits
objp = np.zeros((lignes * colonnes, 3), np.float32)
objp[:, :2] = np.mgrid[0:colonnes, 0:lignes].T.reshape(-1, 2)

objpoints = [] # Stocke les points 3D réels
imgpoints = [] # Stocke les points 2D vus par la caméra (déformés)

# Initialisation de la caméra dans la MÊME résolution que ton projet final
camera_index = int(os.getenv("CAMERA_INDEX", "0" if os.name == "nt" else "4"))
cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_V4L2)
if not cap.isOpened():
    raise RuntimeError(f"Caméra {camera_index} indisponible. Vérifie CAMERA_INDEX.")
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

print("--- MODE CALIBRATION LENTILLE ---")
print("- Bouge le damier devant la caméra (proche, loin, sur les bords, penché).")
print("- Appuie sur [ESPACE] pour valider une capture (vise 15 à 20 captures variées).")
print("- Appuie sur [C] pour lancer le calcul matriciel.")

captures = 0

while True:
    ret, frame = cap.read()
    if not ret: break
    
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Recherche des coins
    ret_corners, corners = cv2.findChessboardCorners(gray, (colonnes, lignes), None)
    frame_display = frame.copy()
    
    if ret_corners:
        # Affinage subpixel pour une précision extrême
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners_subpix = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        
        cv2.drawChessboardCorners(frame_display, (colonnes, lignes), corners_subpix, ret_corners)
        cv2.putText(frame_display, "DAMIER OK -> ESPACE pour capturer", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    else:
        cv2.putText(frame_display, "Recherche du damier...", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
    cv2.putText(frame_display, f"Captures : {captures}/20", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
    cv2.imshow('Calibration', frame_display)
    
    key = cv2.waitKey(1) & 0xFF
    if key == 27 or key == ord('q'): 
        break
    elif key == 32 and ret_corners: # Touche ESPACE
        objpoints.append(objp)
        imgpoints.append(corners_subpix)
        captures += 1
        print(f"Capture {captures} enregistrée !")
        
    elif key == ord('c') and captures > 10:
        print("\nCalcul de la distorsion en cours...")
        ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)
        
        print("\n=== COORDONNÉES OPTIQUES DE TA CAMÉRA ===")
        print("mtx = np.array(" + repr(mtx.tolist()) + ", dtype=np.float32)")
        print("dist = np.array(" + repr(dist.tolist()) + ", dtype=np.float32)")
        print("=========================================\n")
        break

cap.release()
cv2.destroyAllWindows()
