from pathlib import Path

AUDIO_EXT = {".mp3",".wav",".flac",".ogg",".m4a",".aac",".wma"}
VIDEO_EXT = {".mp4",".mkv",".avi",".mov",".webm",".mpeg",".mpg",".m4v"}

import re
import json
import subprocess
import uuid

from pydub import AudioSegment
from .ffmpeg import check_ffmpeg, probe

AUDIO_OUTPUTS = {"mp3", "wav", "flac", "ogg"}
VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".webm",
    ".mpeg", ".mpg", ".m4v"
}


def process_audio(
    source: Path, output_dir: Path, start_ms: int = 0,
    end_ms=None, volume_db: float = 0, fade_in_ms: int = 0,
    fade_out_ms: int = 0, action: str = "export",
    output_format: str = "mp3", bitrate: str = "192k"
):
    check_ffmpeg()
    if source.suffix.lower() in VIDEO_EXTENSIONS:
        return process_video(
            source, output_dir, start_ms, end_ms,
            volume_db, fade_in_ms, fade_out_ms, bitrate
        )
    return process_audio_file(
        source, output_dir, start_ms, end_ms,
        volume_db, fade_in_ms, fade_out_ms,
        output_format, bitrate
    )


def process_audio_file(
    source, output_dir, start_ms, end_ms,
    volume_db, fade_in_ms, fade_out_ms, output_format, bitrate
):
    if output_format not in AUDIO_OUTPUTS:
        raise ValueError("Formato de saída de áudio não suportado.")

    audio = AudioSegment.from_file(source)
    start_ms = max(0, int(start_ms))
    end_ms = len(audio) if end_ms in (None, "", False) else int(end_ms)
    end_ms = min(len(audio), end_ms)

    if start_ms >= end_ms:
        raise ValueError("O intervalo selecionado é inválido.")

    audio = audio[start_ms:end_ms]
    if volume_db:
        audio = audio + float(volume_db)
    if fade_in_ms:
        audio = audio.fade_in(min(int(fade_in_ms), len(audio)))
    if fade_out_ms:
        audio = audio.fade_out(min(int(fade_out_ms), len(audio)))

    output_name = f"{source.stem}_editado_{uuid.uuid4().hex[:8]}.{output_format}"
    output_path = output_dir / output_name

    export_kwargs = {}
    if output_format == "mp3":
        export_kwargs["bitrate"] = bitrate

    audio.export(output_path, format=output_format, **export_kwargs)
    return output_path


def process_video(
    source, output_dir, start_ms, end_ms,
    volume_db, fade_in_ms, fade_out_ms, bitrate
):
    info = probe(source)
    if not info["has_audio"]:
        raise ValueError("O arquivo de vídeo não possui uma faixa de áudio.")

    duration_ms = int(float(info["duration"] or 0) * 1000)
    start_ms = max(0, int(start_ms))
    end_ms = duration_ms if end_ms in (None, "", False) else int(end_ms)
    end_ms = min(duration_ms, end_ms)

    if start_ms >= end_ms:
        raise ValueError("O intervalo selecionado é inválido.")

    start = start_ms / 1000
    duration = (end_ms - start_ms) / 1000

    filters = [f"volume={float(volume_db):.2f}dB"]

    if fade_in_ms > 0:
        fade_duration = min(fade_in_ms / 1000, duration)
        filters.append(f"afade=t=in:st=0:d={fade_duration:.3f}")

    if fade_out_ms > 0:
        fade_duration = min(fade_out_ms / 1000, duration)
        fade_start = max(0, duration - fade_duration)
        filters.append(
            f"afade=t=out:st={fade_start:.3f}:d={fade_duration:.3f}"
        )

    output_name = f"{source.stem}_editado_{uuid.uuid4().hex[:8]}.mp4"
    output_path = output_dir / output_name

    command = [
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}", "-i", str(source),
        "-t", f"{duration:.3f}",
        "-map", "0:v:0?", "-map", "0:a:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", bitrate,
        "-af", ",".join(filters),
        "-movflags", "+faststart",
        str(output_path)
    ]

    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg não conseguiu processar o vídeo:\n" +
            result.stderr[-3000:]
        )

    return output_path


