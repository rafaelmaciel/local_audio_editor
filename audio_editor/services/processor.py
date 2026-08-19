"""Audio/video processing built around streaming FFmpeg filter graphs."""
from __future__ import annotations

import json
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .ffmpeg import check_ffmpeg, probe, run_ffmpeg, supports_filter

AUDIO_EXT = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma"}
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".mpeg", ".mpg", ".m4v"}
AUDIO_OUTPUTS = {"mp3", "wav", "flac", "ogg"}
TRUE_PEAK_LIMIT = 0.891251  # -1 dBFS, expressed as a linear FFmpeg limiter value.


def _files(folder):
    return [p for p in sorted(Path(folder).rglob("*")) if p.is_file() and p.suffix.lower() in AUDIO_EXT | VIDEO_EXT]


def _safe_bitrate(value: str) -> str:
    if not re.fullmatch(r"(?:64|96|128|160|192|224|256|320)k", str(value)):
        raise ValueError("Bitrate inválido.")
    return str(value)


def _audio_codec_args(extension: str, bitrate: str, *, lossless: bool = False):
    extension = extension.lower().lstrip(".")
    if extension == "mp3": return ["-c:a", "libmp3lame", "-b:a", bitrate]
    if extension == "wav": return ["-c:a", "pcm_s24le"]
    if extension == "flac": return ["-c:a", "flac"]
    if extension == "ogg": return ["-c:a", "libvorbis", "-q:a", "6"]
    if extension in {"m4a", "aac", "mp4", "m4v", "mov", "mkv", "avi", "mpeg", "mpg"}: return ["-c:a", "aac", "-b:a", bitrate]
    if extension == "webm": return ["-c:a", "libopus", "-b:a", bitrate]
    if extension == "wma": return ["-c:a", "wmav2", "-b:a", bitrate]
    raise ValueError(f"Não há codificador portável configurado para .{extension}.")


def _output_path(source: Path, outdir: Path, label: str, *, mode: str, extension: str | None = None) -> Path:
    ext = source.suffix if mode == "replace" else f".{extension or source.suffix.lstrip('.')}"
    # A hidden sibling is necessary for atomic replacement on either Windows or Linux.
    prefix = "." if mode == "replace" else ""
    return outdir / f"{prefix}{source.stem}_{label}_{uuid.uuid4().hex[:8]}{ext}"


def _replace_original_safely(source: Path, generated: Path) -> Path:
    if not generated.exists() or generated.stat().st_size == 0:
        raise RuntimeError("O arquivo processado não foi gerado corretamente.")
    backup = source.with_name(f".{source.name}.audio_editor_backup")
    try:
        if backup.exists(): backup.unlink()
        source.replace(backup)
        generated.replace(source)
        backup.unlink(missing_ok=True)
    except Exception:
        if not source.exists() and backup.exists(): backup.replace(source)
        raise
    return source


def _finalize(source: Path, generated: Path, mode: str) -> Path:
    return _replace_original_safely(source, generated) if mode == "replace" else generated


def _run_audio(source: Path, output: Path, filters: list[str], codec_args: list[str], *, start: float | None = None, duration: float | None = None):
    args = ["-y", "-i", str(source)]
    if start is not None:
        args += ["-ss", f"{start:.6f}"]
    if duration is not None:
        args += ["-t", f"{duration:.6f}"]
    args += ["-map", "0:a:0?", "-map_metadata", "0", "-map_chapters", "0", "-vn"]
    if filters: args += ["-af", ",".join(filters)]
    args += codec_args + [str(output)]
    run_ffmpeg(args)


def _run_video(source: Path, output: Path, filters: list[str], bitrate: str, *, start: float | None = None, duration: float | None = None):
    # Accurate cutting deliberately seeks after input. Video stream-copy is fast and lossless.
    args = ["-y", "-i", str(source)]
    if start is not None: args += ["-ss", f"{start:.6f}"]
    if duration is not None: args += ["-t", f"{duration:.6f}"]
    args += ["-map", "0:v:0?", "-map", "0:a:0?", "-map_metadata", "0", "-map_chapters", "0", "-c:v", "copy"]
    if filters: args += ["-af", ",".join(filters)]
    args += _audio_codec_args(output.suffix, bitrate)
    if output.suffix.lower() in {".mp4", ".m4v", ".mov"}:
        args += ["-movflags", "+faststart"]
    args += [str(output)]
    try:
        run_ffmpeg(args)
    except RuntimeError:
        # Some source/container combinations cannot stream-copy video. Re-encode only then.
        video_index = args.index("-c:v")
        args[video_index:video_index + 2] = ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]
        run_ffmpeg(args)


