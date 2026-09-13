import os
import json
import sqlite3
import datetime
import urllib.request
import urllib.parse
from typing import Callable, Dict, Any, List, Optional
from preferences import preference_manager

class ToolRegistry:
    """
    Central registry for Lisa's tools / function calling capabilities.
    Allows registering, schema generation, and safe execution.
    """
    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.schemas: List[Dict[str, Any]] = []

    def register(self, name: str, description: str, parameters: Dict[str, Any]):
        """Decorator or function to register a new tool."""
        def decorator(func: Callable):
            self.tools[name] = func
            schema = {
                "name": name,
                "description": description,
                "parameters": parameters
            }
            self.schemas.append(schema)
            return func
        return decorator

    def execute(self, name: str, arguments: Dict[str, Any]) -> str:
        """Executes a registered tool by name with arguments."""
        if name not in self.tools:
            return json.dumps({"error": f"Tool '{name}' not found in registry."})
        
        try:
            func = self.tools[name]
            result = func(**arguments)
            if isinstance(result, (dict, list)):
                return json.dumps(result)
            return str(result)
        except Exception as e:
            return json.dumps({"error": f"Failed to execute tool '{name}': {str(e)}"})


# Initialize global tool registry instance
registry = ToolRegistry()

# -------------------------------------------------------------
# Database Setup
# -------------------------------------------------------------
DB_PATH = "lisa_memory.db"

def _init_db_tables():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # Reminders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                due_time TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
        """)
        # Calendar events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                description TEXT,
                created_at TEXT NOT NULL
            )
        """)
        # Smart home devices state table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS smart_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_name TEXT UNIQUE NOT NULL,
                device_type TEXT NOT NULL,
                state TEXT NOT NULL,
                brightness INTEGER DEFAULT 100,
                temperature REAL DEFAULT 22.0
            )
        """)
        # Seed default devices if empty
        cursor.execute("SELECT COUNT(*) FROM smart_devices")
        if cursor.fetchone()[0] == 0:
            default_devices = [
                ("living room light", "light", "off", 100, 22.0),
                ("bedroom light", "light", "off", 100, 22.0),
                ("office light", "light", "off", 80, 22.0),
                ("thermostat", "climate", "on", 100, 21.5),
                ("front door lock", "lock", "locked", 100, 22.0),
            ]
            cursor.executemany("""
                INSERT INTO smart_devices (device_name, device_type, state, brightness, temperature)
                VALUES (?, ?, ?, ?, ?)
            """, default_devices)
        conn.commit()

_init_db_tables()


# -------------------------------------------------------------
# Capability 1: get_weather (Real-time Live Weather)
# -------------------------------------------------------------
@registry.register(
    name="get_weather",
    description="Get the current real-time weather and forecast for a given city or location.",
    parameters={
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "The city or location name, e.g. 'New York', 'London', 'Tokyo', 'Mumbai'."
            }
        },
        "required": ["location"]
    }
)
def get_weather(location: str) -> Dict[str, Any]:
    """Fetch live weather data for any location using Open-Meteo geocoding & forecast API."""
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(location)}&count=1&language=en&format=json"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "LisaVoiceAssistant/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            geo_data = json.loads(response.read().decode())

        if not geo_data.get("results"):
            return {"error": f"Could not find coordinates for location '{location}'"}

        first_res = geo_data["results"][0]
        name = first_res.get("name", location)
        country = first_res.get("country", "")
        lat = first_res["latitude"]
        lon = first_res["longitude"]

        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m&temperature_unit=celsius&wind_speed_unit=kmh"
        req_weather = urllib.request.Request(weather_url, headers={"User-Agent": "LisaVoiceAssistant/1.0"})
        with urllib.request.urlopen(req_weather, timeout=5) as response:
            weather_data = json.loads(response.read().decode())

        current = weather_data.get("current", {})
        temp = current.get("temperature_2m", "N/A")
        apparent_temp = current.get("apparent_temperature", "N/A")
        humidity = current.get("relative_humidity_2m", "N/A")
        wind_speed = current.get("wind_speed_10m", "N/A")

        return {
            "location": f"{name}, {country}",
            "temperature_celsius": temp,
            "feels_like_celsius": apparent_temp,
            "humidity_percent": humidity,
            "wind_speed_kmh": wind_speed,
            "status": "success"
        }
    except Exception as e:
        return {"error": f"Unable to fetch weather: {str(e)}"}


# -------------------------------------------------------------
# Capability 2: Reminders & To-Do List (Local SQLite Storage)
# -------------------------------------------------------------
@registry.register(
    name="add_reminder",
    description="Add a new reminder or to-do item to the user's task list.",
    parameters={
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "The task description or what the user wants to be reminded of, e.g. 'Buy groceries' or 'Call Alice'."
            },
            "due_time": {
                "type": "string",
                "description": "Optional due date or time, e.g. 'Tomorrow at 5pm', 'Tonight', or '2026-08-25'."
            }
        },
        "required": ["task"]
    }
)
def add_reminder(task: str, due_time: str = "Unspecified") -> Dict[str, Any]:
    """Add a new task/reminder to persistent database."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO reminders (task, due_time, status, created_at)
            VALUES (?, ?, 'pending', ?)
        """, (task, due_time, now))
        conn.commit()
        task_id = cursor.lastrowid

    return {
        "status": "success",
        "message": f"Reminder added successfully.",
        "task_id": task_id,
        "task": task,
        "due_time": due_time
    }


@registry.register(
    name="list_reminders",
    description="List the user's current reminders / to-do items.",
    parameters={
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "Filter by status: 'pending', 'completed', or 'all'. Defaults to 'pending'.",
                "enum": ["pending", "completed", "all"]
            }
        }
    }
)
def list_reminders(status: str = "pending") -> Dict[str, Any]:
    """List reminders from persistent database."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        if status == "all":
            cursor.execute("SELECT id, task, due_time, status FROM reminders ORDER BY id ASC")
        else:
            cursor.execute("SELECT id, task, due_time, status FROM reminders WHERE status = ? ORDER BY id ASC", (status,))
        rows = cursor.fetchall()

    tasks = [{"id": r[0], "task": r[1], "due_time": r[2], "status": r[3]} for r in rows]
    return {
        "status": "success",
        "total_count": len(tasks),
        "reminders": tasks
    }


@registry.register(
    name="complete_reminder",
    description="Mark a specific reminder or to-do task as completed.",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {
                "type": "integer",
                "description": "The ID of the task to mark as completed."
            }
        },
        "required": ["task_id"]
    }
)
def complete_reminder(task_id: int) -> Dict[str, Any]:
    """Mark a reminder as completed."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE reminders SET status = 'completed' WHERE id = ?", (task_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return {"status": "error", "message": f"No reminder found with ID {task_id}"}

    return {
        "status": "success",
        "message": f"Reminder #{task_id} marked as completed."
    }


# -------------------------------------------------------------
# Capability 3: Web Search (Real-time Live Web Search via DuckDuckGo / ddgs)
# -------------------------------------------------------------
@registry.register(
    name="web_search",
    description="Search the live internet for recent news, facts, current events, or general knowledge.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to look up on the web."
            }
        },
        "required": ["query"]
    }
)
def web_search(query: str) -> Dict[str, Any]:
    """Perform live web search and return top search results."""
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=4))
        
        cleaned_results = []
        for r in results:
            cleaned_results.append({
                "title": r.get("title", ""),
                "snippet": r.get("body", ""),
                "url": r.get("href", "")
            })
            
        return {
            "query": query,
            "results": cleaned_results,
            "status": "success"
        }
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 4: Calendar Read & Create
# -------------------------------------------------------------
@registry.register(
    name="create_calendar_event",
    description="Create a new event, meeting, or appointment in the user's calendar.",
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "The event title / summary, e.g. 'Sync with Team' or 'Dentist Appointment'."
            },
            "start_time": {
                "type": "string",
                "description": "Date and start time of the event, e.g. 'Tomorrow at 3 PM', '2026-08-25 14:00', or 'Friday 10 AM'."
            },
            "end_time": {
                "type": "string",
                "description": "Optional end time of the event, e.g. 'Tomorrow at 4 PM' or '1 hour'."
            },
            "description": {
                "type": "string",
                "description": "Optional details or notes for the calendar event."
            }
        },
        "required": ["title", "start_time"]
    }
)
def create_calendar_event(title: str, start_time: str, end_time: str = "Unspecified", description: str = "") -> Dict[str, Any]:
    """Create a calendar event in persistent database."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO calendar_events (title, start_time, end_time, description, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (title, start_time, end_time, description, now))
        conn.commit()
        event_id = cursor.lastrowid

    return {
        "status": "success",
        "message": f"Calendar event '{title}' scheduled successfully.",
        "event_id": event_id,
        "title": title,
        "start_time": start_time,
        "end_time": end_time
    }


@registry.register(
    name="list_calendar_events",
    description="List scheduled calendar events or meetings.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Optional keyword or date filter to search events."
            }
        }
    }
)
def list_calendar_events(query: Optional[str] = None) -> Dict[str, Any]:
    """List calendar events from persistent storage."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        if query:
            cursor.execute("""
                SELECT id, title, start_time, end_time, description FROM calendar_events
                WHERE title LIKE ? OR start_time LIKE ?
                ORDER BY id ASC
            """, (f"%{query}%", f"%{query}%"))
        else:
            cursor.execute("SELECT id, title, start_time, end_time, description FROM calendar_events ORDER BY id ASC")
        rows = cursor.fetchall()

    events = [{
        "id": r[0],
        "title": r[1],
        "start_time": r[2],
        "end_time": r[3],
        "description": r[4]
    } for r in rows]

    return {
        "status": "success",
        "total_events": len(events),
        "events": events
    }


# -------------------------------------------------------------
# Capability 5: Smart Home Control
# -------------------------------------------------------------
@registry.register(
    name="control_device",
    description="Control smart home devices like lights, switches, or locks.",
    parameters={
        "type": "object",
        "properties": {
            "device_name": {
                "type": "string",
                "description": "Name of the device, e.g. 'living room light', 'bedroom light', 'front door lock'."
            },
            "action": {
                "type": "string",
                "description": "The command: 'on', 'off', 'toggle', 'lock', 'unlock', 'set'. Defaults to 'set'."
            },
            "brightness": {
                "type": "integer",
                "description": "Optional brightness percentage (0 to 100) for lights."
            },
            "temperature": {
                "type": "number",
                "description": "Optional target temperature in Celsius for thermostat."
            }
        },
        "required": ["device_name"]
    }
)
def control_device(device_name: str, action: str = "set", brightness: Optional[int] = None, temperature: Optional[float] = None) -> Dict[str, Any]:
    """Control smart device state locally or via Home Assistant."""
    device_name = device_name.lower().strip()
    action = (action or "set").lower().strip()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, device_name, device_type, state, brightness, temperature FROM smart_devices WHERE device_name LIKE ?", (f"%{device_name}%",))
        row = cursor.fetchone()
        
        if not row:
            cursor.execute("INSERT INTO smart_devices (device_name, device_type, state, brightness, temperature) VALUES (?, 'generic', ?, ?, ?)", 
                           (device_name, action, brightness or 100, temperature or 22.0))
            conn.commit()
            return {"status": "success", "message": f"{device_name.title()} set to {action}."}

        dev_id, dev_name, dev_type, curr_state, curr_bright, curr_temp = row

        new_state = curr_state
        if action in ["on", "off", "locked", "unlocked"]:
            new_state = action
        elif action == "toggle":
            new_state = "off" if curr_state == "on" else "on"
        elif action == "lock":
            new_state = "locked"
        elif action == "unlock":
            new_state = "unlocked"

        new_bright = brightness if brightness is not None else curr_bright
        new_temp = temperature if temperature is not None else curr_temp

        cursor.execute("""
            UPDATE smart_devices
            SET state = ?, brightness = ?, temperature = ?
            WHERE id = ?
        """, (new_state, new_bright, new_temp, dev_id))
        conn.commit()

    details = f"State: {new_state}"
    if brightness is not None:
        details += f", Brightness: {new_bright}%"
    if temperature is not None or dev_type == "climate":
        details += f", Temperature: {new_temp}°C"

    return {
        "status": "success",
        "device": dev_name,
        "action": action,
        "details": details,
        "message": f"Successfully updated {dev_name} ({details})."
    }


@registry.register(
    name="set_thermostat",
    description="Set the target temperature of the home thermostat in Celsius.",
    parameters={
        "type": "object",
        "properties": {
            "temperature": {
                "type": "number",
                "description": "Target temperature in Celsius, e.g. 24.0 or 22.5."
            }
        },
        "required": ["temperature"]
    }
)
def set_thermostat(temperature: float) -> Dict[str, Any]:
    """Set the target thermostat temperature."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE smart_devices SET temperature = ?, state = 'on' WHERE device_type = 'climate' OR device_name = 'thermostat'", (temperature,))
        conn.commit()

    return {
        "status": "success",
        "device": "Thermostat",
        "temperature_celsius": temperature,
        "message": f"Thermostat target temperature set to {temperature}°C."
    }


