import shutil
import subprocess
import json


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def check_ffmpeg():
    if not ffmpeg_available():
        raise RuntimeError(
            "FFmpeg não foi encontrado. Instale o FFmpeg e coloque-o no PATH."
        )


def probe(path):
    check_ffmpeg()
    command = [
        "ffprobe", "-v", "error",
        "-show_entries",
        "format=duration,bit_rate:stream=index,codec_type,codec_name",
        "-of", "json", str(path)
    ]
    result = subprocess.run(
        command, capture_output=True, text=True, check=True
    )
    data = json.loads(result.stdout or "{}")
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    return {
        "duration": fmt.get("duration", 0),
        "bit_rate": fmt.get("bit_rate", 0),
        "streams": streams,
        "has_video": any(s.get("codec_type") == "video" for s in streams),
        "has_audio": any(s.get("codec_type") == "audio" for s in streams),
    }
