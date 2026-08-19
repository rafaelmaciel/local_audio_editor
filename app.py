from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import uuid

from audio_editor.services.library import scan_library, get_audio_metadata
from audio_editor.services.processor import process_audio, process_batch, level_folder, pitch_shift_file, pitch_shift_folder
from audio_editor.services.analyzer import analyze_folder
from audio_editor.services.settings import load_settings, save_settings, reset_settings
from audio_editor.services.karaoke import analyze_path as karaoke_analyze_path, analyze_folder as karaoke_analyze_folder, VOCAL_PROFILES
from audio_editor.services.ffmpeg import ffmpeg_available, ffprobe_available, supports_filter
from audio_editor.services.jobs import jobs

BASE_DIR = Path(__file__).resolve().parent
EXPORT_DIR = BASE_DIR / "exports"
EXPORT_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".mp4", ".mkv", ".avi", ".mov", ".webm", ".mpeg", ".mpg", ".m4v"}

FRIENDLY_VOLUME_TARGETS = {"soft": -16.0, "balanced": -14.0, "strong": -11.0}
FRIENDLY_DYNAMICS_TARGETS = {"uniform": 7.0, "natural": 11.0, "contrasted": 15.0}


def normalization_targets(data):
    """Accept the original technical API as well as the new friendly controls."""
    lufs = data.get("target_lufs")
    lra = data.get("target_lra")
    if lufs is None:
        lufs = FRIENDLY_VOLUME_TARGETS.get(data.get("volume_style"), -14.0)
    if lra is None:
        lra = FRIENDLY_DYNAMICS_TARGETS.get(data.get("dynamics_style"), 11.0)
    return float(lufs), float(lra)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def status():
    return jsonify({
        "ffmpeg": ffmpeg_available() and ffprobe_available(),
        "rubberband": supports_filter("rubberband") if ffmpeg_available() and ffprobe_available() else False,
        "version": "0.1.0"
    })


@app.post("/api/library")
def library():
    data = request.get_json(silent=True) or {}
    folder = Path(data.get("path", "")).expanduser()

    if not folder.exists() or not folder.is_dir():
        return jsonify({"error": "A pasta informada não existe ou não é uma pasta."}), 400

    return jsonify({
        "path": str(folder),
        "files": scan_library(folder, ALLOWED_EXTENSIONS)
    })



@app.post("/api/analyze")
def analyze():
    data=request.get_json(silent=True) or {}
    folder=Path(data.get("folder","")).expanduser()
    if not folder.is_dir(): return jsonify({"error":"A pasta informada não existe ou não é uma pasta."}),400
    try: return jsonify(analyze_folder(folder, ALLOWED_EXTENSIONS))
    except Exception as exc: return jsonify({"error":str(exc)}),500

@app.post("/api/level")
def level():
    data=request.get_json(silent=True) or {}
    folder=Path(data.get("folder","")).expanduser()
    if not folder.is_dir(): return jsonify({"error":"A pasta informada não existe ou não é uma pasta."}),400
    try:
        target_lufs, target_lra = normalization_targets(data)
        job = jobs.submit(lambda **job_args: level_folder(
            folder, EXPORT_DIR, target_lufs, target_lra, data.get("bitrate", "192k"),
            data.get("mode", "replace"), **job_args
        ))
        return jsonify(job), 202
    except Exception as exc: return jsonify({"error":str(exc)}),500


@app.get("/api/jobs/<job_id>")
def get_job(job_id):
    job = jobs.snapshot(job_id)
    if not job:
        return jsonify({"error": "Tarefa não encontrada."}), 404
    return jsonify(job)


@app.post("/api/jobs/<job_id>/cancel")
def cancel_job(job_id):
    job = jobs.cancel(job_id)
    if not job:
        return jsonify({"error": "Tarefa não encontrada."}), 404
    return jsonify(job)



@app.get("/api/settings")
def get_settings():
    return jsonify(load_settings())


@app.post("/api/settings")
def update_settings():
    data = request.get_json(silent=True) or {}
    try:
        current = load_settings()
        if isinstance(data.get("identity"), dict):
            current["identity"].update(data["identity"])
        if isinstance(data.get("appearance"), dict):
            current["appearance"].update(data["appearance"])
        return jsonify(save_settings(current))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/api/settings/reset")