def process_audio(source: Path, output_dir: Path, start_ms: int = 0, end_ms=None,
                  volume_db: float = 0, fade_in_ms: int = 0, fade_out_ms: int = 0,
                  action: str = "export", output_format: str = "mp3", bitrate: str = "192k") -> Path:
    check_ffmpeg(); source = Path(source); output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    bitrate = _safe_bitrate(bitrate)
    info = probe(source)
    duration = float(info["duration"] or 0)
    start = max(0, int(start_ms)) / 1000
    end = duration if end_ms in (None, "", False) else min(duration, int(end_ms) / 1000)
    if start >= end: raise ValueError("O intervalo selecionado é inválido.")
    filters = ["atrim=0:{:.6f}".format(end - start), "asetpts=PTS-STARTPTS"]
    if volume_db: filters.append(f"volume={float(volume_db):.2f}dB")
    if fade_in_ms: filters.append(f"afade=t=in:st=0:d={min(int(fade_in_ms) / 1000, end-start):.6f}")
    if fade_out_ms:
        fd = min(int(fade_out_ms) / 1000, end-start)
        filters.append(f"afade=t=out:st={max(0, end-start-fd):.6f}:d={fd:.6f}")
    filters.append(f"alimiter=limit={TRUE_PEAK_LIMIT}:level=false")
    if source.suffix.lower() in VIDEO_EXT:
        output = _output_path(source, output_dir, "editado", mode="new", extension="mp4")
        _run_video(source, output, filters, bitrate, start=start, duration=end-start)
    else:
        if output_format not in AUDIO_OUTPUTS: raise ValueError("Formato de saída de áudio não suportado.")
        output = _output_path(source, output_dir, "editado", mode="new", extension=output_format)
        _run_audio(source, output, filters, _audio_codec_args(output_format, bitrate), start=start, duration=end-start)
    return output


def _batch_filters(volume_db, bass_db, mid_db, treble_db, intensity):
    filters = []
    if abs(float(bass_db)) > .001: filters.append(f"bass=g={float(bass_db):.2f}:f=100:w=0.6")
    if abs(float(mid_db)) > .001: filters.append(f"equalizer=f=1000:t=q:w=1.1:g={float(mid_db):.2f}")
    if abs(float(treble_db)) > .001: filters.append(f"treble=g={float(treble_db):.2f}:f=8000:w=0.6")
    intensity = max(0, min(100, float(intensity)))
    if intensity:
        filters.append(f"acompressor=threshold={-18-intensity*.06:.2f}dB:ratio={1+intensity*.04:.2f}:attack=20:release=180:makeup=1")
    if abs(float(volume_db)) > .001: filters.append(f"volume={float(volume_db):.2f}dB")
    return filters + [f"alimiter=limit={TRUE_PEAK_LIMIT}:level=false"]


def _parallel(files, worker, *, progress=None, cancelled=None, workers=None):
    done, failed = [], []
    limit = max(1, min(int(workers or min(4, os.cpu_count() or 1)), len(files)))
    def guarded(path):
        if cancelled and cancelled():
            return None
        return worker(path)
    with ThreadPoolExecutor(max_workers=limit, thread_name_prefix="audio-editor") as executor:
        futures = {executor.submit(guarded, path): path for path in files}
        for future in as_completed(futures):
            source = futures[future]
            try:
                result = future.result()
                if result is not None:
                    done.append(result)
            except Exception as exc: failed.append({"source": str(source), "error": str(exc)})
            if progress: progress(len(done) + len(failed), len(files), str(source))
    return done, failed


def process_batch(folder, output_dir, volume_db=0, bass_db=0, mid_db=0, treble_db=0,
                  intensity=0, output_format="mp3", bitrate="192k", mode="replace", *, progress=None, cancelled=None, workers=None):
    check_ffmpeg(); files = _files(folder)
    if not files: raise ValueError("Nenhum arquivo de áudio ou vídeo foi encontrado na pasta.")
    mode = mode if mode in {"replace", "new"} else "replace"; bitrate = _safe_bitrate(bitrate)
    if mode == "replace" and output_format not in AUDIO_OUTPUTS:
        raise ValueError("Formato de saída inválido.")
    workdir = Path(output_dir) / f"processamento_{uuid.uuid4().hex[:8]}"; workdir.mkdir(parents=True, exist_ok=True)
    filters = _batch_filters(volume_db, bass_db, mid_db, treble_db, intensity)
    def work(source):
        outdir = source.parent if mode == "replace" else workdir
        if source.suffix.lower() in VIDEO_EXT:
            generated = _output_path(source, outdir, "ajustado", mode=mode)
            _run_video(source, generated, filters, bitrate)
        else:
            extension = source.suffix.lstrip(".") if mode == "replace" else output_format
            generated = _output_path(source, outdir, "ajustado", mode=mode, extension=extension)
            _run_audio(source, generated, filters, _audio_codec_args(extension, bitrate))
        final = _finalize(source, generated, mode)
        return {"source": str(source), "output": str(final), "mode": mode}
    done, failed = _parallel(files, work, progress=progress, cancelled=cancelled, workers=workers)
    return {"success": True, "processed": done, "failed": failed, "output_dir": str(folder if mode == "replace" else workdir), "mode": mode}