def _replace_original_safely(source, generated):
    """
    Safely replaces the original.

    Important: the generated file must be on the same filesystem as the
    source for Path.replace() to work reliably. The leveling/batch functions
    therefore create temporary output next to the source when mode=replace.
    """
    source = Path(source)
    generated = Path(generated)

    if not generated.exists() or generated.stat().st_size == 0:
        raise RuntimeError("O arquivo processado não foi gerado corretamente.")

    backup = source.with_name(
        f".{source.name}.audio_editor_backup"
    )

    try:
        if backup.exists():
            backup.unlink()

        source.replace(backup)
        generated.replace(source)

        if backup.exists():
            backup.unlink()

    except Exception:
        # Restore the original whenever possible.
        try:
            if not source.exists() and backup.exists():
                backup.replace(source)
        finally:
            if backup.exists() and source.exists():
                backup.unlink()

        raise



def _finalize_output(source, generated, mode):
    if mode == "replace":
        _replace_original_safely(source, generated)
        return source
    return generated


def _batch_filters(volume_db, bass_db, mid_db, treble_db, intensity):
    filters = []
    if abs(volume_db) > 0.001:
        filters.append(f"volume={volume_db:.2f}dB")
    if abs(bass_db) > 0.001:
        filters.append(f"equalizer=f=100:t=q:w=1:g={bass_db:.2f}")
    if abs(mid_db) > 0.001:
        filters.append(f"equalizer=f=1000:t=q:w=1:g={mid_db:.2f}")
    if abs(treble_db) > 0.001:
        filters.append(f"equalizer=f=8000:t=q:w=1:g={treble_db:.2f}")
    intensity = max(0, min(100, intensity))
    if intensity > 0:
        threshold = -18 - intensity * 0.10
        ratio = 1 + intensity * 0.04
        makeup = intensity * 0.04
        filters.append(
            f"acompressor=threshold={threshold:.2f}dB:ratio={ratio:.2f}:"
            f"attack=20:release=180:makeup={makeup:.2f}"
        )
    return filters


def process_batch(folder, output_dir, volume_db=0, bass_db=0, mid_db=0,
                  treble_db=0, intensity=0, output_format="mp3",
                  bitrate="192k", mode="replace"):
    check_ffmpeg()
    audio={".mp3",".wav",".flac",".ogg",".m4a",".aac",".wma"}
    video={".mp4",".mkv",".avi",".mov",".webm",".mpeg",".mpg",".m4v"}
    files=[p for p in sorted(folder.rglob("*"))
           if p.is_file() and p.suffix.lower() in audio|video]
    if not files:
        raise ValueError("Nenhum arquivo de áudio ou vídeo foi encontrado na pasta.")

    mode=mode if mode in {"replace","new"} else "replace"
    workdir=output_dir/f"processamento_{uuid.uuid4().hex[:8]}"
    workdir.mkdir(parents=True,exist_ok=True)
    filters=_batch_filters(volume_db,bass_db,mid_db,treble_db,intensity)
    processed,failed=[],[]

    for source in files:
        try:
            processing_dir = (
                source.parent if mode == "replace" else workdir
            )
            generated=(_batch_video(source,processing_dir,filters,bitrate)
                       if source.suffix.lower() in video
                       else _batch_audio(source,processing_dir,filters,output_format,bitrate))
            final=_finalize_output(source,generated,mode)
            processed.append({"source":str(source),"output":str(final),"mode":mode})
        except Exception as exc:
            failed.append({"source":str(source),"error":str(exc)})

    return {"success":True,"processed":processed,"failed":failed,
            "output_dir":str(folder if mode=="replace" else workdir),"mode":mode}


