from pathlib import Path
import json,re,subprocess
from .ffmpeg import check_ffmpeg

def analyze_file(path):
    check_ffmpeg()
    cmd=["ffmpeg","-hide_banner","-nostats","-i",str(path),
         "-af","loudnorm=I=-14:LRA=11:TP=-1.0:print_format=json","-f","null","-"]
    r=subprocess.run(cmd,capture_output=True,text=True)
    if r.returncode: raise RuntimeError("FFmpeg falhou ao analisar o arquivo:\n" + r.stderr[-2500:])
    m=re.findall(r'\{\s*"input_i".*?\}',r.stderr,re.S)
    if not m: raise RuntimeError("FFmpeg não retornou os dados de loudness.")
    x=json.loads(m[-1])
    return {"path":str(path),"name":path.name,
            "lufs":float(x["input_i"]),"lra":float(x["input_lra"]),
            "true_peak":float(x["input_tp"])}

def analyze_folder(folder,allowed):
    fs=[p for p in sorted(folder.rglob("*")) if p.is_file() and p.suffix.lower() in allowed]
    if not fs: raise ValueError("Nenhum arquivo de áudio ou vídeo encontrado.")
    ok=[]; errors=[]
    for f in fs:
        try: ok.append(analyze_file(f))
        except Exception as e: errors.append({"path":str(f),"name":f.name,"error":str(e)})
    if not ok: raise RuntimeError("Não foi possível analisar nenhum arquivo.")
    avg={k:round(sum(x[k] for x in ok)/len(ok),2) for k in ("lufs","lra","true_peak")}
    return {"success":True,"count":len(ok),"failed_count":len(errors),
            "files":ok,"errors":errors,"average":avg,
            "recommended":{"lufs":round(avg["lufs"],1),"lra":round(avg["lra"],1)}}