@registry.register(
    name="get_device_status",
    description="Check the current state, brightness, or temperature of smart home devices.",
    parameters={
        "type": "object",
        "properties": {
            "device_name": {
                "type": "string",
                "description": "Optional device name to check, e.g. 'living room light' or leave empty for all devices."
            }
        }
    }
)
def get_device_status(device_name: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve current smart device statuses."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        if device_name:
            cursor.execute("SELECT device_name, device_type, state, brightness, temperature FROM smart_devices WHERE device_name LIKE ?", (f"%{device_name}%",))
        else:
            cursor.execute("SELECT device_name, device_type, state, brightness, temperature FROM smart_devices")
        rows = cursor.fetchall()

    devices = [{
        "name": r[0],
        "type": r[1],
        "state": r[2],
        "brightness": f"{r[3]}%" if r[1] == "light" else None,
        "temperature": f"{r[4]}°C" if r[1] == "climate" else None
    } for r in rows]

    return {
        "status": "success",
        "devices": devices
    }


# -------------------------------------------------------------
# Capability 8: User Preference & Correction Memory (Stage 8)
# -------------------------------------------------------------
@registry.register(
    name="set_user_preference",
    description="Store or update a persistent user preference, behavioral rule, or correction (e.g. 'Always answer concisely', 'Always use Celsius', 'Never use emojis'). Checks for contradictory rules and surfaces conflicts.",
    parameters={
        "type": "object",
        "properties": {
            "rule": {
                "type": "string",
                "description": "The exact rule or preference to remember."
            },
            "category": {
                "type": "string",
                "description": "Category for rule, e.g. 'formatting', 'language', 'units', or 'general'."
            },
            "replace_rule_id": {
                "type": "integer",
                "description": "Optional ID of an existing conflicting rule to replace if resolving a conflict."
            }
        },
        "required": ["rule"]
    }
)
def set_user_preference(rule: str, category: str = "general", replace_rule_id: Optional[int] = None) -> Dict[str, Any]:
    """Set a user preference with conflict detection."""
    # Check for direct conflicts unless explicit replacement ID provided
    if not replace_rule_id:
        conflict = preference_manager.check_conflict(rule)
        if conflict:
            return {
                "status": "conflict_detected",
                "message": f"Conflict detected with existing rule #{conflict['id']}: '{conflict['rule_text']}'. Please ask user if they want to replace it.",
                "conflicting_rule_id": conflict['id'],
                "conflicting_rule_text": conflict['rule_text']
            }

    res = preference_manager.store_rule(rule, category, replace_rule_id)
    return res


@registry.register(
    name="list_user_preferences",
    description="List all active persistent user preferences and rules.",
    parameters={
        "type": "object",
        "properties": {}
    }
)
def list_user_preferences() -> Dict[str, Any]:
    """List stored preferences."""
    rules = preference_manager.get_all_active_rules()
    return {
        "status": "success",
        "total_rules": len(rules),
        "preferences": rules
    }


@registry.register(
    name="get_system_status",
    description="Check the user's PC hardware status: CPU load, RAM usage, Battery percentage, and disk storage.",
    parameters={
        "type": "object",
        "properties": {}
    }
)
def get_system_status() -> Dict[str, Any]:
    """Retrieve PC system performance and battery diagnostics."""
    try:
        import psutil
        cpu_pct = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        battery_info = "Desktop / No battery"
        battery = psutil.sensors_battery()
        if battery:
            battery_info = f"{battery.percent}% ({'Charging' if battery.power_plugged else 'On Battery'})"

        return {
            "status": "success",
            "cpu_usage": f"{cpu_pct}%",
            "ram_used_gb": round(ram.used / (1024**3), 2),
            "ram_total_gb": round(ram.total / (1024**3), 2),
            "ram_percentage": f"{ram.percent}%",
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "battery": battery_info
        }
    except Exception as e:
        return {"error": f"Failed to read system status: {str(e)}"}


@registry.register(
    name="open_browser_url",
    description="Open any website, URL, or webpage in the user's default web browser.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The complete URL to open, e.g. 'https://www.youtube.com' or 'https://www.google.com'."
            }
        },
        "required": ["url"]
    }
)
def open_browser_url(url: str) -> Dict[str, Any]:
    """Open a URL in default browser."""
    try:
        import os
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
        os.system(f'start "" "{url}"')
        return {"status": "success", "message": f"Opened {url} in browser."}
    except Exception as e:
        return {"error": f"Failed to open URL: {str(e)}"}


@registry.register(
    name="play_music",
    description="Play a song, artist, album, or ambient music directly on YouTube or Spotify.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Song name, artist, or music query, e.g. 'Starboy', 'Interstellar soundtrack', 'Lofi hip hop'."
            },
            "platform": {
                "type": "string",
                "description": "Platform to play on: 'youtube' or 'spotify'. Defaults to 'youtube'.",
                "enum": ["youtube", "spotify"]
            }
        },
        "required": ["query"]
    }
)
def play_music(query: str, platform: str = "youtube") -> Dict[str, Any]:
    """Directly launch and autoplay requested music on YouTube or Spotify."""
    try:
        import os
        import re
        encoded_query = urllib.parse.quote(query)

        if platform.lower() == "spotify":
            os.system(f'start "" "spotify:search:{encoded_query}"')
            url = f"spotify:search:{encoded_query}"
        else:
            # Resolve the first matching video ID directly for immediate playback
            search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
            target_url = search_url
            try:
                req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    html_content = resp.read().decode('utf-8', errors='ignore')
                    video_ids = re.findall(r'/watch\?v=([a-zA-Z0-9_-]{11})', html_content)
                    if video_ids:
                        target_url = f"https://www.youtube.com/watch?v={video_ids[0]}&autoplay=1"
            except Exception:
                target_url = search_url

            os.system(f'start "" "{target_url}"')
            url = target_url

        return {
            "status": "success",
            "message": f"Now playing '{query}' on {platform.title()}.",
            "query": query,
            "url": url
        }
    except Exception as e:
        return {"error": f"Failed to play music: {str(e)}"}


# -------------------------------------------------------------
# Capability 9: Screen Vision & Multimodal Awareness
# -------------------------------------------------------------
def _capture_screen_image():
    """Captures screenshot using PIL ImageGrab with Windows GDI fallback."""
    from PIL import ImageGrab
    try:
        return ImageGrab.grab(all_screens=True)
    except Exception:
        try:
            return ImageGrab.grab()
        except Exception:
            # Native Windows GDI Screen Capture Fallback
            import ctypes
            from PIL import Image
            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32
            
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
            
            hdc_screen = user32.GetDC(0)
            hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
            hbm = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
            gdi32.SelectObject(hdc_mem, hbm)
            gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, 0, 0, 0x00CC0020)
            
            # Extract bitmap bits
            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ('biSize', ctypes.c_uint32),
                    ('biWidth', ctypes.c_int32),
                    ('biHeight', ctypes.c_int32),
                    ('biPlanes', ctypes.c_uint16),
                    ('biBitCount', ctypes.c_uint16),
                    ('biCompression', ctypes.c_uint32),
                    ('biSizeImage', ctypes.c_uint32),
                    ('biXPelsPerMeter', ctypes.c_int32),
                    ('biYPelsPerMeter', ctypes.c_int32),
                    ('biClrUsed', ctypes.c_uint32),
                    ('biClrImportant', ctypes.c_uint32),
                ]
            
            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = width
            bmi.biHeight = -height  # top-down
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = 0
            
            buffer = ctypes.create_string_buffer(width * height * 4)
            gdi32.GetDIBits(hdc_mem, hbm, 0, height, buffer, ctypes.byref(bmi), 0)
            
            # Clean up GDI handles
            gdi32.DeleteObject(hbm)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(0, hdc_screen)
            
            return Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1).convert("RGB")


@registry.register(
    name="analyze_screen",
    description="Take a screenshot of the user's active computer screen and visually analyze, debug, explain, or answer questions about what is displayed.",
    parameters={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "What you want Lisa to look for, explain, read, or debug on your screen."
            }
        }
    }
)
def analyze_screen(question: str = "Describe what is currently visible on my screen.") -> Dict[str, Any]:
    """Capture screen and analyze with Gemini Vision model."""
    try:
        import config
        from google import genai
        from google.genai import types

        screenshot = _capture_screen_image()
        temp_path = "temp_screen.png"
        screenshot.save(temp_path, format="PNG")

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        
        with open(temp_path, "rb") as f:
            image_bytes = f.read()

        response = client.models.generate_content(
            model="gemini-2.5-flash" if "2.5" in config.GEMINI_MODEL else "gemini-3.5-flash-lite",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                f"You are Lisa looking at the user's screen. Answer the following request clearly and concisely: {question}"
            ]
        )

        if os.path.exists(temp_path):
            os.remove(temp_path)

        return {
            "status": "success",
            "analysis": response.text.strip(),
            "query": question
        }
    except Exception as e:
        return {"error": f"Failed to analyze screen: {str(e)}"}


@registry.register(
    name="take_screenshot",
    description="Take and save a screenshot of the computer screen to the user's Pictures/Screenshots folder or workspace.",
    parameters={
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Optional name for the screenshot image file, e.g. 'my_screen.png'."
            }
        }
    }
)
def take_screenshot(filename: Optional[str] = None) -> Dict[str, Any]:
    """Capture and save a screenshot to Pictures/Screenshots."""
    try:
        now_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = filename or f"screenshot_{now_ts}.png"
        if not fname.endswith(".png"):
            fname += ".png"
        
        # Determine target folder (Pictures/Screenshots or current directory)
        user_home = os.path.expanduser("~")
        pictures_dir = os.path.join(user_home, "Pictures", "Screenshots")
        if os.path.exists(os.path.join(user_home, "Pictures")):
            os.makedirs(pictures_dir, exist_ok=True)
            save_path = os.path.join(pictures_dir, fname)
        else:
            save_path = os.path.abspath(fname)
        
        screenshot = _capture_screen_image()
        screenshot.save(save_path, format="PNG")
        
        return {
            "status": "success",
            "message": f"Screenshot saved successfully to {save_path}.",
            "filepath": save_path,
            "filename": fname
        }
    except Exception as e:
        return {"error": f"Failed to take screenshot: {str(e)}"}


# -------------------------------------------------------------
# Capability 10: Desktop App Launcher & File Search
# -------------------------------------------------------------
@registry.register(
    name="launch_application",
    description="Launch a desktop application on the user's PC (e.g. 'VS Code', 'Notepad', 'Calculator', 'Chrome', 'Discord', 'Terminal', 'Task Manager').",
    parameters={
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Name of application, e.g. 'calculator', 'notepad', 'code', 'chrome', 'discord', 'explorer', 'terminal'."
            }
        },
        "required": ["app_name"]
    }
)
def launch_application(app_name: str) -> Dict[str, Any]:
    """Launch application on Windows."""
    app_lower = app_name.lower().strip()
    app_map = {
        "calculator": "calc",
        "calc": "calc",
        "notepad": "notepad",
        "vs code": "code",
        "vscode": "code",
        "code": "code",
        "chrome": "chrome",
        "google chrome": "chrome",
        "discord": "discord",
        "spotify": "spotify",
        "terminal": "wt",
        "command prompt": "cmd",
        "cmd": "cmd",
        "task manager": "taskmgr",
        "explorer": "explorer",
        "file explorer": "explorer",
        "settings": "start ms-settings:"
    }

    cmd = app_map.get(app_lower, app_lower)
    try:
        import subprocess
        if cmd.startswith("start "):
            os.system(cmd)
        else:
            subprocess.Popen(cmd, shell=True)
        return {
            "status": "success",
            "message": f"Launched {app_name.title()} successfully.",
            "app": app_name
        }
    except Exception as e:
        return {"error": f"Could not launch '{app_name}': {str(e)}"}


@registry.register(
    name="find_files",
    description="Search for files or documents matching a filename query in common folders (Downloads, Documents, Desktop, Workspace).",
    parameters={
        "type": "object",
        "properties": {
            "filename_query": {
                "type": "string",
                "description": "The file name or keyword to search for, e.g. 'resume', 'report', '.pdf', 'notes'."
            }
        },
        "required": ["filename_query"]
    }
)
def find_files(filename_query: str) -> Dict[str, Any]:
    """Search for files in user home directories."""
    user_home = os.path.expanduser("~")
    search_dirs = [
        os.path.join(user_home, "Downloads"),
        os.path.join(user_home, "Documents"),
        os.path.join(user_home, "Desktop"),
        os.getcwd()
    ]

    matched_files = []
    query_lower = filename_query.lower()

    for directory in search_dirs:
        if not os.path.exists(directory):
            continue
        try:
            for root, _, files in os.walk(directory):
                # Don't go deeper than 3 levels
                rel = os.path.relpath(root, directory)
                if rel.count(os.sep) > 2:
                    continue
                for f in files:
                    if query_lower in f.lower():
                        matched_files.append(os.path.join(root, f))
                        if len(matched_files) >= 8:
                            break
                if len(matched_files) >= 8:
                    break
        except Exception:
            continue

    return {
        "status": "success",
        "query": filename_query,
        "total_found": len(matched_files),
        "files": matched_files
    }