def _batch_audio(source, outdir, filters, fmt, bitrate):
    if fmt not in AUDIO_OUTPUTS:
        raise ValueError("Formato de saída inválido.")
    out = outdir / f"{source.stem}_ajustado_{uuid.uuid4().hex[:8]}.{fmt}"
    cmd = ["ffmpeg","-y","-i",str(source),"-af",",".join(filters) if filters else "anull","-vn"]
    if fmt == "mp3":
        cmd += ["-c:a","libmp3lame","-b:a",bitrate]
    elif fmt == "wav":
        cmd += ["-c:a","pcm_s16le"]
    elif fmt == "flac":
        cmd += ["-c:a","flac"]
    else:
        cmd += ["-c:a","libvorbis","-q:a","5"]
    cmd += [str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-2500:])
    return out


def _batch_video(source, outdir, filters, bitrate):
    out = outdir / f"{source.stem}_ajustado_{uuid.uuid4().hex[:8]}.mp4"
    cmd = ["ffmpeg","-y","-i",str(source),"-map","0:v:0?","-map","0:a:0",
           "-c:v","copy","-af",",".join(filters) if filters else "anull",
           "-c:a","aac","-b:a",bitrate,"-movflags","+faststart",str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        cmd = ["ffmpeg","-y","-i",str(source),"-map","0:v:0?","-map","0:a:0",
               "-c:v","libx264","-preset","medium","-crf","18",
               "-af",",".join(filters) if filters else "anull",
               "-c:a","aac","-b:a",bitrate,"-movflags","+faststart",str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-2500:])
    return out


def _measure_loudnorm(source):
    check_ffmpeg()
    cmd=["ffmpeg","-hide_banner","-nostats","-i",str(source),
         "-af","loudnorm=I=-14:LRA=11:TP=-1.0:print_format=json","-f","null","-"]
    r=subprocess.run(cmd,capture_output=True,text=True)
    if r.returncode: raise RuntimeError(r.stderr[-2500:])
    m=re.findall(r'\{\s*"input_i".*?\}',r.stderr,re.S)
    if not m: raise RuntimeError("FFmpeg não retornou a análise.")
    return json.loads(m[-1])

def level_folder(folder, output_dir, target_lufs, target_lra,
                bitrate="192k", mode="replace"):
    check_ffmpeg()
    audio={".mp3",".wav",".flac",".ogg",".m4a",".aac",".wma"}
    video={".mp4",".mkv",".avi",".mov",".webm",".mpeg",".mpg",".m4v"}
    files=[p for p in sorted(folder.rglob("*"))
           if p.is_file() and p.suffix.lower() in audio|video]
    if not files:
        raise ValueError("Nenhum arquivo de áudio ou vídeo encontrado.")

    mode=mode if mode in {"replace","new"} else "replace"
    workdir=output_dir/f"nivelado_{uuid.uuid4().hex[:8]}"
    workdir.mkdir(parents=True,exist_ok=True)
    done,failed=[],[]

    for source in files:
        try:
            measured=_measure_loudnorm(source)
            fl=(f"loudnorm=I={target_lufs}:LRA={target_lra}:TP=-1.0:"
                f"measured_I={measured['input_i']}:measured_LRA={measured['input_lra']}:"
                f"measured_TP={measured['input_tp']}:measured_thresh={measured['input_thresh']}:"
                f"offset={measured['target_offset']}:linear=true:print_format=summary")

            processing_dir = (
                source.parent if mode == "replace" else workdir
            )

            if source.suffix.lower() in video:
                generated=processing_dir/f".{source.stem}_nivelado_{uuid.uuid4().hex[:8]}.mp4"
                cmd=["ffmpeg","-y","-i",str(source),"-map","0:v:0?","-map","0:a:0",
                     "-c:v","copy","-af",fl,"-c:a","aac","-b:a",bitrate,
                     "-movflags","+faststart",str(generated)]
            else:
                generated=processing_dir/f".{source.stem}_nivelado_{uuid.uuid4().hex[:8]}.mp3"
                cmd=["ffmpeg","-y","-i",str(source),"-af",fl,"-vn",
                     "-c:a","libmp3lame","-b:a",bitrate,str(generated)]

            r=subprocess.run(cmd,capture_output=True,text=True)
            if r.returncode:
                raise RuntimeError(r.stderr[-3000:])

            final=_finalize_output(source,generated,mode)
            done.append({"source":str(source),"output":str(final),"mode":mode,
                         "measured_lufs":float(measured["input_i"]),
                         "measured_lra":float(measured["input_lra"])})
        except Exception as exc:
            failed.append({"source":str(source),"error":str(exc)})

    return {"success":True,"processed":done,"failed":failed,
            "output_dir":str(folder if mode=="replace" else workdir),
            "target_lufs":float(target_lufs),"target_lra":float(target_lra),
            "mode":mode}


