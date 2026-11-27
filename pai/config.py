from pathlib import Path
import json, hashlib, os, math

ROOT = Path(__file__).resolve().parents[1]

def project():
    return json.loads((ROOT/'config/project.json').read_text(encoding='utf-8'))

def symbols():
    return [x['symbol'] for x in project()['assets']]

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save_json(path, obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False,default=str),encoding='utf-8')

class PaiError(ValueError):
    """Fallo identificado que obliga a detener o pausar el paso afectado."""

def finite(value, name):
    x=float(value)
    if not math.isfinite(x):raise PaiError(f'{name}: valor no finito.')
    return x
