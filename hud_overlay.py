"""
Floating Translucent HUD & Screen Annotation Overlay for Lisa AI.
Renders transparent, click-through bounding boxes, spotlight arrows,
and cyberpunk HUD notification banners directly on top of the user's desktop.
"""

import time
import threading
import tkinter as tk
from typing import Optional

class HUDOverlayManager:
    def __init__(self):
        self.root: Optional[tk.Tk] = None
        self.canvas: Optional[tk.Canvas] = None
        self.is_ready = False
        self.annotations = []
        self._thread: Optional[threading.Thread] = None

    def _init_gui(self):
        try:
            self.root = tk.Tk()
            self.root.title("Lisa HUD Overlay")
            self.root.attributes("-topmost", True)
            self.root.attributes("-alpha", 0.88)
            self.root.overrideredirect(True) # Frameless

            # Full screen geometry
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            self.root.geometry(f"{screen_width}x{screen_height}+0+0")

            # Transparent background
            self.root.config(bg="#050811")
            try:
                self.root.wm_attributes("-transparentcolor", "#050811")
            except Exception:
                pass

            self.canvas = tk.Canvas(
                self.root,
                width=screen_width,
                height=screen_height,
                bg="#050811",
                highlightthickness=0
            )
            self.canvas.pack(fill="both", expand=True)
            self.is_ready = True
            self.root.mainloop()
        except Exception as e:
            print(f"[HUDOverlay Error in GUI loop]: {e}")

    def ensure_running(self):
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._init_gui, daemon=True)
            self._thread.start()
            # Wait for ready
            for _ in range(20):
                if self.is_ready and self.root and self.canvas:
                    break
                time.sleep(0.05)

    def show_banner(self, text: str, duration_seconds: int = 4, color: str = "#00f2fe"):
        self.ensure_running()
        if not self.root or not self.canvas:
            return {"status": "error", "message": "HUD canvas not initialized."}

        def _draw():
            try:
                self.canvas.delete("banner")
                sw = self.root.winfo_screenwidth()
                # Draw sleek HUD top pill banner
                bx, by, bw, bh = (sw // 2) - 250, 24, 500, 48
                self.canvas.create_rectangle(
                    bx, by, bx + bw, by + bh,
                    fill="#0d1117", outline=color, width=2,
                    tags="banner"
                )
                self.canvas.create_text(
                    sw // 2, by + 24,
                    text=f"✦ LISA HUD: {text}",
                    fill=color, font=("Consolas", 12, "bold"),
                    tags="banner"
                )
                # Schedule auto clear
                self.root.after(int(duration_seconds * 1000), lambda: self.canvas.delete("banner"))
            except Exception as e:
                print(f"[HUD Banner draw error]: {e}")

        self.root.after(0, _draw)
        return {"status": "success", "message": f"Displayed HUD banner: '{text}'"}

    def highlight_region(self, x: int, y: int, width: int, height: int, 
                         label: str = "", color: str = "#00f2fe", duration_seconds: int = 6):
        self.ensure_running()
        if not self.root or not self.canvas:
            return {"status": "error", "message": "HUD canvas not initialized."}

        tag_name = f"box_{int(time.time() * 1000)}"

        def _draw():
            try:
                # Neon bounding box
                self.canvas.create_rectangle(
                    x, y, x + width, y + height,
                    outline=color, width=3, tags=tag_name
                )
                # Outer glow border
                self.canvas.create_rectangle(
                    x - 2, y - 2, x + width + 2, y + height + 2,
                    outline="#ffffff", width=1, tags=tag_name
                )
                if label:
                    # Label badge
                    self.canvas.create_rectangle(
                        x, y - 24, x + len(label) * 9 + 16, y,
                        fill="#0d1117", outline=color, width=1, tags=tag_name
                    )
                    self.canvas.create_text(
                        x + 8, y - 12,
                        text=label, fill=color, font=("Consolas", 10, "bold"),
                        anchor="w", tags=tag_name
                    )

                self.root.after(int(duration_seconds * 1000), lambda: self.canvas.delete(tag_name))
            except Exception as e:
                print(f"[HUD Box draw error]: {e}")

        self.root.after(0, _draw)
        return {
            "status": "success",
            "coords": {"x": x, "y": y, "width": width, "height": height},
            "label": label,
            "duration": duration_seconds,
            "message": f"Highlighted screen region ({x}, {y}, {width}x{height}) on HUD."
        }

    def clear_all(self):
        if self.root and self.canvas:
            self.root.after(0, lambda: self.canvas.delete("all"))
        return {"status": "success", "message": "HUD screen annotations cleared."}

hud_overlay = HUDOverlayManager()

if __name__ == "__main__":
    print("Testing HUD Overlay...")
    hud_overlay.show_banner("Tactical Target Identified", duration_seconds=3)
    hud_overlay.highlight_region(200, 200, 300, 200, label="Target Window", duration_seconds=5)
    time.sleep(6)