def _measure_loudnorm(source):
    result = run_ffmpeg(["-i", str(source), "-af", "loudnorm=I=-14:LRA=11:TP=-1.0:print_format=json", "-f", "null", "-"], loglevel="info")
    matches = re.findall(r'\{\s*"input_i".*?\}', result.stderr, re.S)
    if not matches: raise RuntimeError("FFmpeg não retornou a análise de loudness.")
    return json.loads(matches[-1])


def level_folder(folder, output_dir, target_lufs, target_lra, bitrate="192k", mode="replace", *, progress=None, cancelled=None, workers=None):
    check_ffmpeg(); files = _files(folder)
    if not files: raise ValueError("Nenhum arquivo de áudio ou vídeo encontrado.")
    target_lufs, target_lra = float(target_lufs), float(target_lra)
    if not -36 <= target_lufs <= -5 or not 1 <= target_lra <= 30: raise ValueError("Alvos de loudness inválidos.")
    mode = mode if mode in {"replace", "new"} else "replace"; bitrate = _safe_bitrate(bitrate)
    workdir = Path(output_dir) / f"nivelado_{uuid.uuid4().hex[:8]}"; workdir.mkdir(parents=True, exist_ok=True)
    def work(source):
        measured = _measure_loudnorm(source)
        fl = (f"loudnorm=I={target_lufs}:LRA={target_lra}:TP=-1.0:measured_I={measured['input_i']}:"
              f"measured_LRA={measured['input_lra']}:measured_TP={measured['input_tp']}:"
              f"measured_thresh={measured['input_thresh']}:offset={measured['target_offset']}:print_format=summary")
        outdir = source.parent if mode == "replace" else workdir
        if source.suffix.lower() in VIDEO_EXT:
            generated = _output_path(source, outdir, "nivelado", mode=mode)
            _run_video(source, generated, [fl], bitrate)
        else:
            extension = source.suffix.lstrip(".")
            generated = _output_path(source, outdir, "nivelado", mode=mode, extension=extension)
            _run_audio(source, generated, [fl], _audio_codec_args(extension, bitrate))
        final = _finalize(source, generated, mode)
        verified = _measure_loudnorm(final)
        return {"source": str(source), "output": str(final), "mode": mode, "measured_lufs": float(measured['input_i']), "final_lufs": float(verified['input_i']), "final_true_peak": float(verified['input_tp'])}
    done, failed = _parallel(files, work, progress=progress, cancelled=cancelled, workers=workers)
    return {"success": True, "processed": done, "failed": failed, "output_dir": str(folder if mode == "replace" else workdir), "target_lufs": target_lufs, "target_lra": target_lra, "mode": mode}


def pitch_shift_file(source, output_dir, semitones, mode="replace", bitrate="192k"):
    check_ffmpeg(); source = Path(source); output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    semitones, bitrate = float(semitones), _safe_bitrate(bitrate)
    if not -12 <= semitones <= 12: raise ValueError("A transposição deve estar entre -12 e +12 semitons.")
    if abs(semitones) < .001: return {"source": str(source), "output": str(source), "mode": "unchanged"}
    factor = 2 ** (semitones / 12)
    rubberband_available = supports_filter("rubberband")
    if rubberband_available:
        filters = [f"rubberband=pitch={factor:.10f}:tempo=1"]
    else:
        sample_rate = probe(source)["sample_rate"] or 48000
        filters = [f"asetrate={round(sample_rate * factor)}", f"aresample={sample_rate}", f"atempo={1/factor:.8f}"]
    workdir = source.parent if mode == "replace" else output_dir
    generated = _output_path(source, workdir, "karaoke", mode=mode)
    if source.suffix.lower() in VIDEO_EXT: _run_video(source, generated, filters, bitrate)
    else: _run_audio(source, generated, filters, _audio_codec_args(source.suffix, bitrate))
    final = _finalize(source, generated, mode)
    return {"source": str(source), "output": str(final), "mode": mode, "semitones": semitones, "quality_mode": "rubberband" if rubberband_available else "fast"}


def pitch_shift_folder(folder, output_dir, semitones_map, mode="replace", bitrate="192k", *, progress=None, cancelled=None, workers=None):
    files = _files(folder)
    if not files: raise ValueError("Nenhum arquivo de áudio ou vídeo encontrado.")
    workdir = Path(output_dir) / f"karaoke_{uuid.uuid4().hex[:8]}"; workdir.mkdir(parents=True, exist_ok=True)
    def work(source): return pitch_shift_file(source, workdir, float(semitones_map.get(str(source), 0)), mode, bitrate)
    done, failed = _parallel(files, work, progress=progress, cancelled=cancelled, workers=workers)
    return {"success": True, "processed": done, "failed": failed, "output_dir": str(folder if mode == "replace" else workdir), "mode": mode}
