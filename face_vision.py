import os
os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"

import time
import json
import sqlite3
import datetime
import threading
from typing import Dict, Any, List, Optional

class FaceVisionEngine:
    def __init__(self, db_path: str = "lisa_memory.db"):
        self.db_path = db_path
        self.sentry_active = False
        self.sentry_thread: Optional[threading.Thread] = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS enrolled_faces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_name TEXT NOT NULL UNIQUE,
                    enrolled_at TEXT NOT NULL,
                    encoding_json TEXT NOT NULL
                )
            """)
            conn.commit()

    def capture_webcam_frame(self, index: Optional[int] = None):
        """Captures a single high-quality BGR frame from webcam cleanly without MSMF conflicts."""
        try:
            import cv2
            indices_to_try = [0, 1] if index is None else [index]
            backends = [cv2.CAP_DSHOW, cv2.CAP_ANY] if os.name == 'nt' else [cv2.CAP_ANY]
            
            for idx in indices_to_try:
                for backend in backends:
                    cap = None
                    try:
                        cap = cv2.VideoCapture(idx, backend)
                        if not cap.isOpened():
                            if cap is not None: cap.release()
                            continue
                        
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                        
                        frame = None
                        for _ in range(5):
                            ret, f = cap.read()
                            if ret and f is not None:
                                frame = f
                            time.sleep(0.03)
                            
                        cap.release()
                        if frame is not None and frame.size > 0:
                            return frame
                    except Exception:
                        if cap is not None:
                            try: cap.release()
                            except Exception: pass
        except Exception as e:
            print(f"[FaceVision Error capturing frame]: {e}")
        return None

    def check_camera_health(self) -> Dict[str, Any]:
        """Test and verify webcam hardware accessibility and resolution."""
        frame = self.capture_webcam_frame()
        if frame is None:
            return {
                "status": "unavailable",
                "accessible": False,
                "message": "Webcam could not be opened. Please verify that your camera is plugged in and permissions are granted."
            }
        h, w, c = frame.shape
        return {
            "status": "healthy",
            "accessible": True,
            "resolution": f"{w}x{h}",
            "channels": c,
            "message": f"Webcam is fully operational and accessible ({w}x{h})."
        }

    def analyze_scene(self, prompt: str = "Describe what you see in front of the camera in detail.", frame=None) -> Dict[str, Any]:
        """
        Captures a live frame and analyzes it using Gemini Multimodal Vision.
        """
        if frame is None:
            frame = self.capture_webcam_frame()

        if frame is None:
            return {
                "status": "error",
                "message": "Camera is currently unavailable or could not be accessed. Please ensure no other app is locking the webcam."
            }

        try:
            import cv2
            import io
            from PIL import Image
            import config
            from google import genai
            from google.genai import types

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)
            buf = io.BytesIO()
            pil_img.save(buf, format='JPEG', quality=90)
            jpeg_bytes = buf.getvalue()

            client = genai.Client(api_key=config.GEMINI_API_KEY)
            res = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=[
                    types.Part.from_bytes(data=jpeg_bytes, mime_type='image/jpeg'),
                    f"You are Lisa, an observant, warm personal AI companion. Look at this live webcam capture and answer the following request accurately and conversationally:\nRequest: {prompt}"
                ]
            )

            return {
                "status": "success",
                "analysis": res.text.strip(),
                "resolution": f"{frame.shape[1]}x{frame.shape[0]}"
            }
        except Exception as e:
            return {"status": "error", "message": f"Vision analysis failed: {str(e)}"}


    def enroll_user(self, user_name: str, frame=None) -> Dict[str, Any]:
        """
        Enrolls a new user face into Lisa's biometric database.
        """
        if frame is None:
            frame = self.capture_webcam_frame()

        if frame is None:
            return {"status": "error", "message": "Failed to capture webcam frame for face enrollment. Ensure camera is connected."}

        try:
            import cv2
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Detect face
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(60, 60))

            if len(faces) == 0:
                return {"status": "error", "message": "No face detected in the camera frame. Please look directly at the webcam and try again."}

            x, y, w, h = faces[0]
            face_roi = cv2.resize(gray[y:y+h, x:x+w], (100, 100))
            # Create a normalized histogram feature vector
            hist = cv2.calcHist([face_roi], [0], None, [32], [0, 256])
            cv2.normalize(hist, hist)
            encoding = hist.flatten().tolist()

            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO enrolled_faces (user_name, enrolled_at, encoding_json)
                    VALUES (?, ?, ?)
                """, (user_name, now, json.dumps(encoding)))
                conn.commit()

            return {
                "status": "success",
                "user_name": user_name,
                "face_box": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
                "message": f"Successfully enrolled face profile for '{user_name}'!"
            }

        except Exception as e:
            return {"status": "error", "message": f"Face enrollment failed: {str(e)}"}

    def identify_face(self, frame=None) -> Dict[str, Any]:
        """
        Scans webcam and matches detected face against enrolled profiles.
        """
        if frame is None:
            frame = self.capture_webcam_frame()

        if frame is None:
            return {"status": "error", "message": "Webcam unavailable."}

        try:
            import cv2
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(60, 60))

            if len(faces) == 0:
                return {"status": "no_face", "message": "No face visible in front of the camera."}

            x, y, w, h = faces[0]
            face_roi = cv2.resize(gray[y:y+h, x:x+w], (100, 100))
            hist = cv2.calcHist([face_roi], [0], None, [32], [0, 256])
            cv2.normalize(hist, hist)
            curr_encoding = hist.flatten().tolist()

            # Retrieve enrolled faces
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_name, encoding_json FROM enrolled_faces")
                enrolled = cursor.fetchall()

            if not enrolled:
                return {
                    "status": "unregistered",
                    "face_detected": True,
                    "face_box": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
                    "message": "Face detected, but no users are enrolled in memory yet. Use enroll_user_face to register."
                }

            best_match = None
            best_score = 0.0

            import numpy as np
            curr_arr = np.array(curr_encoding, dtype=np.float32)

            for name, enc_str in enrolled:
                target_arr = np.array(json.loads(enc_str), dtype=np.float32)
                # Correlation comparison
                score = cv2.compareHist(curr_arr, target_arr, cv2.HISTCMP_CORREL)
                if score > best_score:
                    best_score = score
                    best_match = name

            if best_score > 0.70:
                return {
                    "status": "recognized",
                    "user_name": best_match,
                    "confidence": round(float(best_score), 2),
                    "face_box": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
                    "message": f"Recognized {best_match} (confidence {int(best_score * 100)}%)."
                }
            else:
                return {
                    "status": "unknown",
                    "confidence": round(float(best_score), 2),
                    "face_box": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
                    "message": "Unknown face detected. Identity could not be verified."
                }

        except Exception as e:
            return {"status": "error", "message": f"Face identification error: {str(e)}"}

    def detect_user_facial_emotion(self, frame=None) -> Dict[str, Any]:
        """
        Scans webcam and analyzes the user's facial expression and emotional mood
        (e.g., happy/smiling, tired/fatigued, focused, stressed, neutral).
        """
        if frame is None:
            frame = self.capture_webcam_frame()

        if frame is None:
            return {"status": "error", "message": "Webcam unavailable for emotion analysis."}

        try:
            import cv2
            import numpy as np
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            smile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_smile.xml')
            eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(60, 60))
            if len(faces) == 0:
                return {"status": "no_face", "message": "No face detected in front of the camera."}

            x, y, w, h = faces[0]
            roi_gray = gray[y:y+h, x:x+w]

            # Detect smiles and eyes
            smiles = smile_cascade.detectMultiScale(roi_gray, scaleFactor=1.7, minNeighbors=20, minSize=(25, 25))
            eyes = eye_cascade.detectMultiScale(roi_gray, scaleFactor=1.1, minNeighbors=5, minSize=(20, 20))

            # Calculate facial metrics
            brightness = float(np.mean(roi_gray))
            contrast = float(np.std(roi_gray))

            detected_emotion = "neutral"
            confidence = 0.85
            notes = "User appears calm and attentive."

            if len(smiles) > 0:
                detected_emotion = "happy"
                confidence = 0.92
                notes = "User is smiling and appears cheerful!"
            elif len(eyes) < 2 and brightness < 80:
                detected_emotion = "tired"
                confidence = 0.82
                notes = "User's eyes appear partially closed or fatigued. May need a quick break or rest."
            elif contrast > 55:
                detected_emotion = "focused"
                confidence = 0.88
                notes = "User has sharp focus and deep concentration."
            else:
                detected_emotion = "neutral"
                notes = "User maintains a relaxed, neutral expression."

            return {
                "status": "success",
                "emotion": detected_emotion,
                "confidence": confidence,
                "notes": notes,
                "eyes_detected": len(eyes),
                "smile_detected": len(smiles) > 0,
                "message": f"User's facial emotion detected as '{detected_emotion.capitalize()}'. {notes}"
            }
        except Exception as e:
            return {"status": "error", "message": f"Emotion detection failed: {str(e)}"}

    def toggle_sentry_mode(self, enable: bool = True) -> Dict[str, Any]:
        """
        Activates or deactivates autonomous sentry patrol mode.
        """
        if enable:
            if self.sentry_active:
                return {"status": "already_running", "message": "Sentry mode is already active."}
            self.sentry_active = True
            self.sentry_thread = threading.Thread(target=self._sentry_loop, daemon=True)
            self.sentry_thread.start()
            return {"status": "active", "message": "🛡️ Sentry Patrol activated. Lisa is monitoring for unfamiliar faces."}
        else:
            self.sentry_active = False
            return {"status": "disabled", "message": "Sentry Patrol deactivated."}

    def _sentry_loop(self):
        last_alert_time = 0
        while self.sentry_active:
            time.sleep(10)
            now = time.time()
            if now - last_alert_time < 60:
                continue

            res = self.identify_face()
            if res.get("status") == "unknown":
                last_alert_time = now
                alert_msg = "Intruder Alert: An unidentified individual is in front of your workstation!"
                print(f"\n[Lisa Sentry]: {alert_msg}\n")
                
                # Proactive dispatch
                try:
                    from cron_monitor import cron_engine
                    cron_engine._dispatch_alert(alert_msg, channel="all")
                except Exception:
                    pass

face_vision_engine = FaceVisionEngine()

if __name__ == "__main__":
    print("Testing Face Vision Engine...")
    print("Capturing and scanning face:", face_vision_engine.identify_face())