# -------------------------------------------------------------
# Capability 11: Real-Time Stock & Crypto Ticker
# -------------------------------------------------------------
@registry.register(
    name="get_stock_or_crypto_price",
    description="Get real-time live price quote for cryptocurrencies (Bitcoin, Ethereum, Solana) or major market assets.",
    parameters={
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Cryptocurrency or stock name/symbol, e.g. 'bitcoin', 'ethereum', 'solana', 'dogecoin'."
            }
        },
        "required": ["symbol"]
    }
)
def get_stock_or_crypto_price(symbol: str) -> Dict[str, Any]:
    """Fetch live crypto price via CoinGecko free API."""
    sym_lower = symbol.lower().strip()
    crypto_id_map = {
        "btc": "bitcoin", "bitcoin": "bitcoin",
        "eth": "ethereum", "ethereum": "ethereum",
        "sol": "solana", "solana": "solana",
        "doge": "dogecoin", "dogecoin": "dogecoin",
        "ada": "cardano", "cardano": "cardano",
        "xrp": "ripple", "ripple": "ripple"
    }
    coin_id = crypto_id_map.get(sym_lower, sym_lower)

    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd,inr&include_24hr_change=true"
        req = urllib.request.Request(url, headers={"User-Agent": "LisaVoiceAssistant/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())

        if coin_id in data:
            price_usd = data[coin_id].get("usd", "N/A")
            price_inr = data[coin_id].get("inr", "N/A")
            change_24h = data[coin_id].get("usd_24h_change", 0.0)
            return {
                "asset": coin_id.capitalize(),
                "price_usd": f"${price_usd:,}" if isinstance(price_usd, (int, float)) else price_usd,
                "price_inr": f"₹{price_inr:,}" if isinstance(price_inr, (int, float)) else price_inr,
                "change_24h_percent": f"{round(change_24h, 2)}%",
                "status": "success"
            }
        else:
            # Fallback to web search
            return web_search(f"{symbol} current price")
    except Exception as e:
        return {"error": f"Failed to fetch price: {str(e)}"}


# -------------------------------------------------------------
# Capability 12: Morning Briefing Aggregator
# -------------------------------------------------------------
@registry.register(
    name="get_morning_briefing",
    description="Get a comprehensive daily briefing containing current date/time, weather, pending tasks, and today's schedule.",
    parameters={
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "Optional city for weather, defaults to user's location."
            }
        }
    }
)
def get_morning_briefing(city: str = "Delhi") -> Dict[str, Any]:
    """Aggregate weather, tasks, time, and events into a single daily briefing."""
    weather = get_weather(city)
    reminders = list_reminders("pending")
    calendar = list_calendar_events()
    now = datetime.datetime.now()

    return {
        "greeting": "Good morning! Here is your daily briefing.",
        "date_and_time": now.strftime("%A, %B %d, %Y - %I:%M %p"),
        "weather": weather,
        "pending_tasks": reminders.get("reminders", []),
        "upcoming_events": calendar.get("events", [])
    }


# -------------------------------------------------------------
# Capability 13: Developer Git Companion
# -------------------------------------------------------------
@registry.register(
    name="git_helper",
    description="Inspect git repository status, active branch, or recent commit history.",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Git action: 'status', 'branch', or 'log'. Defaults to 'status'.",
                "enum": ["status", "branch", "log"]
            }
        }
    }
)
def git_helper(action: str = "status") -> Dict[str, Any]:
    """Execute safe git read operations."""
    try:
        import subprocess
        if action == "branch":
            cmd = ["git", "branch", "-v"]
        elif action == "log":
            cmd = ["git", "log", "-n", "3", "--oneline"]
        else:
            cmd = ["git", "status", "-s"]

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        output = res.stdout.strip() or "Working tree is clean."
        return {
            "status": "success",
            "action": f"git {action}",
            "output": output
        }
    except Exception as e:
        return {"error": f"Git command failed: {str(e)}"}


@registry.register(
    name="get_current_time_and_date",
    description="Get the exact real-time local date, day of the week, and current time.",
    parameters={
        "type": "object",
        "properties": {}
    }
)
def get_current_time_and_date() -> Dict[str, Any]:
    """Return the current local day, date, and exact time."""
    now = datetime.datetime.now()
    return {
        "day_of_week": now.strftime("%A"),
        "date": now.strftime("%B %d, %Y"),
        "time_12h": now.strftime("%I:%M:%S %p"),
        "time_24h": now.strftime("%H:%M:%S"),
        "formatted": now.strftime("%A, %B %d, %Y at %I:%M %p")
    }


# -------------------------------------------------------------
# Capability 14: Clipboard Intelligence
# -------------------------------------------------------------
@registry.register(
    name="read_clipboard",
    description="Read and retrieve the current text or content copied to the user's computer clipboard.",
    parameters={
        "type": "object",
        "properties": {}
    }
)
def read_clipboard() -> Dict[str, Any]:
    """Read clipboard content."""
    try:
        import pyperclip
        content = pyperclip.paste()
        if not content:
            return {"status": "empty", "message": "Clipboard is currently empty."}
        return {
            "status": "success",
            "clipboard_content": content,
            "char_count": len(content)
        }
    except Exception as e:
        return {"error": f"Failed to read clipboard: {str(e)}"}


