from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import json
import re

from .ffmpeg import check_ffmpeg, run_ffmpeg

_CACHE = {}


def analyze_file(path):
    """Measure a file once per modification time; FFmpeg remains the authority."""
    path = Path(path)
    key = (str(path.resolve()), path.stat().st_size, path.stat().st_mtime_ns)
    if key in _CACHE:
        return _CACHE[key].copy()
    check_ffmpeg()
    result = run_ffmpeg([
        "-i", str(path), "-af", "loudnorm=I=-14:LRA=11:TP=-1.0:print_format=json",
        "-f", "null", "-",
    ], loglevel="info")
    matches = re.findall(r'\{\s*"input_i".*?\}', result.stderr, re.S)
    if not matches:
        raise RuntimeError("FFmpeg não retornou os dados de loudness.")
    data = json.loads(matches[-1])
    value = {"path": str(path), "name": path.name, "lufs": float(data["input_i"]),
             "lra": float(data["input_lra"]), "true_peak": float(data["input_tp"])}
    _CACHE[key] = value
    return value.copy()


def analyze_folder(folder, allowed, workers=4):
    files = [p for p in sorted(Path(folder).rglob("*")) if p.is_file() and p.suffix.lower() in allowed]
    if not files: raise ValueError("Nenhum arquivo de áudio ou vídeo encontrado.")
    ok, errors = [], []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(files))), thread_name_prefix="loudness") as executor:
        futures = {executor.submit(analyze_file, file): file for file in files}
        for future in as_completed(futures):
            file = futures[future]
            try: ok.append(future.result())
            except Exception as exc: errors.append({"path": str(file), "name": file.name, "error": str(exc)})
    ok.sort(key=lambda item: item["path"])
    if not ok: raise RuntimeError("Não foi possível analisar nenhum arquivo.")
    average = {key: round(sum(item[key] for item in ok) / len(ok), 2) for key in ("lufs", "lra", "true_peak")}
    median = {key: round(sorted(item[key] for item in ok)[len(ok)//2], 2) for key in ("lufs", "lra", "true_peak")}
    return {"success": True, "count": len(ok), "failed_count": len(errors), "files": ok, "errors": errors,
            "average": average, "median": median,
            "recommended": {"lufs": -14.0, "lra": 11.0, "true_peak": -1.0}}
