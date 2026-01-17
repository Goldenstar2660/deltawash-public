"""CNN-only inference server with live video feed.

Uses the CNN model as the single source of truth for hand wash step recognition.
MediaPipe has been completely eliminated.
"""

import numpy as np
import cv2
from flask import Flask, Response
from picamera2 import Picamera2

# --- IMPORT CNN-ONLY ENGINE ---
from inference_script import DeltaWashEngine, CLASSES

app = Flask(__name__)

# 1. Initialize Picamera2
picam2 = Picamera2()
config = picam2.create_video_configuration(main={"size": (640, 480), "format": "RGB888"})
picam2.configure(config)
picam2.start()

# 2. Initialize CNN-Only Engine
engine = DeltaWashEngine(cnn_path="cnn_model.pth")

def generate_frames():
    while True:
        frame_rgb = picam2.capture_array()
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        
        try:
            # Get predictions from CNN-only engine
            lbl, conf, _, status, cnn_p, _ = engine.predict(frame_bgr, True)
            
            # --- HUD DRAWING ---
            # 1. Main CNN Result (Top Left)
            color = (0, 255, 0) if lbl != "Background" else (200, 200, 200)
            cv2.rectangle(frame_bgr, (5, 5), (320, 100), (0,0,0), -1)
            cv2.putText(frame_bgr, f"STEP: {lbl}", (15, 40), 1, 2, color, 2)
            cv2.putText(frame_bgr, f"CONF: {conf:.0%}", (15, 80), 1, 1.5, (255,255,255), 2)

            # 2. CNN Breakdown (Right Side)
            cnn_idx = np.argmax(cnn_p)
            cnn_label = CLASSES[cnn_idx]
            cnn_conf = cnn_p[cnn_idx]

            # Draw debug overlay
            cv2.rectangle(frame_bgr, (350, 5), (635, 80), (50, 50, 50), -1)
            cv2.putText(frame_bgr, f"CNN: {cnn_label}", (360, 35), 1, 1, (0, 255, 255), 1)
            cv2.putText(frame_bgr, f"     ({cnn_conf:.0%})", (360, 55), 1, 1, (0, 255, 255), 1)

            # Status (Bottom)
            cv2.putText(frame_bgr, f"MODE: {status}", (15, 460), 1, 1, (255, 255, 255), 1)

        except Exception as e:
            cv2.putText(frame_bgr, f"Engine Error: {e}", (10, 40), 1, 1, (0, 0, 255), 2)

        # --- ENCODE ---
        ret, buffer = cv2.imencode('.jpg', frame_bgr)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    return """
    <html>
        <body style="background:#111; color:white; text-align:center; font-family:sans-serif;">
            <h1>WHO Hand Wash AI: CNN-Only Model</h1>
            <img src="/video" style="border:4px solid #333; width:85%;">
            <div style="margin-top:10px;">
                <span style="color:#0FF;">Single Source of Truth: MobileNetV3 CNN</span>
            </div>
        </body>
    </html>
    """

@app.route('/video')
def video():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    try:
        app.run(host='0.0.0.0', port=5000, threaded=True)
    finally:
        picam2.stop()