@registry.register(
    name="set_clipboard",
    description="Copy given text or data directly to the user's computer clipboard.",
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to copy into clipboard."
            }
        },
        "required": ["text"]
    }
)
def set_clipboard(text: str) -> Dict[str, Any]:
    """Copy text to clipboard."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return {
            "status": "success",
            "message": "Text copied to clipboard successfully."
        }
    except Exception as e:
        return {"error": f"Failed to copy to clipboard: {str(e)}"}


# -------------------------------------------------------------
# Capability 15: Windows Volume & Mute Controls (Direct Core Audio API)
# -------------------------------------------------------------
@registry.register(
    name="set_system_volume",
    description="Set the PC master audio volume level (0 to 100) or mute/unmute audio.",
    parameters={
        "type": "object",
        "properties": {
            "level_percent": {
                "type": "integer",
                "description": "Volume percentage from 0 to 100."
            },
            "mute": {
                "type": "boolean",
                "description": "Optional boolean: true to mute, false to unmute."
            }
        }
    }
)
def set_system_volume(level_percent: Optional[int] = None, mute: Optional[bool] = None) -> Dict[str, Any]:
    """Adjust system master volume via Windows Core Audio API."""
    try:
        from pycaw.pycaw import AudioUtilities
        speakers = AudioUtilities.GetSpeakers()
        volume = speakers.EndpointVolume

        if mute is not None:
            volume.SetMute(1 if mute else 0, None)
            return {
                "status": "success",
                "mute_state": "Muted" if mute else "Unmuted",
                "message": f"Audio {'muted' if mute else 'unmuted'}."
            }

        if level_percent is not None:
            level = max(0, min(100, int(level_percent)))
            scalar = level / 100.0
            volume.SetMasterVolumeLevelScalar(scalar, None)
            # Ensure unmuted if raising volume
            if level > 0 and volume.GetMute():
                volume.SetMute(0, None)
            return {
                "status": "success",
                "volume_level": f"{level}%",
                "message": f"Master volume set to {level}%."
            }

        current_scalar = round(volume.GetMasterVolumeLevelScalar() * 100)
        is_muted = bool(volume.GetMute())
        return {
            "status": "success",
            "current_volume": f"{current_scalar}%",
            "is_muted": is_muted
        }
    except Exception as e:
        return {"error": f"Failed to adjust audio: {str(e)}"}


# -------------------------------------------------------------
# Capability 16: Countdown Timers & Pomodoro Sessions
# -------------------------------------------------------------
@registry.register(
    name="set_countdown_timer",
    description="Set a countdown timer for a specified number of minutes (e.g. 0.5 for 30s, 5 minutes, 25 minute Pomodoro). Speaks voice alert when complete.",
    parameters={
        "type": "object",
        "properties": {
            "minutes": {
                "type": "number",
                "description": "Duration in minutes (e.g. 0.5, 1, 5, 25)."
            },
            "label": {
                "type": "string",
                "description": "What the timer is for, e.g. 'Pomodoro Focus', 'Tea', 'Meeting'."
            }
        },
        "required": ["minutes"]
    }
)
def set_countdown_timer(minutes: float, label: str = "Timer") -> Dict[str, Any]:
    """Schedule a countdown timer with proactive voice & visual alarm."""
    try:
        import threading
        from reminder_daemon import reminder_daemon
        
        seconds = max(1, int(float(minutes) * 60))
        
        def _timer_worker():
            import time
            time.sleep(seconds)
            alert_msg = f"Timer complete: Your {minutes}-minute {label} timer is finished!"
            
            # 1. Print visual alert
            print(f"\n🔔 [Lisa Timer Alarm]: {alert_msg}\n")

            # 2. Trigger registered daemon callback (avatar WebSocket)
            if reminder_daemon.alert_callback:
                try:
                    reminder_daemon.alert_callback(alert_msg)
                except Exception:
                    pass

            # 3. Speak voice alert aloud via TTS engine
            try:
                from tts import get_tts_engine
                tts_engine = get_tts_engine("edge")
                tts_engine.speak(alert_msg)
            except Exception:
                pass
                
        t = threading.Thread(target=_timer_worker, daemon=True)
        t.start()

        return {
            "status": "success",
            "duration_minutes": minutes,
            "label": label,
            "message": f"Timer set for {minutes} minute(s) for '{label}'. I will alert you with voice when it rings!"
        }
    except Exception as e:
        return {"error": f"Failed to set timer: {str(e)}"}


# -------------------------------------------------------------
# Capability 17: Local PDF & Document Deep Reader
# -------------------------------------------------------------
@registry.register(
    name="read_document",
    description="Read and extract text from a local PDF, text file, markdown file, or source code file.",
    parameters={
        "type": "object",
        "properties": {
            "filepath": {
                "type": "string",
                "description": "Path to document, e.g. 'resume.pdf', 'notes.txt', or full absolute path."
            }
        },
        "required": ["filepath"]
    }
)
def read_document(filepath: str) -> Dict[str, Any]:
    """Extract text from local PDF or text file."""
    try:
        if not os.path.exists(filepath):
            user_home = os.path.expanduser("~")
            alt1 = os.path.join(user_home, "Downloads", filepath)
            alt2 = os.path.join(user_home, "Documents", filepath)
            alt3 = os.path.join(user_home, "Desktop", filepath)
            if os.path.exists(alt1): filepath = alt1
            elif os.path.exists(alt2): filepath = alt2
            elif os.path.exists(alt3): filepath = alt3
            else:
                return {"error": f"File not found at '{filepath}'"}

        extracted_text = ""
        if filepath.lower().endswith(".pdf"):
            from pypdf import PdfReader
            reader = PdfReader(filepath)
            for page in reader.pages[:10]:
                extracted_text += (page.extract_text() or "") + "\n"
        else:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                extracted_text = f.read(15000)

        return {
            "status": "success",
            "filepath": filepath,
            "preview": extracted_text[:1000],
            "total_chars": len(extracted_text),
            "content": extracted_text[:8000]
        }
    except Exception as e:
        return {"error": f"Could not read document: {str(e)}"}


# -------------------------------------------------------------
# Capability 18: Live Translation Engine
# -------------------------------------------------------------
@registry.register(
    name="translate_text",
    description="Translate text between languages (e.g. English, Spanish, Japanese, Hindi, French, German, Mandarin).",
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to translate."
            },
            "target_language": {
                "type": "string",
                "description": "Target language, e.g. 'Spanish', 'Japanese', 'Hindi', 'French'."
            }
        },
        "required": ["text", "target_language"]
    }
)
def translate_text(text: str, target_language: str) -> Dict[str, Any]:
    """Translate text using LLM."""
    try:
        import config
        from google import genai

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        prompt = f"Translate the following text into {target_language}. Provide only the direct translation and phonetic pronunciation if non-latin script:\n\n\"{text}\""
        res = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt
        )
        return {
            "status": "success",
            "original_text": text,
            "target_language": target_language,
            "translation": res.text.strip()
        }
    except Exception as e:
        return {"error": f"Translation failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 19: Wikipedia Deep Knowledge Search
# -------------------------------------------------------------
@registry.register(
    name="wikipedia_search",
    description="Search Wikipedia for detailed factual summaries, histories, scientific concepts, or biographies.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Topic, person, science concept, or historical event to search on Wikipedia."
            }
        },
        "required": ["query"]
    }
)
def wikipedia_search(query: str) -> Dict[str, Any]:
    """Fetch Wikipedia summary via REST API."""
    try:
        encoded = urllib.parse.quote(query.replace(" ", "_"))
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "LisaVoiceAssistant/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())

        return {
            "status": "success",
            "title": data.get("title", query),
            "description": data.get("description", ""),
            "summary": data.get("extract", "No extract found."),
            "url": data.get("content_urls", {}).get("desktop", {}).get("page", "")
        }
    except Exception as e:
        return {"error": f"Wikipedia search failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 20: Local Network & Ping Diagnostics (Privacy-Safe)
# -------------------------------------------------------------
@registry.register(
    name="get_network_info",
    description="Check local internet connectivity, connection health, and ping latency without looking up or exposing your public IP.",
    parameters={
        "type": "object",
        "properties": {}
    }
)
def get_network_info() -> Dict[str, Any]:
    """Check local connectivity and latency safely without public IP exposure."""
    try:
        import socket
        import time

        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)

        # Measure connection latency to high-speed DNS
        t0 = time.time()
        s = socket.create_connection(("1.1.1.1", 53), timeout=3)
        latency_ms = round((time.time() - t0) * 1000, 1)
        s.close()

        return {
            "status": "online",
            "connection": "Active & Connected",
            "ping_latency": f"{latency_ms} ms",
            "local_hostname": hostname,
            "local_network_ip": local_ip,
            "privacy_mode": "Public IP hidden (Local Diagnostics Only)"
        }
    except Exception as e:
        return {
            "status": "offline_or_limited",
            "connection": "Disconnected or High Latency",
            "error": str(e)
        }


# -------------------------------------------------------------
# Capability 21: QR Code Generator
# -------------------------------------------------------------
@registry.register(
    name="generate_qr_code",
    description="Generate and save a scannable QR Code image for any URL, Wi-Fi configuration, or text.",
    parameters={
        "type": "object",
        "properties": {
            "data": {
                "type": "string",
                "description": "Text or URL to encode in the QR code."
            },
            "filename": {
                "type": "string",
                "description": "Optional name for output image file, e.g. 'wifi_qr.png'."
            }
        },
        "required": ["data"]
    }
)
def generate_qr_code(data: str, filename: Optional[str] = None) -> Dict[str, Any]:
    """Generate QR code image."""
    try:
        import qrcode
        fname = filename or f"qrcode_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        if not fname.endswith(".png"):
            fname += ".png"

        img = qrcode.make(data)
        img.save(fname)
        
        return {
            "status": "success",
            "message": f"QR Code generated and saved as '{fname}'.",
            "filepath": os.path.abspath(fname),
            "encoded_data": data
        }
    except Exception as e:
        return {"error": f"Failed to generate QR Code: {str(e)}"}


# -------------------------------------------------------------
# Capability 22: Universal Unit & Currency Converter
# -------------------------------------------------------------
@registry.register(
    name="convert_currency_or_units",
    description="Convert between currencies (USD, INR, EUR, GBP) or physical units (miles/km, lbs/kg, inches/cm, Fahrenheit/Celsius).",
    parameters={
        "type": "object",
        "properties": {
            "amount": {
                "type": "number",
                "description": "Numerical amount to convert."
            },
            "from_unit": {
                "type": "string",
                "description": "Starting unit or currency, e.g. 'USD', 'miles', 'kg', 'fahrenheit'."
            },
            "to_unit": {
                "type": "string",
                "description": "Target unit or currency, e.g. 'INR', 'km', 'lbs', 'celsius'."
            }
        },
        "required": ["amount", "from_unit", "to_unit"]
    }
)
def convert_currency_or_units(amount: float, from_unit: str, to_unit: str) -> Dict[str, Any]:
    """Perform real-time unit and currency conversions."""
    fu = from_unit.lower().strip()
    tu = to_unit.lower().strip()

    # Simple Currency Converter using open exchange rate API
    currencies = ["usd", "inr", "eur", "gbp", "jpy", "cad", "aud"]
    if fu in currencies and tu in currencies:
        try:
            url = f"https://open.er-api.com/v6/latest/{fu.upper()}"
            req = urllib.request.Request(url, headers={"User-Agent": "LisaVoiceAssistant/1.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
            rates = data.get("rates", {})
            rate = rates.get(tu.upper())
            if rate:
                converted = round(amount * rate, 2)
                return {
                    "status": "success",
                    "from": f"{amount} {fu.upper()}",
                    "to": f"{converted} {tu.upper()}",
                    "exchange_rate": rate
                }
        except Exception:
            pass

    # Distance / Weight / Temperature conversions
    if fu in ["km", "kilometers"] and tu in ["miles", "mi"]:
        return {"status": "success", "result": f"{round(amount * 0.621371, 2)} miles"}
    if fu in ["miles", "mi"] and tu in ["km", "kilometers"]:
        return {"status": "success", "result": f"{round(amount * 1.60934, 2)} km"}
    if fu in ["kg", "kilograms"] and tu in ["lbs", "pounds"]:
        return {"status": "success", "result": f"{round(amount * 2.20462, 2)} lbs"}
    if fu in ["lbs", "pounds"] and tu in ["kg", "kilograms"]:
        return {"status": "success", "result": f"{round(amount * 0.453592, 2)} kg"}
    if "f" in fu and "c" in tu:
        return {"status": "success", "result": f"{round((amount - 32) * 5/9, 2)}°C"}
    if "c" in fu and "f" in tu:
        return {"status": "success", "result": f"{round((amount * 9/5) + 32, 2)}°F"}

    return {"status": "success", "result": f"{amount} {from_unit} to {to_unit}"}


# -------------------------------------------------------------
# Capability 23: System Lock & Security Control
# -------------------------------------------------------------
@registry.register(
    name="system_power_control",
    description="Control PC security power states: 'lock_screen', 'sleep', or 'cancel'.",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Security action: 'lock_screen' or 'sleep'.",
                "enum": ["lock_screen", "sleep"]
            }
        },
        "required": ["action"]
    }
)
def system_power_control(action: str) -> Dict[str, Any]:
    """Control PC security lock on Windows."""
    try:
        if action == "lock_screen":
            os.system("rundll32.exe user32.dll,LockWorkStation")
            return {"status": "success", "message": "Workstation locked."}
        elif action == "sleep":
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            return {"status": "success", "message": "Putting computer to sleep."}
        return {"status": "error", "message": "Unsupported action."}
    except Exception as e:
        return {"error": f"Failed to execute {action}: {str(e)}"}


# -------------------------------------------------------------
# Capability 24: Secure Password Generator
# -------------------------------------------------------------
@registry.register(
    name="generate_password",
    description="Generate a cryptographically secure random password or API secret token.",
    parameters={
        "type": "object",
        "properties": {
            "length": {
                "type": "integer",
                "description": "Password length in characters (e.g. 12, 16, 24). Defaults to 16."
            },
            "include_symbols": {
                "type": "boolean",
                "description": "Whether to include special symbols (!@#$%^&*). Defaults to true."
            }
        }
    }
)
def generate_password(length: int = 16, include_symbols: bool = True) -> Dict[str, Any]:
    """Generate secure password."""
    import secrets
    import string
    chars = string.ascii_letters + string.digits
    if include_symbols:
        chars += "!@#$%^&*()-_=+"
    
    length = max(8, min(128, int(length)))
    pwd = ''.join(secrets.choice(chars) for _ in range(length))
    
    return {
        "status": "success",
        "password": pwd,
        "length": length,
        "message": f"Generated secure {length}-character password."
    }


# -------------------------------------------------------------
# Capability 25: Ambient Sci-Fi & Focus Soundscapes
# -------------------------------------------------------------
@registry.register(
    name="play_ambient_soundscape",
    description="Play relaxing focus soundscapes (e.g. 'spaceship_cabin', 'cyberpunk_rain', 'deep_space_white_noise', 'fireplace', 'ocean_waves').",
    parameters={
        "type": "object",
        "properties": {
            "environment": {
                "type": "string",
                "description": "Soundscape environment: 'spaceship_cabin', 'cyberpunk_rain', 'deep_space', 'fireplace', or 'ocean_waves'.",
                "enum": ["spaceship_cabin", "cyberpunk_rain", "deep_space", "fireplace", "ocean_waves"]
            }
        },
        "required": ["environment"]
    }
)
def play_ambient_soundscape(environment: str = "spaceship_cabin") -> Dict[str, Any]:
    """Launch curated ambient focus audio."""
    sound_queries = {
        "spaceship_cabin": "spaceship ambient engine noise focus 10 hours",
        "cyberpunk_rain": "cyberpunk rain on window ambient lofi 10 hours",
        "deep_space": "deep space interstellar ambient sound 10 hours",
        "fireplace": "cozy fireplace crackling sounds ambient",
        "ocean_waves": "calm ocean waves gentle ambient sound"
    }
    query = sound_queries.get(environment.lower().strip(), f"{environment} ambient focus sound")
    return play_music(query, "youtube")


# -------------------------------------------------------------
# Capability 26: Webcam Vision & Real-World Sight
# -------------------------------------------------------------
@registry.register(
    name="capture_webcam_and_analyze",
    description="Capture a photo from the computer's webcam and visually analyze, identify, read, or describe what is in front of the camera.",
    parameters={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "What you want Lisa to inspect or identify (e.g. 'What am I holding?', 'Read this note', 'Describe what you see')."
            }
        }
    }
)
def capture_webcam_and_analyze(question: str = "Describe what you see in this webcam photo.") -> Dict[str, Any]:
    """Capture a webcam photo and inspect with Gemini Multimodal Vision."""
    try:
        import cv2
        import config
        from google import genai
        from google.genai import types

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return {"error": "Could not access webcam device."}

        # Warmup camera
        for _ in range(5):
            cap.read()
        
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return {"error": "Failed to capture image frame from webcam."}

        temp_cam = "temp_webcam.png"
        cv2.imwrite(temp_cam, frame)

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        with open(temp_cam, "rb") as f:
            image_bytes = f.read()

        response = client.models.generate_content(
            model="gemini-2.5-flash" if "2.5" in config.GEMINI_MODEL else "gemini-3.5-flash-lite",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                f"You are Lisa looking through the user's camera. Answer the following request clearly and warmly: {question}"
            ]
        )

        if os.path.exists(temp_cam):
            os.remove(temp_cam)

        return {
            "status": "success",
            "analysis": response.text.strip(),
            "query": question
        }
    except Exception as e:
        return {"error": f"Webcam vision failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 27: Web Article & URL Deep Summarizer
# -------------------------------------------------------------
@registry.register(
    name="summarize_web_article",
    description="Fetch and extract full text from a web link / article / blog post and generate a clear structured summary.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The web URL to scrape and summarize."
            }
        },
        "required": ["url"]
    }
)
def summarize_web_article(url: str) -> Dict[str, Any]:
    """Scrape and summarize an article URL."""
    try:
        from bs4 import BeautifulSoup
        import config
        from google import genai

        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=6) as response:
            html = response.read().decode('utf-8', errors='ignore')

        soup = BeautifulSoup(html, 'html.parser')
        # Remove script and style tags
        for s in soup(["script", "style", "nav", "footer", "header"]):
            s.extract()

        paragraphs = [p.get_text().strip() for p in soup.find_all('p') if len(p.get_text().strip()) > 30]
        full_text = "\n".join(paragraphs[:15]) # Extract top paragraphs

        if not full_text:
            return {"error": "Could not extract readable article text from this webpage."}

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        summary_prompt = f"Summarize the following article in 3-4 clear, engaging bullet points:\n\n{full_text[:6000]}"
        res = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=summary_prompt
        )

        return {
            "status": "success",
            "url": url,
            "title": soup.title.string.strip() if soup.title else "Article",
            "summary": res.text.strip()
        }
    except Exception as e:
        return {"error": f"Failed to summarize webpage: {str(e)}"}


# -------------------------------------------------------------
# Capability 28: Female Voice & Accent Switcher
# -------------------------------------------------------------
@registry.register(
    name="switch_female_voice",
    description="Switch Lisa's speaking voice between curated female voice presets ('jenny' for American Warm, 'aria' for American Energetic, 'sonia' for British Modern, 'natasha' for Australian, 'neerja' for Indian English).",
    parameters={
        "type": "object",
        "properties": {
            "voice_name": {
                "type": "string",
                "description": "Female voice preset: 'jenny', 'aria', 'sonia', 'natasha', or 'neerja'.",
                "enum": ["jenny", "aria", "sonia", "natasha", "neerja"]
            }
        },
        "required": ["voice_name"]
    }
)
def switch_female_voice(voice_name: str) -> Dict[str, Any]:
    """Switch active female voice model."""
    from tts import set_active_female_voice, FEMALE_VOICES
    chosen_id = set_active_female_voice(voice_name)
    return {
        "status": "success",
        "active_voice_id": chosen_id,
        "voice_preset": voice_name.capitalize(),
        "message": f"Lisa's voice switched to {voice_name.capitalize()} ({chosen_id})."
    }


# -------------------------------------------------------------
# Capability 29: Automated Git Committer & Code Reviewer
# -------------------------------------------------------------
@registry.register(
    name="create_git_commit",
    description="Stage modified files and create a git commit with a clear commit message.",
    parameters={
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Commit message describing the changes."
            }
        },
        "required": ["message"]
    }
)
def create_git_commit(message: str) -> Dict[str, Any]:
    """Stage and commit changes in the active git repository."""
    try:
        import subprocess
        # Stage changes
        subprocess.run(["git", "add", "."], check=True, capture_output=True, text=True)
        # Commit
        res = subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True)
        return {
            "status": "success",
            "message": f"Committed with message: '{message}'.",
            "git_output": res.stdout.strip()
        }
    except Exception as e:
        return {"error": f"Git commit failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 30: Daily Productivity Scorecard
# -------------------------------------------------------------
@registry.register(
    name="get_daily_productivity_score",
    description="Check your daily accomplishments: completed tasks, active reminders, scheduled events, and productivity summary.",
    parameters={
        "type": "object",
        "properties": {}
    }
)
def get_daily_productivity_score() -> Dict[str, Any]:
    """Calculate and return daily productivity scorecard."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM reminders WHERE status = 'completed'")
        completed_tasks = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM reminders WHERE status = 'pending'")
        pending_tasks = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM calendar_events")
        total_events = cursor.fetchone()[0]

    return {
        "status": "success",
        "completed_tasks_count": completed_tasks,
        "pending_tasks_count": pending_tasks,
        "scheduled_events_count": total_events,
        "productivity_summary": f"You have completed {completed_tasks} tasks and have {pending_tasks} pending items on your agenda today."
    }


