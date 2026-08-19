"""Portable helpers for invoking FFmpeg without invoking a shell."""
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Iterable


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def check_ffmpeg():
    if not ffmpeg_available() or not ffprobe_available():
        raise RuntimeError(
            "FFmpeg e FFprobe devem estar instalados e disponíveis no PATH."
        )


def run_ffmpeg(arguments: Iterable[str], *, timeout: int | None = None, loglevel: str = "error"):
    """Run FFmpeg with bounded diagnostics instead of accumulating verbose logs."""
    check_ffmpeg()
    command = ["ffmpeg", "-hide_banner", "-loglevel", loglevel, "-nostdin", *map(str, arguments)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("O processamento excedeu o tempo máximo permitido.") from exc
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:] or "FFmpeg não conseguiu processar o arquivo.")
    return result


def supports_filter(name: str) -> bool:
    check_ffmpeg()
    result = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True)
    return result.returncode == 0 and any(
        re.search(rf"\s{re.escape(name)}\s", line) for line in result.stdout.splitlines()
    )


def probe(path: str | Path):
    check_ffmpeg()
    command = [
        "ffprobe", "-v", "error",
        "-show_entries",
        "format=duration,bit_rate,format_name:"
        "stream=index,codec_type,codec_name,sample_rate,channels,channel_layout,bit_rate",
        "-of", "json", str(path)
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:] or "FFprobe não conseguiu ler o arquivo.")
    data = json.loads(result.stdout or "{}")
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    return {
        "duration": fmt.get("duration", 0),
        "bit_rate": fmt.get("bit_rate", 0),
        "format_name": fmt.get("format_name", ""),
        "streams": streams,
        "audio_streams": audio_streams,
        "has_video": any(s.get("codec_type") == "video" for s in streams),
        "has_audio": bool(audio_streams),
        "audio_codec": audio_streams[0].get("codec_name") if audio_streams else None,
        "sample_rate": int(audio_streams[0].get("sample_rate") or 0) if audio_streams else 0,
        "channels": int(audio_streams[0].get("channels") or 0) if audio_streams else 0,
    }
