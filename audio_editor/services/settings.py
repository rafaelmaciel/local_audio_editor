from pathlib import Path
import json
import copy

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE_DIR / "config"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "identity": {
        "title": "Audio Editor Local",
        "subtitle": "Editor de músicas executado no próprio computador",
        "logo": "",
        "logo_type": "emoji",
        "logo_value": "🎵"
    },
    "appearance": {
        "theme": "dark",
        "primary": "#6C63FF",
        "secondary": "#252936",
        "background": "#111318",
        "card": "#1B1E27",
        "text": "#F5F7FA",
        "muted": "#9CA3AF",
        "accent": "#00D4FF",
        "success": "#22C55E",
        "danger": "#EF4444",
        "warning": "#F59E0B",
        "font_size": "normal",
        "density": "normal",
        "border_radius": 10
    }
}


def _merge(default, current):
    result = copy.deepcopy(default)
    if isinstance(default, dict) and isinstance(current, dict):
        for key, value in current.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = _merge(result[key], value)
            else:
                result[key] = value
    return result


def load_settings():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS)
        return copy.deepcopy(DEFAULT_SETTINGS)

    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        merged = _merge(DEFAULT_SETTINGS, data)
        if merged != data:
            save_settings(merged)
        return merged
    except (OSError, json.JSONDecodeError):
        save_settings(DEFAULT_SETTINGS)
        return copy.deepcopy(DEFAULT_SETTINGS)


def save_settings(data):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    merged = _merge(DEFAULT_SETTINGS, data)
    SETTINGS_FILE.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return merged


def reset_settings():
    save_settings(DEFAULT_SETTINGS)
    return copy.deepcopy(DEFAULT_SETTINGS)