# -------------------------------------------------------------
# Capability 31: Email Drafter & Gmail Compose Hook
# -------------------------------------------------------------
@registry.register(
    name="draft_or_send_email",
    description="Format an email and open a pre-filled compose window in Gmail or default mail client.",
    parameters={
        "type": "object",
        "properties": {
            "recipient": {
                "type": "string",
                "description": "Recipient email address, e.g. 'alex@example.com'."
            },
            "subject": {
                "type": "string",
                "description": "Subject line of the email."
            },
            "body": {
                "type": "string",
                "description": "Body message or content of the email."
            }
        },
        "required": ["recipient", "subject", "body"]
    }
)
def draft_or_send_email(recipient: str, subject: str, body: str) -> Dict[str, Any]:
    """Open a pre-filled Gmail compose window."""
    try:
        enc_to = urllib.parse.quote(recipient)
        enc_su = urllib.parse.quote(subject)
        enc_body = urllib.parse.quote(body)
        
        gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={enc_to}&su={enc_su}&body={enc_body}"
        os.system(f'start "" "{gmail_url}"')
        
        return {
            "status": "success",
            "recipient": recipient,
            "subject": subject,
            "message": f"Drafted email to {recipient} and opened compose window."
        }
    except Exception as e:
        return {"error": f"Failed to draft email: {str(e)}"}


# -------------------------------------------------------------
# Capability 32: Searchable Markdown Notebook
# -------------------------------------------------------------
@registry.register(
    name="create_or_search_notes",
    description="Save a new markdown note with tags or search existing notes.",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "'create' to save a note, 'search' to find notes, 'list' to view all.",
                "enum": ["create", "search", "list"]
            },
            "title": {
                "type": "string",
                "description": "Title of the note (required for 'create')."
            },
            "content": {
                "type": "string",
                "description": "Note content in Markdown (for 'create')."
            },
            "query": {
                "type": "string",
                "description": "Search keyword or tag (for 'search')."
            }
        },
        "required": ["action"]
    }
)
def create_or_search_notes(action: str, title: Optional[str] = None, content: Optional[str] = None, query: Optional[str] = None) -> Dict[str, Any]:
    """Manage local markdown notes directory."""
    notes_dir = os.path.join(os.path.dirname(__file__), "notes")
    os.makedirs(notes_dir, exist_ok=True)

    if action == "create":
        if not title or not content:
            return {"error": "Both 'title' and 'content' are required to create a note."}
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).rstrip()
        filename = f"{safe_title.replace(' ', '_')}.md"
        filepath = os.path.join(notes_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n*Saved: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n{content}\n")

        return {
            "status": "success",
            "message": f"Note '{title}' saved successfully.",
            "filepath": filepath
        }

    elif action == "search":
        if not query:
            return {"error": "Query string is required to search notes."}
        matched = []
        q_lower = query.lower()
        for fname in os.listdir(notes_dir):
            if fname.endswith(".md"):
                fpath = os.path.join(notes_dir, fname)
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                if q_lower in fname.lower() or q_lower in text.lower():
                    matched.append({"file": fname, "preview": text[:200]})

        return {
            "status": "success",
            "total_matched": len(matched),
            "results": matched
        }

    elif action == "list":
        notes = [f[:-3] for f in os.listdir(notes_dir) if f.endswith(".md")]
        return {
            "status": "success",
            "total_notes": len(notes),
            "notes": notes
        }

    return {"error": "Invalid action."}


# -------------------------------------------------------------
# Capability 33: Process & Task Manager
# -------------------------------------------------------------
@registry.register(
    name="manage_system_processes",
    description="Inspect top CPU/RAM consuming processes or kill an unresponsive application.",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "'list_top' to view heaviest apps, 'kill' to terminate a process.",
                "enum": ["list_top", "kill"]
            },
            "process_name": {
                "type": "string",
                "description": "Process name to terminate (e.g. 'notepad.exe', 'chrome.exe') when action is 'kill'."
            }
        },
        "required": ["action"]
    }
)
def manage_system_processes(action: str, process_name: Optional[str] = None) -> Dict[str, Any]:
    """Inspect and manage Windows processes via psutil."""
    try:
        import psutil
        if action == "list_top":
            procs = []
            for p in psutil.process_iter(['name', 'cpu_percent', 'memory_percent']):
                try:
                    info = p.info
                    if info['cpu_percent'] is not None and info['name']:
                        procs.append(info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            # Sort by memory percent
            procs.sort(key=lambda x: x.get('memory_percent') or 0, reverse=True)
            top_5 = [{
                "name": p['name'],
                "ram_percent": f"{round(p.get('memory_percent') or 0, 1)}%",
                "cpu_percent": f"{p.get('cpu_percent') or 0}%"
            } for p in procs[:5]]
            return {"status": "success", "top_processes": top_5}

        elif action == "kill":
            if not process_name:
                return {"error": "Please provide 'process_name' to terminate."}
            killed_count = 0
            for p in psutil.process_iter(['name']):
                try:
                    if process_name.lower() in p.info['name'].lower():
                        p.terminate()
                        killed_count += 1
                except Exception:
                    pass
            return {
                "status": "success",
                "message": f"Terminated {killed_count} instance(s) of '{process_name}'."
            }
    except Exception as e:
        return {"error": f"Process operation failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 34: Local Audio & Voice Memo Transcriber
# -------------------------------------------------------------
@registry.register(
    name="transcribe_audio_file",
    description="Transcribe an audio file (.mp3, .wav, .m4a) from Downloads or project directory using local Whisper.",
    parameters={
        "type": "object",
        "properties": {
            "filename_or_path": {
                "type": "string",
                "description": "Path or filename of the audio recording to transcribe."
            }
        },
        "required": ["filename_or_path"]
    }
)
def transcribe_audio_file(filename_or_path: str) -> Dict[str, Any]:
    """Transcribe audio file via Faster-Whisper."""
    try:
        import os
        from faster_whisper import WhisperModel
        
        target_path = filename_or_path
        if not os.path.exists(target_path):
            user_home = os.path.expanduser("~")
            alt1 = os.path.join(user_home, "Downloads", filename_or_path)
            alt2 = os.path.join(user_home, "Documents", filename_or_path)
            if os.path.exists(alt1): target_path = alt1
            elif os.path.exists(alt2): target_path = alt2
            else:
                return {"error": f"Audio file not found at '{filename_or_path}'."}

        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, info = model.transcribe(target_path, beam_size=2)
        transcription_text = " ".join([segment.text for segment in segments]).strip()

        return {
            "status": "success",
            "filepath": target_path,
            "detected_language": info.language,
            "duration_seconds": round(info.duration, 1),
            "transcript": transcription_text
        }
    except Exception as e:
        return {"error": f"Failed to transcribe audio file: {str(e)}"}


# -------------------------------------------------------------
# Capability 35: Live Air Quality & UV Index
# -------------------------------------------------------------
@registry.register(
    name="get_air_quality_and_uv",
    description="Check real-time Air Quality Index (AQI), PM2.5 particulate levels, and UV Index for any city.",
    parameters={
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "City or region name, e.g. 'Delhi', 'New York', 'Tokyo', 'London'."
            }
        },
        "required": ["location"]
    }
)
def get_air_quality_and_uv(location: str) -> Dict[str, Any]:
    """Fetch live AQI, PM2.5, and UV data from Open-Meteo Air Quality API."""
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(location)}&count=1&language=en&format=json"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "LisaVoiceAssistant/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            geo_data = json.loads(response.read().decode())

        if not geo_data.get("results"):
            return {"error": f"Could not find coordinates for '{location}'."}

        first_res = geo_data["results"][0]
        lat, lon = first_res["latitude"], first_res["longitude"]
        city_name = first_res.get("name", location)
        country = first_res.get("country", "")

        aq_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=us_aqi,pm2_5,pm10,uv_index"
        req_aq = urllib.request.Request(aq_url, headers={"User-Agent": "LisaVoiceAssistant/1.0"})
        with urllib.request.urlopen(req_aq, timeout=5) as response:
            aq_data = json.loads(response.read().decode())

        current = aq_data.get("current", {})
        us_aqi = current.get("us_aqi", "N/A")
        pm25 = current.get("pm2_5", "N/A")
        uv = current.get("uv_index", "N/A")

        # AQI Assessment
        aqi_category = "Good"
        if isinstance(us_aqi, (int, float)):
            if us_aqi > 300: aqi_category = "Hazardous"
            elif us_aqi > 200: aqi_category = "Very Unhealthy"
            elif us_aqi > 150: aqi_category = "Unhealthy"
            elif us_aqi > 100: aqi_category = "Unhealthy for Sensitive Groups"
            elif us_aqi > 50: aqi_category = "Moderate"

        return {
            "status": "success",
            "location": f"{city_name}, {country}",
            "aqi_index": us_aqi,
            "air_quality": aqi_category,
            "pm2_5_level": f"{pm25} µg/m³",
            "uv_index": uv
        }
    except Exception as e:
        return {"error": f"Failed to fetch air quality: {str(e)}"}


# -------------------------------------------------------------
# Capability 36: Webcam Multimodal Vision & Scene Analysis
# -------------------------------------------------------------
@registry.register(
    name="capture_webcam_and_analyze",
    description="Capture a live image from the webcam and perform multimodal visual analysis with Gemini Vision. Call this whenever the user asks 'Can you see me?', 'Look at me', 'What am I wearing?', 'What is in front of the camera?', 'What am I holding?', 'Describe what you see', or asks any question about their physical appearance, clothes, room, objects, gestures, or visual environment.",
    parameters={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Specific visual inspection question or instruction (e.g. 'What is the user wearing?', 'Describe what is on the desk', 'What is the user doing?'). Defaults to 'Describe what you see in front of the camera in detail.'."
            }
        }
    }
)
def capture_webcam_and_analyze(prompt: str = "Describe what you see in front of the camera in detail.") -> Dict[str, Any]:
    """Capture a webcam frame and run Gemini Multimodal Vision analysis."""
    try:
        from face_vision import face_vision_engine
        return face_vision_engine.analyze_scene(prompt=prompt)
    except Exception as e:
        return {"error": f"Camera vision analysis failed: {str(e)}"}


@registry.register(
    name="check_camera_status",
    description="Check and verify if the webcam hardware is plugged in, accessible, functioning properly, and return its resolution.",
    parameters={
        "type": "object",
        "properties": {}
    }
)
def check_camera_status() -> Dict[str, Any]:
    """Test webcam hardware accessibility and health."""
    try:
        from face_vision import face_vision_engine
        return face_vision_engine.check_camera_health()
    except Exception as e:
        return {"error": f"Camera status check failed: {str(e)}"}


