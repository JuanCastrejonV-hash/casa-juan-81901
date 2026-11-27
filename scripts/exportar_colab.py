from pathlib import Path
import json,hashlib,zipfile,sys
root=Path(__file__).resolve().parents[1];dest=root/'resultados_colab_81901.zip'
files=[]
for folder in ['artifacts','data','evidencia']:
    files.extend(p for p in (root/folder).rglob('*') if p.is_file() and p.suffix not in ('.pyc',) and '__pycache__' not in p.parts)
manifest=[{'path':str(p.relative_to(root)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in files]
with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
    for p in files:z.write(p,p.relative_to(root))
    z.writestr('manifest_exportacion.json',json.dumps(manifest,indent=2))
print(dest)
