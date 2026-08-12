from pathlib import Path
from mutagen import File as MutagenFile
from .ffmpeg import probe

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".webm",
    ".mpeg", ".mpg", ".m4v"
}


def scan_library(folder: Path, allowed_extensions):
    files = []
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix.lower() in allowed_extensions:
            try:
                files.append(get_audio_metadata(path))
            except Exception:
                files.append({
                    "path": str(path), "name": path.name,
                    "title": path.stem, "artist": "", "album": "",
                    "extension": path.suffix.lower(), "duration": 0,
                    "duration_formatted": "--:--", "size": path.stat().st_size,
                    "is_video": path.suffix.lower() in VIDEO_EXTENSIONS
                })
    return files


def get_audio_metadata(path: Path):
    probe_data = probe(path)
    duration = float(probe_data.get("duration", 0) or 0)
    bitrate = int(probe_data.get("bit_rate", 0) or 0)

    title, artist, album = path.stem, "", ""

    try:
        audio = MutagenFile(path, easy=True)
        if audio:
            title = (audio.get("title") or [path.stem])[0]
            artist = (audio.get("artist") or [""])[0]
            album = (audio.get("album") or [""])[0]
    except Exception:
        pass

    return {
        "path": str(path), "name": path.name, "title": title,
        "artist": artist, "album": album,
        "extension": path.suffix.lower(), "duration": duration,
        "duration_formatted": format_duration(duration),
        "bitrate": bitrate,
        "bitrate_formatted": f"{round(bitrate / 1000)} kbps" if bitrate else "",
        "size": path.stat().st_size,
        "is_video": path.suffix.lower() in VIDEO_EXTENSIONS
    }


def format_duration(seconds):
    seconds = int(seconds)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