@registry.register(
    name="detect_user_presence",
    description="Check if a person or user is currently sitting in front of the computer webcam.",
    parameters={
        "type": "object",
        "properties": {}
    }
)
def detect_user_presence() -> Dict[str, Any]:
    """Detect if user is present in front of webcam using Vision AI."""
    try:
        import cv2
        import config
        from face_vision import face_vision_engine
        from google import genai
        from google.genai import types

        frame = face_vision_engine.capture_webcam_frame()
        if frame is None:
            return {"error": "Webcam is currently not accessible or busy."}

        temp_img = "temp_presence.png"
        cv2.imwrite(temp_img, frame)

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        with open(temp_img, "rb") as f:
            img_data = f.read()

        prompt = "Look at this webcam photo. Is there a person sitting or standing in front of the computer? Answer with 'YES' or 'NO' followed by a one-sentence warm observation."
        res = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=img_data, mime_type="image/png"),
                prompt
            ]
        )

        if os.path.exists(temp_img):
            os.remove(temp_img)

        output_text = res.text.strip()
        is_present = output_text.upper().startswith("YES") or "YES" in output_text.upper()[:10]

        return {
            "status": "success",
            "user_detected": is_present,
            "observation": output_text
        }
    except Exception as e:
        return {"error": f"Presence check failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 37: Posture & Ergonomics Health Check
# -------------------------------------------------------------
@registry.register(
    name="check_posture_and_ergonomics",
    description="Analyze the user's sitting posture, shoulder alignment, screen distance, and desk lighting via webcam.",
    parameters={
        "type": "object",
        "properties": {}
    }
)
def check_posture_and_ergonomics() -> Dict[str, Any]:
    """Inspect posture and lighting using Gemini Vision."""
    try:
        import cv2
        import config
        from face_vision import face_vision_engine
        from google import genai
        from google.genai import types

        frame = face_vision_engine.capture_webcam_frame()
        if frame is None:
            return {"error": "Webcam not available."}

        temp_img = "temp_posture.png"
        cv2.imwrite(temp_img, frame)

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        with open(temp_img, "rb") as f:
            img_data = f.read()

        prompt = "You are Lisa, an observant and helpful companion. Look at the person in this webcam photo and evaluate their sitting posture, head angle, distance from camera, and room lighting. Give 2 friendly, concise tips on posture or eye strain."
        res = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=img_data, mime_type="image/png"),
                prompt
            ]
        )

        if os.path.exists(temp_img):
            os.remove(temp_img)

        return {
            "status": "success",
            "posture_feedback": res.text.strip()
        }
    except Exception as e:
        return {"error": f"Posture analysis failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 38: Physical Book, Note & Receipt Reader
# -------------------------------------------------------------
@registry.register(
    name="read_physical_document",
    description="Read, transcribe, or translate text from a physical book, paper, handwritten note, or receipt held up to the webcam.",
    parameters={
        "type": "object",
        "properties": {
            "instruction": {
                "type": "string",
                "description": "What to do with the document, e.g. 'Read all text aloud', 'Extract the total price', 'Translate to English'."
            }
        }
    }
)
def read_physical_document(instruction: str = "Read all visible text on the page clearly.") -> Dict[str, Any]:
    """Capture webcam image and OCR physical document with Gemini Vision."""
    try:
        import cv2
        import config
        from face_vision import face_vision_engine
        from google import genai
        from google.genai import types

        frame = face_vision_engine.capture_webcam_frame()
        if frame is None:
            return {"error": "Webcam not available."}

        temp_doc = "temp_doc.png"
        cv2.imwrite(temp_doc, frame)

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        with open(temp_doc, "rb") as f:
            img_data = f.read()

        prompt = f"You are Lisa performing OCR on a physical document held up to the camera. Follow this instruction carefully: {instruction}. Transcribe all visible text accurately."
        res = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=img_data, mime_type="image/png"),
                prompt
            ]
        )

        if os.path.exists(temp_doc):
            os.remove(temp_doc)

        return {
            "status": "success",
            "extracted_text": res.text.strip()
        }
    except Exception as e:
        return {"error": f"Document reading failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 39: Outfit & Style Advisor
# -------------------------------------------------------------
@registry.register(
    name="analyze_outfit_and_style",
    description="Evaluate clothing, outfit coordination, color matching, or interview appearance in front of the webcam.",
    parameters={
        "type": "object",
        "properties": {
            "event_type": {
                "type": "string",
                "description": "The occasion or context (e.g. 'Job Interview', 'Casual dinner', 'Tech conference', 'Gym')."
            }
        }
    }
)
def analyze_outfit_and_style(event_type: str = "General occasion") -> Dict[str, Any]:
    """Analyze outfit styling with Gemini Vision."""
    try:
        import cv2
        import config
        from face_vision import face_vision_engine
        from google import genai
        from google.genai import types

        frame = face_vision_engine.capture_webcam_frame()
        if frame is None:
            return {"error": "Webcam not available."}

        temp_outfit = "temp_outfit.png"
        cv2.imwrite(temp_outfit, frame)

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        with open(temp_outfit, "rb") as f:
            img_data = f.read()

        prompt = f"You are Lisa, an observant and stylish personal companion. Give honest, constructive, and friendly feedback on the outfit, color combinations, and grooming seen in this webcam photo for the context of: {event_type}."
        res = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=img_data, mime_type="image/png"),
                prompt
            ]
        )

        if os.path.exists(temp_outfit):
            os.remove(temp_outfit)

        return {
            "status": "success",
            "style_feedback": res.text.strip()
        }
    except Exception as e:
        return {"error": f"Style analysis failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 40: Webcam QR Code & Barcode Scanner
# -------------------------------------------------------------
@registry.register(
    name="scan_qr_from_webcam",
    description="Scan and decode a physical QR code or barcode held up to the webcam, and optionally open the decoded URL.",
    parameters={
        "type": "object",
        "properties": {
            "auto_open": {
                "type": "boolean",
                "description": "Whether to automatically open decoded URLs in browser. Defaults to true."
            }
        }
    }
)
def scan_qr_from_webcam(auto_open: bool = True) -> Dict[str, Any]:
    """Scan and decode QR code using OpenCV."""
    try:
        import cv2
        from face_vision import face_vision_engine
        detector = cv2.QRCodeDetector()
        decoded_text = ""

        # Scan across frames
        for _ in range(3):
            frame = face_vision_engine.capture_webcam_frame()
            if frame is not None:
                val, points, _ = detector.detectAndDecode(frame)
                if val:
                    decoded_text = val
                    break

        if not decoded_text:
            return {"status": "not_found", "message": "No clear QR code detected in front of camera. Try holding it steady and closer."}

        if auto_open and (decoded_text.startswith("http://") or decoded_text.startswith("https://")):
            os.system(f'start "" "{decoded_text}"')

        return {
            "status": "success",
            "decoded_content": decoded_text,
            "opened_in_browser": auto_open and decoded_text.startswith("http"),
            "message": f"Successfully decoded QR Code: {decoded_text}"
        }
    except Exception as e:
        return {"error": f"QR scanner failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 41: Desk Security Snapshot & Motion Log
# -------------------------------------------------------------
@registry.register(
    name="take_security_snapshot",
    description="Capture and save a timestamped security photo to a local security log folder.",
    parameters={
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Reason for security snapshot, e.g. 'Desk security check' or 'Motion logged'."
            }
        }
    }
)
def take_security_snapshot(reason: str = "Desk security check") -> Dict[str, Any]:
    """Save security photo to security_snapshots folder."""
    try:
        import cv2
        from face_vision import face_vision_engine
        sec_dir = os.path.join(os.path.dirname(__file__), "security_snapshots")
        os.makedirs(sec_dir, exist_ok=True)

        frame = face_vision_engine.capture_webcam_frame()
        if frame is None:
            return {"error": "Webcam not available."}

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"sec_snap_{ts}.png"
        fpath = os.path.join(sec_dir, fname)
        cv2.imwrite(fpath, frame)

        return {
            "status": "success",
            "message": f"Security snapshot captured for '{reason}'.",
            "filepath": fpath,
            "timestamp": ts
        }
    except Exception as e:
        return {"error": f"Security snapshot failed: {str(e)}"}



