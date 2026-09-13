"""
Floating Desktop Active Live Ethereal Silk Plasma Nebula for Lisa AI.
Renders an organic, luminous fluid flame / quantum silk nebula (Cortana-style)
with anti-aliased translucent flowing ribbons, electric blue/violet gradients, and audio responsiveness.

"""

import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import math
import time
import json
import threading
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk, ImageFilter

class LisaQuantumNebulaOrb:
    def __init__(self, size: int = 100):
        self.size = size
        self.center = size // 2
        
        # State Variables
        self.current_state = "idle"         # 'idle', 'listening', 'thinking', 'speaking'
        self.current_emotion = "caring"     # Default bright electric cyan/blue
        self.audio_energy = 0.0
        self.anim_time = 0.0
        self.is_dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.photo_img = None

        # 1. Setup Windows DWM Transparent Frameless Window
        self.root = tk.Tk()
        self.root.title("Lisa Quantum Nebula")
        self.root.overrideredirect(True)       # Frameless
        self.root.attributes("-topmost", True)  # Always on top across all apps

        # 100% Native Windows DWM Transparent Color Key
        self.transparent_key = "#010101"
        self.root.config(bg=self.transparent_key)
        try:
            self.root.wm_attributes("-transparentcolor", self.transparent_key)
        except Exception:
            pass

        # Position at bottom-right corner
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{self.size}x{self.size}+{sw - self.size - 25}+{sh - self.size - 65}")

        # Canvas with zero borders and transparent key background
        self.canvas = tk.Canvas(
            self.root,
            width=self.size,
            height=self.size,
            bg=self.transparent_key,
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(fill="both", expand=True)

        # Event Bindings
        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<Button-3>", self._show_context_menu)
        self.canvas.bind("<Double-Button-1>", lambda e: self._trigger_voice())

        # Context Menu
        self.menu = tk.Menu(self.root, tearoff=0, bg="#0d1117", fg="#f0f6fc", activebackground="#0077ff")
        self.menu.add_command(label="⚡ Mood: Electric Cyan", command=lambda: self.set_emotion("caring"))
        self.menu.add_command(label="💖 Mood: Neon Magenta", command=lambda: self.set_emotion("affectionate"))
        self.menu.add_command(label="✨ Mood: Radiant Gold", command=lambda: self.set_emotion("playful"))
        self.menu.add_command(label="🌐 Mood: Deep Cobalt", command=lambda: self.set_emotion("tactical"))
        self.menu.add_separator()
        self.menu.add_command(label="🎙️ Speak to Lisa", command=self._trigger_voice)
        self.menu.add_command(label="📌 Reset Position", command=self._reset_position)
        self.menu.add_command(label="✖ Exit Widget", command=self.root.destroy)

        # Background WebSocket Listener
        self._start_ws_thread()

        # Start 60 FPS Render Loop
        self._render_loop()

    def _on_mouse_down(self, event):
        self.is_dragging = True
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def _on_mouse_drag(self, event):
        if self.is_dragging:
            cur_x = self.root.winfo_x()
            cur_y = self.root.winfo_y()
            dx = event.x - self.drag_start_x
            dy = event.y - self.drag_start_y
            self.root.geometry(f"+{cur_x + dx}+{cur_y + dy}")

    def _on_mouse_up(self, event):
        self.is_dragging = False

    def _show_context_menu(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _reset_position(self):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{self.size}x{self.size}+{sw - self.size - 25}+{sh - self.size - 65}")

    def _trigger_voice(self):
        self.current_state = "listening"
        from orb_bridge import update_orb_state
        update_orb_state("listening")

        def _send_request():
            try:
                import urllib.request
                req = urllib.request.Request(
                    "http://127.0.0.1:8000/api/chat",
                    data=json.dumps({"message": "Hello Lisa"}).encode(),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=1.5) as response:
                    pass
            except Exception:
                # Avatar web server is not active; fallback cleanly without error
                pass

        threading.Thread(target=_send_request, daemon=True).start()

    def set_emotion(self, emo: str):
        self.current_emotion = emo
        try:
            from tools import registry
            if 'set_lisa_facial_expression' in registry.tools:
                registry.tools['set_lisa_facial_expression'](expression=emo)
        except Exception:
            pass

    def _start_ws_thread(self):
        def _sync_loop():
            from orb_bridge import get_orb_state
            while True:
                try:
                    # Sync directly from local state bridge
                    state_data = get_orb_state()
                    if state_data:
                        self.current_state = state_data.get("state", "idle")
                        if state_data.get("emotion"):
                            self.current_emotion = state_data["emotion"]
                        if state_data.get("energy"):
                            self.audio_energy = float(state_data["energy"])
                except Exception:
                    pass
                time.sleep(0.08) # 80ms poll for instant responsive chat tracking

        threading.Thread(target=_sync_loop, daemon=True).start()

    def _render_loop(self):
        self.anim_time += 0.045
        t = self.anim_time
        cx, cy = self.center, self.center

        # Create 100% transparent frame (Zero background box)
        img = Image.new("RGBA", (self.size, self.size), (1, 1, 1, 0))
        draw = ImageDraw.Draw(img)

        # Ultra-Vibrant Electric Color Palettes
        emotion_schemes = {
            "caring": {
                "mid":    (0, 140, 255),   # Electric Vivid Blue
                "high":   (0, 230, 255),   # Neon Laser Cyan
                "core":   (235, 252, 255), # Luminous White-Cyan Star
                "fringe": (255, 255, 255)  # Crisp Specular Light
            },
            "tactical": {
                "mid":    (0, 90, 255),    # Deep Cobalt Blue
                "high":   (0, 200, 255),   # Bright Sky Blue
                "core":   (210, 245, 255), # Luminous Core
                "fringe": (100, 255, 230)
            },
            "affectionate": {
                "mid":    (255, 30, 130),  # Neon Pink
                "high":   (170, 80, 255),  # Vivid Violet
                "core":   (255, 235, 250),
                "fringe": (255, 255, 255)
            },
            "playful": {
                "mid":    (255, 150, 0),   # Radiant Gold
                "high":   (255, 40, 140),  # Hot Magenta
                "core":   (255, 245, 230),
                "fringe": (255, 255, 255)
            }
        }
        scheme = emotion_schemes.get(self.current_emotion, emotion_schemes["caring"])

        # Speed and Energy Modulation
        speed = 1.0
        energy_scale = 1.0
        if self.current_state == "idle":
            speed = 1.0
            energy_scale = 1.0 + math.sin(t * 1.8) * 0.08
        elif self.current_state == "listening":
            speed = 2.4
            energy_scale = 1.25 + math.sin(t * 6.0) * 0.15
        elif self.current_state == "thinking":
            speed = 3.2
            energy_scale = 1.18
        elif self.current_state == "speaking":
            speed = 2.0
            energy_scale = 1.15 + (self.audio_energy * 0.45)

        # -------------------------------------------------------------
        # 1. Multi-Layer Luminous Silk Petal Sheets (Cortana Vortex)
        # -------------------------------------------------------------
        num_petals = 13
        mid_col = scheme["mid"]
        high_col = scheme["high"]
        fringe_col = scheme["fringe"]
        core_col = scheme["core"]

        for p_idx in range(num_petals):
            # Phase-offset base angle for layered vortex formation
            base_angle = (p_idx * (2.0 * math.pi / num_petals)) + (t * 0.28 * speed)
            
            left_pts = []
            right_pts = []
            crest_pts = []

            steps = 18
            for s in range(steps):
                norm = s / float(steps - 1) # 0.0 to 1.0 (from center to tip)
                dist = 3 + (norm * 34 * energy_scale)

                # Complex organic zero-gravity silk folding
                fold1 = math.sin(norm * 3.4 - (t * 1.2 * speed) + p_idx * 0.9) * 0.72
                fold2 = math.cos(norm * 2.8 + (t * 0.8 * speed) + p_idx * 1.4) * 0.42
                cur_angle = base_angle + fold1 + fold2

                # Translucent ribbon sheet thickness profile
                sheet_w = math.sin(math.pow(norm, 0.8) * math.pi) * 10.5 * energy_scale

                px = cx + math.cos(cur_angle) * dist
                py = cy + math.sin(cur_angle) * (dist * 0.95)

                # Ribbon normal vector
                nx = -math.sin(cur_angle) * sheet_w
                ny = math.cos(cur_angle) * sheet_w

                left_pts.append((px + nx, py + ny))
                right_pts.insert(0, (px - nx, py - ny))
                crest_pts.append((px + nx * 0.9, py + ny * 0.9))

            sheet_polygon = left_pts + right_pts

            if len(sheet_polygon) > 6:
                # Alternate between electric blue and bright cyan
                if p_idx % 2 == 0:
                    col = mid_col
                    alpha = int(95 * (0.85 + energy_scale * 0.15))
                else:
                    col = high_col
                    alpha = int(115 * (0.85 + energy_scale * 0.15))

                # Draw Translucent Silk Sheet
                draw.polygon(sheet_polygon, fill=(col[0], col[1], col[2], alpha))

                # Draw Glowing Electric Silk Edge Crest Highlight
                draw.line(left_pts, fill=(fringe_col[0], fringe_col[1], fringe_col[2], 220), width=2)
                draw.line(crest_pts, fill=(255, 255, 255, 180), width=1)

        # -------------------------------------------------------------
        # 3. Inner Swirling Radiant Filaments
        # -------------------------------------------------------------
        for f_idx in range(5):
            f_angle = (f_idx * (2.0 * math.pi / 5.0)) - (t * 0.45 * speed)
            f_pts = []
            for s in range(15):
                norm = s / 14.0
                dist = 2 + norm * 24 * energy_scale
                swirl = math.sin(norm * 4.2 + (t * 1.8 * speed) + f_idx) * 0.6
                px = cx + math.cos(f_angle + swirl) * dist
                py = cy + math.sin(f_angle + swirl) * (dist * 0.9)
                f_pts.append((int(px), int(py)))

            if len(f_pts) > 3:
                draw.line(f_pts, fill=(core_col[0], core_col[1], core_col[2], 210), width=2)
                draw.line(f_pts, fill=(fringe_col[0], fringe_col[1], fringe_col[2], 160), width=1)

        # -------------------------------------------------------------
        # 4. Central Radiant Quantum Energy Core
        # -------------------------------------------------------------
        core_r = int((11 + math.sin(t * 3.0 * speed) * 2.0) * energy_scale)

        # Inner illuminating glow radiating through sheets
        for cr in range(core_r + 8, 3, -2):
            c_alpha = int(180 * (1.0 - (cr / (core_r + 8))))
            draw.ellipse(
                (cx - cr, cy - cr, cx + cr, cy + cr),
                fill=(high_col[0], high_col[1], high_col[2], c_alpha)
            )

        # Intense bright core
        draw.ellipse(
            (cx - core_r // 2, cy - core_r // 2, cx + core_r // 2, cy + core_r // 2),
            fill=(core_col[0], core_col[1], core_col[2], 255)
        )

        # Pure white center star highlight
        draw.ellipse(
            (cx - 2, cy - 2, cx + 2, cy + 2),
            fill=(255, 255, 255, 255)
        )

        # Smooth optical silk bloom filter
        img = img.filter(ImageFilter.GaussianBlur(radius=0.6))

        # 2. Convert to ImageTk and update canvas
        self.photo_img = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo_img)

        # Schedule Next Frame (~60 FPS)
        self.root.after(16, self._render_loop)

    def run(self):
        print("✓ [Lisa Quantum Silk Nebula]: Active live floating plasma flame.")
        self.root.mainloop()

def launch_desktop_orb():
    orb = LisaQuantumNebulaOrb(size=100)
    orb.run()

if __name__ == "__main__":
    launch_desktop_orb()