def pitch_shift_file(source, output_dir, semitones, mode="replace", bitrate="192k"):
    """
    Changes pitch while preserving duration. Uses FFmpeg's sample-rate trick:
    asetrate changes pitch, aresample restores the original rate, and atempo
    compensates the speed change.
    """
    check_ffmpeg()

    source=Path(source)
    output_dir=Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    semitones=float(semitones)
    if semitones < -12 or semitones > 12:
        raise ValueError("A transposição deve estar entre -12 e +12 semitons.")

    if abs(semitones) < 0.001:
        return {"source":str(source),"output":str(source),"mode":"unchanged"}

    factor=2 ** (semitones/12.0)
    sample_rate=48000
    shifted_rate=max(8000,int(round(sample_rate*factor)))

    # Process next to the original in replacement mode, avoiding cross-filesystem
    # rename failures.
    workdir=source.parent if mode=="replace" else output_dir

    ext=source.suffix.lower()
    if ext in VIDEO_EXT:
        generated=workdir/f".{source.stem}_karaoke_{uuid.uuid4().hex[:8]}{ext}"
        cmd=[
            "ffmpeg","-y","-i",str(source),
            "-map","0:v:0?","-map","0:a:0",
            "-c:v","copy",
            "-af",f"asetrate={shifted_rate},aresample={sample_rate},atempo={1/factor:.8f}",
            "-c:a","aac","-b:a",bitrate,
            "-movflags","+faststart",str(generated)
        ]
    else:
        generated=workdir/f".{source.stem}_karaoke_{uuid.uuid4().hex[:8]}{ext}"

        if ext==".mp3":
            codec=["-c:a","libmp3lame","-b:a",bitrate]
        elif ext==".wav":
            codec=["-c:a","pcm_s16le"]
        elif ext==".flac":
            codec=["-c:a","flac"]
        elif ext==".ogg":
            codec=["-c:a","libvorbis","-q:a","5"]
        elif ext in {".m4a",".aac"}:
            codec=["-c:a","aac","-b:a",bitrate]
        else:
            codec=["-c:a","libmp3lame","-b:a",bitrate]

        cmd=[
            "ffmpeg","-y","-i",str(source),
            "-af",f"asetrate={shifted_rate},aresample={sample_rate},atempo={1/factor:.8f}",
            "-vn",*codec,str(generated)
        ]

    r=subprocess.run(cmd,capture_output=True,text=True)
    if r.returncode or not generated.exists() or generated.stat().st_size==0:
        raise RuntimeError(r.stderr[-3000:] or "FFmpeg não gerou o arquivo.")

    final=_finalize_output(source,generated,mode)

    return {"source":str(source),"output":str(final),"mode":mode,"semitones":semitones}


def pitch_shift_folder(folder, output_dir, semitones_map,
                       mode="replace", bitrate="192k"):
    folder=Path(folder)
    files=[p for p in sorted(folder.rglob("*"))
           if p.is_file() and p.suffix.lower() in AUDIO_EXT|VIDEO_EXT]

    if not files:
        raise ValueError("Nenhum arquivo de áudio ou vídeo encontrado.")

    workdir=output_dir/f"karaoke_{uuid.uuid4().hex[:8]}"
    workdir.mkdir(parents=True,exist_ok=True)

    processed=[]; failed=[]
    for source in files:
        try:
            shift=float(semitones_map.get(str(source),0))
            result=pitch_shift_file(
                source,workdir,shift,mode=mode,bitrate=bitrate
            )
            processed.append(result)
        except Exception as exc:
            failed.append({"source":str(source),"error":str(exc)})

    return {
        "success":True,
        "processed":processed,
        "failed":failed,
        "output_dir":str(folder if mode=="replace" else workdir),
        "mode":mode
    }