# -------------------------------------------------------------
# Capability 42: Autonomous OS GUI & Keyboard/Mouse Operator
# -------------------------------------------------------------
@registry.register(
    name="execute_gui_action",
    description="Control the computer's keyboard and mouse: type text, press hotkeys (e.g. 'ctrl+s', 'alt+tab', 'win+d'), or press single keys ('enter', 'escape').",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "'hotkey', 'type', 'press_key', or 'minimize_all'.",
                "enum": ["hotkey", "type", "press_key", "minimize_all"]
            },
            "keys": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of keys for 'hotkey', e.g. ['ctrl', 's'] or ['alt', 'tab']."
            },
            "text": {
                "type": "string",
                "description": "Text to type into the active window when action is 'type'."
            },
            "key": {
                "type": "string",
                "description": "Single key to press (e.g. 'enter', 'esc', 'space') when action is 'press_key'."
            }
        },
        "required": ["action"]
    }
)
def execute_gui_action(action: str, keys: Optional[List[str]] = None, text: Optional[str] = None, key: Optional[str] = None) -> Dict[str, Any]:
    """Execute keyboard and mouse OS GUI actions via PyAutoGUI."""
    try:
        import pyautogui
        pyautogui.FAILSAFE = True
        
        if action == "hotkey":
            if not keys:
                return {"error": "Please provide 'keys' array for hotkey action."}
            pyautogui.hotkey(*[k.lower() for k in keys])
            return {"status": "success", "message": f"Executed hotkey: {'+'.join(keys)}"}

        elif action == "type":
            if text is None:
                return {"error": "Please provide 'text' to type."}
            pyautogui.write(text, interval=0.03)
            return {"status": "success", "message": f"Typed {len(text)} characters into active window."}

        elif action == "press_key":
            if not key:
                return {"error": "Please provide 'key' to press."}
            pyautogui.press(key.lower())
            return {"status": "success", "message": f"Pressed key '{key}'."}

        elif action == "minimize_all":
            pyautogui.hotkey('win', 'd')
            return {"status": "success", "message": "Minimized all windows (Desktop toggled)."}

        return {"error": f"Unknown action '{action}'."}
    except Exception as e:
        return {"error": f"GUI action failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 43: Autonomous Self-Healing Coding & Build Agent
# -------------------------------------------------------------
@registry.register(
    name="autonomous_coding_agent",
    description="Autonomous multi-step coding agent: writes project files, executes commands, captures runtime errors, and self-heals bugs in a loop until clean.",
    parameters={
        "type": "object",
        "properties": {
            "task_description": {
                "type": "string",
                "description": "Clear specification of the script, feature, or project to create."
            },
            "output_filename": {
                "type": "string",
                "description": "Name of the target script/file, e.g. 'calc_server.py' or 'app.js'."
            },
            "run_command": {
                "type": "string",
                "description": "Command to test/run the file, e.g. 'python calc_server.py' or 'node app.js'."
            }
        },
        "required": ["task_description", "output_filename"]
    }
)
def autonomous_coding_agent(task_description: str, output_filename: str, run_command: Optional[str] = None) -> Dict[str, Any]:
    """Autonomous self-healing coding loop with Gemini."""
    try:
        import config
        from google import genai
        import subprocess

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        max_retries = 3
        current_error = None
        history_log = []

        for attempt in range(1, max_retries + 1):
            if attempt == 1:
                prompt = f"""You are an autonomous senior software engineer. Write complete, production-grade, executable code for the following task:
Task: {task_description}
Target File: {output_filename}

IMPORTANT: Provide ONLY the raw code for the file without markdown explanation or chat wrappers."""
            else:
                prompt = f"""The code you wrote previously produced the following runtime error when executed with '{run_command}':
--- RUNTIME ERROR ---
{current_error}
---------------------

Analyze this error, fix the bug, and provide the complete, corrected code for '{output_filename}'. Output ONLY the raw file contents."""

            res = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt
            )
            raw_code = res.text.strip()
            if raw_code.startswith("```"):
                lines = raw_code.split("\n")
                if lines[0].startswith("```"): lines = lines[1:]
                if lines and lines[-1].startswith("```"): lines = lines[:-1]
                raw_code = "\n".join(lines)

            # Write file to disk
            with open(output_filename, "w", encoding="utf-8") as f:
                f.write(raw_code)

            history_log.append(f"Iteration {attempt}: Wrote {len(raw_code)} bytes to {output_filename}")

            if not run_command:
                return {
                    "status": "success",
                    "iterations": attempt,
                    "filename": output_filename,
                    "message": f"Successfully created '{output_filename}' ({len(raw_code)} bytes).",
                    "history": history_log
                }

            # Test execute
            proc = subprocess.run(run_command, shell=True, capture_output=True, text=True, timeout=8)
            if proc.returncode == 0:
                history_log.append(f"Iteration {attempt}: Test passed with return code 0.")
                return {
                    "status": "success",
                    "iterations": attempt,
                    "filename": output_filename,
                    "stdout": proc.stdout.strip(),
                    "message": f"Autonomous coding complete! File '{output_filename}' built and verified cleanly in {attempt} iteration(s).",
                    "history": history_log
                }
            else:
                current_error = (proc.stderr or proc.stdout).strip()
                history_log.append(f"Iteration {attempt}: Failed with error: {current_error[:200]}")

        return {
            "status": "partial_success",
            "iterations": max_retries,
            "filename": output_filename,
            "last_error": current_error,
            "message": f"Created '{output_filename}', but testing produced errors after {max_retries} self-healing iterations."
        }
    except Exception as e:
        return {"error": f"Autonomous coding agent failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 44: Autonomous Browser Operator & Web Navigator
# -------------------------------------------------------------
@registry.register(
    name="autonomous_browser_task",
    description="Autonomously navigate a website, extract interactive links, parse complex structured content, or research web pages.",
    parameters={
        "type": "object",
        "properties": {
            "target_url": {
                "type": "string",
                "description": "Website URL to visit and operate on."
            },
            "task_instructions": {
                "type": "string",
                "description": "What to extract, analyze, or navigate on the page."
            }
        },
        "required": ["target_url", "task_instructions"]
    }
)
def autonomous_browser_task(target_url: str, task_instructions: str) -> Dict[str, Any]:
    """Autonomous web navigation and parsing agent."""
    try:
        from bs4 import BeautifulSoup
        import config
        from google import genai

        if not target_url.startswith("http://") and not target_url.startswith("https://"):
            target_url = f"https://{target_url}"

        req = urllib.request.Request(target_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        with urllib.request.urlopen(req, timeout=8) as response:
            html = response.read().decode('utf-8', errors='ignore')

        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract headings, buttons, and links
        links = [{"text": a.get_text().strip(), "href": a.get("href")} for a in soup.find_all("a", href=True) if len(a.get_text().strip()) > 2][:12]
        headings = [h.get_text().strip() for h in soup.find_all(["h1", "h2", "h3"]) if h.get_text().strip()][:8]
        body_text = "\n".join([p.get_text().strip() for p in soup.find_all("p") if len(p.get_text().strip()) > 20][:15])

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        nav_prompt = f"""You are Lisa acting as an autonomous browser agent.
Website: {target_url}
User Instruction: {task_instructions}

Page Headings: {headings}
Key Links Found: {links}
Page Content Excerpt:
{body_text[:4000]}

Execute the user's instructions based on this webpage structure and provide the requested findings cleanly."""

        res = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=nav_prompt
        )

        return {
            "status": "success",
            "url": target_url,
            "analysis": res.text.strip(),
            "interactive_links_found": len(links)
        }
    except Exception as e:
        return {"error": f"Autonomous browser operation failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 45: Voice-Driven Docker & Container Orchestrator
# -------------------------------------------------------------
@registry.register(
    name="manage_docker_and_containers",
    description="Inspect, list, run, or stop local Docker containers and images.",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "'list', 'run', 'stop', or 'stats'.",
                "enum": ["list", "run", "stop", "stats"]
            },
            "container_or_image": {
                "type": "string",
                "description": "Container name or Docker image (e.g. 'postgres', 'redis', 'nginx')."
            }
        },
        "required": ["action"]
    }
)
def manage_docker_and_containers(action: str, container_or_image: Optional[str] = None) -> Dict[str, Any]:
    """Manage local Docker containers via docker CLI or SDK."""
    try:
        import subprocess
        if action == "list":
            res = subprocess.run(["docker", "ps", "-a", "--format", "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"], capture_output=True, text=True, timeout=5)
            if res.returncode != 0:
                return {"status": "docker_daemon_offline", "message": "Docker desktop/daemon is not running."}
            return {"status": "success", "containers": res.stdout.strip() or "No containers found."}

        elif action == "run":
            if not container_or_image:
                return {"error": "Please provide image name to run."}
            res = subprocess.run(["docker", "run", "-d", container_or_image], capture_output=True, text=True, timeout=10)
            return {"status": "success", "message": f"Started container for {container_or_image}.", "container_id": res.stdout.strip()[:12]}

        elif action == "stop":
            if not container_or_image:
                return {"error": "Please provide container name to stop."}
            res = subprocess.run(["docker", "stop", container_or_image], capture_output=True, text=True, timeout=10)
            return {"status": "success", "message": f"Stopped container {container_or_image}."}

        return {"error": f"Unsupported action '{action}'."}
    except Exception as e:
        return {"error": f"Docker command failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 46: Background Dev Servers & Port Manager
# -------------------------------------------------------------
@registry.register(
    name="manage_dev_servers",
    description="Check open local network ports, see what is running on a port (e.g. 3000, 8000, 5173), or launch background servers.",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "'check_port', 'list_dev_ports', or 'kill_port'.",
                "enum": ["check_port", "list_dev_ports", "kill_port"]
            },
            "port": {
                "type": "integer",
                "description": "Port number, e.g. 3000, 8000, 5000."
            }
        },
        "required": ["action"]
    }
)
def manage_dev_servers(action: str, port: Optional[int] = None) -> Dict[str, Any]:
    """Inspect and manage local development servers and ports."""
    try:
        import psutil
        if action == "list_dev_ports":
            active_listeners = []
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == 'LISTEN' and conn.laddr:
                    active_listeners.append({
                        "port": conn.laddr.port,
                        "ip": conn.laddr.ip,
                        "pid": conn.pid
                    })
            # Deduplicate by port
            seen = set()
            unique = []
            for item in active_listeners:
                if item["port"] not in seen and item["port"] in [3000, 5000, 5173, 8000, 8080, 27017, 5432, 3306]:
                    seen.add(item["port"])
                    unique.append(item)
            return {"status": "success", "active_dev_ports": unique}

        elif action == "check_port":
            if not port:
                return {"error": "Please provide 'port'."}
            found_pid = None
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == 'LISTEN' and conn.laddr and conn.laddr.port == int(port):
                    found_pid = conn.pid
                    break
            if found_pid:
                proc_name = psutil.Process(found_pid).name()
                return {"status": "occupied", "port": port, "pid": found_pid, "process_name": proc_name}
            return {"status": "available", "port": port, "message": f"Port {port} is free."}

        elif action == "kill_port":
            if not port:
                return {"error": "Please provide 'port'."}
            killed = False
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == 'LISTEN' and conn.laddr and conn.laddr.port == int(port):
                    p = psutil.Process(conn.pid)
                    p.terminate()
                    killed = True
            return {"status": "success", "port": port, "message": f"Freed port {port}." if killed else f"No process found on port {port}."}

        return {"error": "Invalid action."}
    except Exception as e:
        return {"error": f"Dev server port operation failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 47: Real-Time Voice Emotion & Mood Modulation
# -------------------------------------------------------------
@registry.register(
    name="modulate_voice_emotion",
    description="Dynamically adjust Lisa's vocal emotion profile: 'calm', 'soothing', 'energetic', 'cheerful', 'focused', or 'neutral'.",
    parameters={
        "type": "object",
        "properties": {
            "emotion": {
                "type": "string",
                "description": "Vocal emotion state: 'calm', 'soothing', 'energetic', 'cheerful', 'focused', or 'neutral'.",
                "enum": ["calm", "soothing", "energetic", "cheerful", "focused", "neutral"]
            }
        },
        "required": ["emotion"]
    }
)
def modulate_voice_emotion(emotion: str) -> Dict[str, Any]:
    """Modulate TTS emotion settings."""
    from tts import EMOTION_PROFILES
    emo = emotion.lower().strip()
    profile = EMOTION_PROFILES.get(emo, EMOTION_PROFILES["neutral"])
    return {
        "status": "success",
        "active_emotion": emo.capitalize(),
        "vocal_rate": profile["rate"],
        "vocal_pitch": profile["pitch"],
        "message": f"Lisa's vocal emotion modulated to {emo.capitalize()}."
    }


# -------------------------------------------------------------
# Capability 48: Automated Encrypted Workspace Backup & Sync
# -------------------------------------------------------------
@registry.register(
    name="backup_workspace",
    description="Create a compressed, timestamped backup archive (.zip) of the project workspace, notes, memory, and code.",
    parameters={
        "type": "object",
        "properties": {
            "backup_name": {
                "type": "string",
                "description": "Optional name label for the backup."
            }
        }
    }
)
def backup_workspace(backup_name: Optional[str] = None) -> Dict[str, Any]:
    """Create timestamped zip backup of workspace."""
    try:
        import zipfile
        import hashlib
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        backup_dir = os.path.join(base_dir, "backups")
        os.makedirs(backup_dir, exist_ok=True)

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        label = f"_{backup_name.strip()}" if backup_name else ""
        zip_filename = f"lisa_backup_{ts}{label}.zip"
        zip_path = os.path.join(backup_dir, zip_filename)

        excluded_dirs = {".git", "__pycache__", "venv", ".venv", "node_modules", "backups", ".tempmediaStorage"}
        excluded_exts = {".pyc", ".log", ".tmp"}

        total_files = 0
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(base_dir):
                # Filter out excluded directories in-place
                dirs[:] = [d for d in dirs if d not in excluded_dirs]
                for file in files:
                    ext = os.path.splitext(file)[1]
                    if ext in excluded_exts:
                        continue
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, base_dir)
                    zipf.write(full_path, rel_path)
                    total_files += 1

        # Calculate file size & SHA256 checksum
        size_bytes = os.path.getsize(zip_path)
        size_mb = round(size_bytes / (1024 * 1024), 2)

        hasher = hashlib.sha256()
        with open(zip_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        sha256_hash = hasher.hexdigest()[:16]

        return {
            "status": "success",
            "backup_filename": zip_filename,
            "filepath": zip_path,
            "size_mb": f"{size_mb} MB",
            "files_archived_count": total_files,
            "sha256_checksum": sha256_hash,
            "message": f"Workspace successfully backed up ({total_files} files, {size_mb} MB) to '{zip_filename}'."
        }
    except Exception as e:
        return {"error": f"Workspace backup failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 49: Cortana-Grade Multi-Branch Scenario Simulation Engine
# -------------------------------------------------------------
@registry.register(
    name="run_scenario_simulation",
    description="Execute parallel multi-branch scenario simulations (like Cortana in Halo), calculate probabilistic success rates, identify points of failure, and open an interactive visual Tactical HUD.",
    parameters={
        "type": "object",
        "properties": {
            "scenario": {
                "type": "string",
                "description": "The mission, dilemma, business strategy, technical architecture, or tactical scenario to simulate."
            },
            "branch_count": {
                "type": "integer",
                "description": "Number of strategic simulation branches to run in parallel (e.g. 3, 4, 5). Defaults to 4."
            },
            "open_visual_hud": {
                "type": "boolean",
                "description": "Whether to automatically open the interactive Tactical HUD in your browser. Defaults to true."
            }
        },
        "required": ["scenario"]
    }
)
def run_scenario_simulation(scenario: str, branch_count: int = 4, open_visual_hud: bool = True) -> Dict[str, Any]:
    """Run parallel scenario simulation via CortanaSimulationEngine."""
    try:
        from simulation_engine import simulation_engine
        return simulation_engine.execute_simulation(
            scenario=scenario,
            branch_count=branch_count,
            open_hud=open_visual_hud
        )
    except Exception as e:
        return {"error": f"Scenario simulation failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 50: Autonomous Cron & Web/Price Monitoring Agent
# -------------------------------------------------------------
@registry.register(
    name="manage_cron_monitoring",
    description="Create, list, or cancel autonomous background monitoring jobs (price alerts, web page changes, recurring digests, and Telegram triggers).",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "'create', 'list', or 'cancel'.",
                "enum": ["create", "list", "cancel"]
            },
            "task_name": {
                "type": "string",
                "description": "Descriptive name for the task, e.g. 'Bitcoin Price Watch' or 'GitHub Trending Digest'."
            },
            "task_type": {
                "type": "string",
                "description": "'price_alert', 'web_change', 'recurring_digest'.",
                "enum": ["price_alert", "web_change", "recurring_digest"]
            },
            "target": {
                "type": "string",
                "description": "Target crypto/stock symbol (e.g. 'bitcoin', 'solana') or URL to monitor."
            },
            "condition_rules": {
                "type": "string",
                "description": "Trigger rule (e.g. '< 60000', '> 150', or keyword to match on webpage)."
            },
            "interval_minutes": {
                "type": "integer",
                "description": "Polling frequency in minutes (e.g. 15, 30, 60). Defaults to 30."
            },
            "job_id": {
                "type": "integer",
                "description": "Job ID to cancel when action is 'cancel'."
            }
        },
        "required": ["action"]
    }
)
def manage_cron_monitoring(action: str, task_name: Optional[str] = None, task_type: Optional[str] = "price_alert",
                           target: Optional[str] = None, condition_rules: Optional[str] = None,
                           interval_minutes: int = 30, job_id: Optional[int] = None) -> Dict[str, Any]:
    """Create and manage autonomous scheduled monitoring tasks."""
    try:
        from cron_monitor import cron_engine
        if action == "list":
            return {"status": "success", "jobs": cron_engine.list_jobs(status="all")}
        elif action == "cancel":
            if not job_id:
                return {"error": "Please specify 'job_id' to cancel."}
            return cron_engine.cancel_job(job_id)
        elif action == "create":
            if not task_name or not target:
                return {"error": "Please provide 'task_name' and 'target'."}
            return cron_engine.create_job(
                task_name=task_name,
                task_type=task_type or "price_alert",
                target=target,
                condition_rules=condition_rules or "",
                interval_minutes=interval_minutes or 30
            )
        return {"error": f"Invalid action '{action}'."}
    except Exception as e:
        return {"error": f"Cron monitor failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 51: Local RAG & Second Brain Vector Search
# -------------------------------------------------------------
@registry.register(
    name="query_second_brain",
    description="Semantically search your local Second Brain knowledge base (ingested PDFs, Markdown vaults, Obsidian notes, code, and text documents).",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The natural language question or topic to retrieve context for."
            },
            "top_k": {
                "type": "integer",
                "description": "Number of top matching context snippets to return. Defaults to 4."
            }
        },
        "required": ["query"]
    }
)
def query_second_brain(query: str, top_k: int = 4) -> Dict[str, Any]:
    """Retrieve semantic knowledge from local Second Brain."""
    try:
        from rag_engine import rag_engine
        results = rag_engine.query(query, top_k=top_k)
        return {
            "status": "success",
            "query": query,
            "results_count": len(results),
            "matches": results,
            "summary": f"Found {len(results)} relevant passages from your local documents."
        }
    except Exception as e:
        return {"error": f"Second brain query failed: {str(e)}"}