def reset_app_settings():
    try:
        return jsonify(reset_settings())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/api/karaoke/analyze")
def karaoke_analyze():
    data=request.get_json(silent=True) or {}
    path=Path(data.get("path","")).expanduser()
    profile=data.get("profile","baritone")
    if profile not in VOCAL_PROFILES:
        return jsonify({"error":"Perfil vocal inválido."}),400
    if not path.exists():
        return jsonify({"error":"Arquivo ou pasta não encontrado."}),400
    try:
        if path.is_dir():
            return jsonify(karaoke_analyze_folder(path,profile))
        return jsonify(karaoke_analyze_path(path,profile))
    except Exception as exc:
        return jsonify({"error":str(exc)}),500


@app.post("/api/karaoke/transpose")
def karaoke_transpose():
    data=request.get_json(silent=True) or {}
    mode=data.get("mode","replace")
    semitones=float(data.get("semitones",0))
    bitrate=data.get("bitrate","192k")
    path=Path(data.get("path","")).expanduser()

    if not path.exists():
        return jsonify({"error":"Arquivo ou pasta não encontrado."}),400
    if not -12 <= semitones <= 12:
        return jsonify({"error":"A transposição deve estar entre -12 e +12 semitons."}),400

    try:
        if path.is_dir():
            shifts=data.get("semitones_map",{})
            job = jobs.submit(lambda **job_args: pitch_shift_folder(
                path, EXPORT_DIR, shifts, mode, bitrate, **job_args
            ))
            return jsonify(job), 202
        return jsonify(pitch_shift_file(path,EXPORT_DIR,semitones,mode,bitrate))
    except Exception as exc:
        return jsonify({"error":str(exc)}),500


@app.post("/api/batch")
def batch_process():
    data = request.get_json(silent=True) or {}
    folder = Path(data.get("folder", "")).expanduser()
    if not folder.exists() or not folder.is_dir():
        return jsonify({"error": "A pasta informada não existe ou não é uma pasta."}), 400
    try:
        job = jobs.submit(lambda **job_args: process_batch(
            folder, EXPORT_DIR,
            float(data.get("volume_db", 0)), float(data.get("bass_db", 0)),
            float(data.get("mid_db", 0)), float(data.get("treble_db", 0)),
            float(data.get("intensity", 0)), data.get("output_format", "mp3"),
            data.get("bitrate", "192k"), data.get("mode", "replace"), **job_args
        ))
        return jsonify(job), 202
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@app.get("/api/audio")
def audio_metadata():
    path = Path(request.args.get("path", "")).expanduser()

    if not path.exists() or path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "Arquivo de áudio inválido."}), 400

    try:
        return jsonify(get_audio_metadata(path))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.get("/api/stream")
def stream():
    path = Path(request.args.get("path", "")).expanduser()

    if not path.exists() or path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "Arquivo inválido."}), 400

    return send_file(path, conditional=True)


@app.post("/api/process")
def process():
    data = request.get_json(silent=True) or {}
    source = Path(data.get("source", "")).expanduser()

    if not source.exists() or source.suffix.lower() not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "Arquivo de origem inválido."}), 400

    try:
        result = process_audio(
            source=source,
            output_dir=EXPORT_DIR,
            start_ms=int(data.get("start_ms", 0)),
            end_ms=data.get("end_ms"),
            volume_db=float(data.get("volume_db", 0)),
            fade_in_ms=int(data.get("fade_in_ms", 0)),
            fade_out_ms=int(data.get("fade_out_ms", 0)),
            action=data.get("action", "export"),
            output_format=data.get("output_format", "mp3"),
            bitrate=data.get("bitrate", "192k"),
        )

        return jsonify({
            "success": True,
            "filename": result.name,
            "download_url": f"/api/download/{result.name}"
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.get("/api/download/<filename>")
def download(filename):
    safe_name = secure_filename(filename)
    path = EXPORT_DIR / safe_name

    if not path.exists() or path.parent != EXPORT_DIR:
        return jsonify({"error": "Arquivo não encontrado."}), 404

    return send_file(path, as_attachment=True, download_name=path.name)


if __name__ == "__main__":
    # Debug reload starts a second process and breaks in-memory job state.
    app.run(host="127.0.0.1", port=5001, debug=False)
