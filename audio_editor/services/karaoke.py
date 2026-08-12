from pathlib import Path
import math
import subprocess
import tempfile
import uuid
import numpy as np

from .ffmpeg import check_ffmpeg

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F",
              "F#", "G", "G#", "A", "A#", "B"]

VOCAL_PROFILES = {
    "soprano": {"label": "Soprano", "low": 261.63, "high": 880.00},
    "mezzo": {"label": "Mezzo-soprano", "low": 220.00, "high": 698.46},
    "contralto": {"label": "Contralto", "low": 174.61, "high": 587.33},
    "tenor": {"label": "Tenor", "low": 130.81, "high": 440.00},
    "baritone": {"label": "Barítono", "low": 110.00, "high": 349.23},
    "bass": {"label": "Baixo", "low": 82.41, "high": 329.63},
}

AUDIO_EXT = {".mp3",".wav",".flac",".ogg",".m4a",".aac",".wma"}
VIDEO_EXT = {".mp4",".mkv",".avi",".mov",".webm",".mpeg",".mpg",".m4v"}


def _decode_audio(path, seconds=120):
    check_ffmpeg()
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-i", str(path),
        "-t", str(seconds),
        "-vn", "-ac", "1", "-ar", "22050",
        "-f", "f32le", "-"
    ]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode:
        raise RuntimeError(r.stderr.decode(errors="replace")[-3000:])
    return np.frombuffer(r.stdout, dtype=np.float32), 22050


def _estimate_f0(samples, sr):
    # Autocorrelation pitch estimator. It is intentionally conservative:
    # only reasonably periodic frames are considered voiced.
    frame_size = 4096
    hop = 2048
    min_f = 70.0
    max_f = 1000.0
    min_lag = int(sr / max_f)
    max_lag = int(sr / min_f)

    pitches = []
    energies = []

    if len(samples) < frame_size:
        return pitches

    for start in range(0, len(samples) - frame_size, hop):
        frame = samples[start:start + frame_size]
        frame = frame - np.mean(frame)
        rms = float(np.sqrt(np.mean(frame * frame)))
        if rms < 0.008:
            continue

        frame *= np.hanning(frame_size)
        corr = np.correlate(frame, frame, mode="full")[frame_size-1:]
        corr[:min_lag] = 0

        region = corr[min_lag:max_lag + 1]
        if len(region) == 0:
            continue

        idx = int(np.argmax(region)) + min_lag
        peak = corr[idx] / max(corr[0], 1e-9)

        # Reject noisy/unvoiced frames.
        if peak < 0.30:
            continue

        if 1 < idx < len(corr) - 1:
            a, b, c = corr[idx-1], corr[idx], corr[idx+1]
            denom = a - 2*b + c
            if abs(denom) > 1e-12:
                idx = idx + 0.5 * (a-c) / denom

        f0 = sr / idx
        if min_f <= f0 <= max_f:
            pitches.append(float(f0))
            energies.append(rms)

    return pitches


def _median_filter(values, width=5):
    if len(values) < width:
        return values
    arr=np.asarray(values)
    result=[]
    half=width//2
    for i in range(len(arr)):
        result.append(float(np.median(arr[max(0,i-half):min(len(arr),i+half+1)])))
    return result


def _frequency_to_note(f):
    midi=69 + 12*math.log2(f/440.0)
    midi_round=int(round(midi))
    octave=(midi_round//12)-1
    name=NOTE_NAMES[midi_round%12]
    cents=(midi-midi_round)*100
    return {
        "name": f"{name}{octave}",
        "note": name,
        "octave": octave,
        "midi": midi_round,
        "cents": round(cents,1),
        "frequency": round(f,2)
    }


def _detect_key(pitches):
    if not pitches:
        return {"name":"Desconhecida","root":None,"major_minor":"?"}

    hist=np.zeros(12,dtype=float)
    for f in pitches:
        midi=69+12*math.log2(f/440.0)
        pc=int(round(midi))%12
        hist[pc]+=1

    root=int(np.argmax(hist))
    # Without harmonic analysis we don't claim major/minor certainty.
    return {
        "name": NOTE_NAMES[root],
        "root": root,
        "major_minor": "estimada",
        "confidence": round(float(hist[root]/max(hist.sum(),1))*100,1)
    }


def analyze_file(path):
    samples,sr=_decode_audio(path)
    pitches=_median_filter(_estimate_f0(samples,sr))
    if not pitches:
        raise RuntimeError(
            "Não foi possível detectar uma linha melódica suficientemente clara."
        )

    low=min(pitches)
    high=max(pitches)
    median=float(np.median(pitches))

    return {
        "path":str(path),
        "name":path.name,
        "key":_detect_key(pitches),
        "range":{
            "low":_frequency_to_note(low),
            "high":_frequency_to_note(high),
            "median":_frequency_to_note(median)
        },
        "sampled_seconds":round(min(len(samples)/sr,120),1),
        "confidence":round(min(100,30+len(pitches)*0.15),1)
    }


def _profile_score(low, high, profile_low, profile_high, shift):
    factor=2**(shift/12)
    a=low*factor
    b=high*factor

    span=max(high-low,1)
    below=max(0, profile_low-a)
    above=max(0, b-profile_high)

    # Prefer solutions with maximum overlap and minimum excursion outside range.
    penalty=(below+above)/span
    inside=max(0, min(b,profile_high)-max(a,profile_low))
    overlap=inside/span

    center=((a+b)/2)
    pcenter=(profile_low+profile_high)/2
    center_penalty=abs(center-pcenter)/pcenter

    return overlap*100 - penalty*120 - center_penalty*20


def recommend_shift(analysis, profile_name):
    profile=VOCAL_PROFILES[profile_name]
    low=analysis["range"]["low"]["frequency"]
    high=analysis["range"]["high"]["frequency"]

    candidates=[]
    for shift in range(-6,7):
        score=_profile_score(low,high,profile["low"],profile["high"],shift)
        candidates.append({"semitones":shift,"score":round(score,1)})

    best=max(candidates,key=lambda x:x["score"])
    return {
        "profile":profile_name,
        "profile_label":profile["label"],
        "recommended_semitones":best["semitones"],
        "score":max(0,min(100,round(best["score"],1))),
        "candidates":candidates
    }


def analyze_path(path, profile_name="baritone"):
    path=Path(path)
    result=analyze_file(path)
    result["recommendation"]=recommend_shift(result,profile_name)
    return result


def analyze_folder(folder, profile_name="baritone"):
    folder=Path(folder)
    files=[p for p in sorted(folder.rglob("*"))
           if p.is_file() and p.suffix.lower() in AUDIO_EXT|VIDEO_EXT]
    if not files:
        raise ValueError("Nenhum arquivo de áudio ou vídeo encontrado.")

    results=[]; errors=[]
    for path in files:
        try:
            results.append(analyze_path(path,profile_name))
        except Exception as exc:
            errors.append({"path":str(path),"name":path.name,"error":str(exc)})

    return {
        "success":True,
        "profile":VOCAL_PROFILES[profile_name],
        "count":len(results),
        "failed_count":len(errors),
        "files":results,
        "errors":errors
    }