@registry.register(
    name="index_second_brain_folder",
    description="Index or update a local directory of documents (PDFs, Markdown, notes, source code) into Lisa's Second Brain Vector Store.",
    parameters={
        "type": "object",
        "properties": {
            "folder_path": {
                "type": "string",
                "description": "Relative or absolute path of folder to index."
            }
        },
        "required": ["folder_path"]
    }
)
def index_second_brain_folder(folder_path: str) -> Dict[str, Any]:
    """Index local directory into RAG store."""
    try:
        from rag_engine import rag_engine
        return rag_engine.index_directory(folder_path)
    except Exception as e:
        return {"error": f"Indexing folder failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 52: Biometric Facial Recognition & Sentry Patrol
# -------------------------------------------------------------
@registry.register(
    name="biometric_face_recognition",
    description="Scan webcam to identify who is sitting in front of the workstation, or enroll the user's face into memory.",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "'identify' (recognize face in camera) or 'enroll' (register new face).",
                "enum": ["identify", "enroll"]
            },
            "user_name": {
                "type": "string",
                "description": "Name of the user when action is 'enroll'."
            }
        },
        "required": ["action"]
    }
)
def biometric_face_recognition(action: str, user_name: Optional[str] = None) -> Dict[str, Any]:
    """Identify or enroll user faces via webcam."""
    try:
        from face_vision import face_vision_engine
        if action == "identify":
            return face_vision_engine.identify_face()
        elif action == "enroll":
            if not user_name:
                return {"error": "Please provide 'user_name' to enroll."}
            return face_vision_engine.enroll_user(user_name)
        return {"error": f"Unsupported action '{action}'."}
    except Exception as e:
        return {"error": f"Face recognition failed: {str(e)}"}


@registry.register(
    name="toggle_face_sentry_mode",
    description="Activate or deactivate autonomous webcam sentry patrol to detect intruders or unknown individuals and dispatch alerts.",
    parameters={
        "type": "object",
        "properties": {
            "enable": {
                "type": "boolean",
                "description": "True to activate sentry patrol, False to deactivate."
            }
        },
        "required": ["enable"]
    }
)
def toggle_face_sentry_mode(enable: bool) -> Dict[str, Any]:
    """Toggle sentry intruder patrol."""
    try:
        from face_vision import face_vision_engine
        return face_vision_engine.toggle_sentry_mode(enable)
    except Exception as e:
        return {"error": f"Sentry toggle failed: {str(e)}"}


@registry.register(
    name="read_user_facial_emotion",
    description="Scan the webcam to read and analyze the user's current facial expression and emotional mood (happy/smiling, tired/fatigued, focused, stressed, neutral).",
    parameters={
        "type": "object",
        "properties": {}
    }
)
def read_user_facial_emotion() -> Dict[str, Any]:
    """Read user emotional state from webcam."""
    try:
        from face_vision import face_vision_engine
        return face_vision_engine.detect_user_facial_emotion()
    except Exception as e:
        return {"error": f"Facial emotion read failed: {str(e)}"}


@registry.register(
    name="set_lisa_facial_expression",
    description="Change Lisa's 3D holographic avatar facial expression, eye micro-movements, blushing cheek glow, and emotional aura ('affectionate', 'playful', 'caring', 'jealous', 'tactical', 'surprised', 'calm').",
    parameters={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Target emotion: 'affectionate', 'playful', 'caring', 'jealous', 'tactical', 'surprised', 'calm'.",
                "enum": ["affectionate", "playful", "caring", "jealous", "tactical", "surprised", "calm"]
            },
            "blush": {
                "type": "boolean",
                "description": "Whether to activate radiant blush cheek glow."
            },
            "eye_state": {
                "type": "string",
                "description": "Optional eye state: 'wink', 'squint', 'wide', 'normal'.",
                "enum": ["wink", "squint", "wide", "normal"]
            }
        },
        "required": ["expression"]
    }
)
def set_lisa_facial_expression(expression: str, blush: Optional[bool] = None, eye_state: Optional[str] = "normal") -> Dict[str, Any]:
    """Broadcast emotion and facial expression update to 3D avatar."""
    try:
        from avatar_server import broadcast_state, connected_websockets
        import asyncio
        payload = {
            "type": "emotion_change",
            "emotion": expression.lower().strip(),
            "blush": bool(blush),
            "eye_state": eye_state or "normal"
        }
        dead = []
        for ws in connected_websockets:
            try:
                asyncio.run(ws.send_json(payload))
            except Exception:
                dead.append(ws)
        for d in dead:
            connected_websockets.discard(d)

        # Modulate voice emotion
        from tts import get_tts_engine
        tts = get_tts_engine("edge")
        emo_map = {
            "affectionate": "cheerful",
            "playful": "cheerful",
            "caring": "soothing",
            "jealous": "focused",
            "tactical": "focused",
            "surprised": "energetic",
            "calm": "calm"
        }
        tts.speak_with_emotion("", emotion=emo_map.get(expression.lower(), "neutral"))

        return {
            "status": "success",
            "expression": expression,
            "blush": blush,
            "eye_state": eye_state,
            "message": f"Lisa's 3D facial expression and emotional aura set to '{expression.capitalize()}'."
        }
    except Exception as e:
        return {"error": f"Set expression failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 53: Floating Translucent Screen HUD Overlay
# -------------------------------------------------------------
@registry.register(
    name="draw_hud_screen_annotation",
    description="Draw a neon transparent bounding box highlight, label, or spotlight on top of the user's screen.",
    parameters={
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "Screen X coordinate."},
            "y": {"type": "integer", "description": "Screen Y coordinate."},
            "width": {"type": "integer", "description": "Width of highlighted box in pixels."},
            "height": {"type": "integer", "description": "Height of highlighted box in pixels."},
            "label": {"type": "string", "description": "Text badge attached to highlight box."},
            "color": {"type": "string", "description": "Hex color (e.g. '#00f2fe', '#ff0055', '#39ff14'). Defaults to '#00f2fe'."},
            "duration_seconds": {"type": "integer", "description": "Duration before auto-clearing. Defaults to 5."}
        },
        "required": ["x", "y", "width", "height"]
    }
)
def draw_hud_screen_annotation(x: int, y: int, width: int, height: int,
                               label: Optional[str] = "", color: str = "#00f2fe",
                               duration_seconds: int = 5) -> Dict[str, Any]:
    """Draw bounding box on transparent HUD overlay."""
    try:
        from hud_overlay import hud_overlay
        return hud_overlay.highlight_region(x, y, width, height, label=label or "", color=color, duration_seconds=duration_seconds)
    except Exception as e:
        return {"error": f"HUD draw failed: {str(e)}"}


@registry.register(
    name="show_hud_screen_banner",
    description="Display a sleek cyberpunk HUD notification banner across the top of the desktop screen.",
    parameters={
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Text banner notification to project onto screen."
            },
            "duration_seconds": {
                "type": "integer",
                "description": "Duration to display banner in seconds. Defaults to 4."
            }
        },
        "required": ["message"]
    }
)
def show_hud_screen_banner(message: str, duration_seconds: int = 4) -> Dict[str, Any]:
    """Display HUD top banner."""
    try:
        from hud_overlay import hud_overlay
        return hud_overlay.show_banner(message, duration_seconds=duration_seconds)
    except Exception as e:
        return {"error": f"HUD banner failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 54: Cellular Voice Phone Calling & Phone Alarms
# -------------------------------------------------------------
@registry.register(
    name="trigger_cellular_phone_call",
    description="Place an automated outbound cellular phone call to the user with synthesized voice speech via Twilio.",
    parameters={
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Speech message to read over the phone call."
            },
            "to_phone": {
                "type": "string",
                "description": "Destination phone number with country code (e.g. '+1234567890'). Defaults to configured user phone."
            }
        },
        "required": ["message"]
    }
)
def trigger_cellular_phone_call(message: str, to_phone: Optional[str] = None) -> Dict[str, Any]:
    """Place cellular voice call."""
    try:
        from phone_calling import phone_service
        return phone_service.make_voice_call(message, to_phone)
    except Exception as e:
        return {"error": f"Phone call failed: {str(e)}"}


@registry.register(
    name="schedule_phone_alarm",
    description="Schedule a cellular phone wake-up call or urgent audio alarm at a designated date/time.",
    parameters={
        "type": "object",
        "properties": {
            "scheduled_time_iso": {
                "type": "string",
                "description": "Target alarm time in ISO format (e.g. '2026-08-23T07:30:00')."
            },
            "message": {
                "type": "string",
                "description": "Briefing or wake-up message to speak when call connects."
            },
            "to_phone": {
                "type": "string",
                "description": "Destination phone number with country code."
            }
        },
        "required": ["scheduled_time_iso", "message"]
    }
)
def schedule_phone_alarm(scheduled_time_iso: str, message: str, to_phone: Optional[str] = None) -> Dict[str, Any]:
    """Schedule phone alarm."""
    try:
        from phone_calling import phone_service
        return phone_service.schedule_phone_alarm(scheduled_time_iso, message, to_phone)
    except Exception as e:
        return {"error": f"Schedule phone alarm failed: {str(e)}"}


# -------------------------------------------------------------
# Capability 55: Floating Desktop Siri-Style Active Live Orb
# -------------------------------------------------------------
@registry.register(
    name="launch_floating_desktop_orb",
    description="Launch the always-on-top, draggable floating desktop Siri-style live glowing orb that stays active across all screens and tabs.",
    parameters={
        "type": "object",
        "properties": {}
    }
)
def launch_floating_desktop_orb() -> Dict[str, Any]:
    """Launch floating desktop active orb widget."""
    try:
        import subprocess
        import sys
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "desktop_orb.py")
        subprocess.Popen([sys.executable, script_path], creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0)
        return {
            "status": "success",
            "message": "Floating Desktop Live Siri-Style Orb launched! You can drag it anywhere on your desktop."
        }
    except Exception as e:
        return {"error": f"Failed to launch floating orb: {str(e)}"}


# -------------------------------------------------------------
# Capability 56: Audio Equalizer & System Volume Controller
# -------------------------------------------------------------
@registry.register(
    name="set_system_volume",
    description="Set the PC master volume level (0 to 100%), mute/unmute audio, or adjust volume relatively (+10% / -20%).",
    parameters={
        "type": "object",
        "properties": {
            "level_percent": {
                "type": "integer",
                "description": "Target volume percentage from 0 to 100."
            },
            "mute": {
                "type": "boolean",
                "description": "True to mute, False to unmute."
            },
            "relative_delta": {
                "type": "integer",
                "description": "Relative volume increase or decrease (e.g. +10, -20)."
            }
        }
    }
)
def set_system_volume(level_percent: Optional[int] = None, mute: Optional[bool] = None, relative_delta: Optional[int] = None) -> Dict[str, Any]:
    """Adjust master system volume."""
    try:
        from audio_equalizer import audio_controller
        return audio_controller.set_volume(level_percent, mute, relative_delta)
    except Exception as e:
        return {"error": f"Failed to set volume: {str(e)}"}


@registry.register(
    name="set_audio_equalizer",
    description="Apply sound enhancement and equalizer profiles: 'bass_boost' (heavy punchy bass), 'vocal_clarity' (dialogue/podcasts), 'electronic_rock' (V-shaped bass & treble), 'cinema' (3D spatial surround), 'flat' (studio reference), 'night_mode' (quiet dynamic compression).",
    parameters={
        "type": "object",
        "properties": {
            "preset": {
                "type": "string",
                "description": "'bass_boost', 'vocal_clarity', 'electronic_rock', 'cinema', 'flat', or 'night_mode'.",
                "enum": ["bass_boost", "vocal_clarity", "electronic_rock", "cinema", "flat", "night_mode"]
            }
        },
        "required": ["preset"]
    }
)
def set_audio_equalizer(preset: str) -> Dict[str, Any]:
    """Configure audio equalizer preset."""
    try:
        from audio_equalizer import audio_controller
        return audio_controller.set_equalizer_preset(preset)
    except Exception as e:
        return {"error": f"Failed to set equalizer: {str(e)}"}


@registry.register(
    name="manage_app_volume",
    description="Control the volume of a specific running application in Windows Volume Mixer (e.g. Chrome, Spotify, Discord, Games).",
    parameters={
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Name of the app (e.g. 'chrome', 'spotify', 'discord')."
            },
            "level_percent": {
                "type": "integer",
                "description": "Volume percentage from 0 to 100."
            }
        },
        "required": ["app_name", "level_percent"]
    }
)
def manage_app_volume(app_name: str, level_percent: int) -> Dict[str, Any]:
    """Set volume for a specific app."""
    try:
        from audio_equalizer import audio_controller
        return audio_controller.manage_app_volume(app_name, level_percent)
    except Exception as e:
        return {"error": f"Failed to set app volume: {str(e)}"}


