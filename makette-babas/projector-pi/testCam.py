import os
import cv2

for i in range(40):
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_V4L2)
    if cap.isOpened():
        ret, frame = cap.read()
        print(f"/dev/video{i} -> OK, frame shape: {frame.shape if ret else 'None'}")
        cap.release()
    else:
        print(f"/dev/video{i} -> indisponible")
