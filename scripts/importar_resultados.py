from pathlib import Path,PurePosixPath
import sys,json,hashlib,zipfile,shutil,tempfile
root=Path(__file__).resolve().parents[1]
if len(sys.argv)!=2:raise SystemExit('Uso: python scripts/importar_resultados.py /ruta/resultados_colab_81901.zip')
with zipfile.ZipFile(sys.argv[1]) as z:
    manifest=json.loads(z.read('manifest_exportacion.json'))
    if sum(item['bytes'] for item in manifest)>1024**3:raise SystemExit('Paquete mayor a 1 GiB; revisar antes de importar.')
    with tempfile.TemporaryDirectory(prefix='pai_import_') as temp:
        for item in manifest:
            rel=PurePosixPath(item['path'])
            if rel.is_absolute() or '..' in rel.parts or rel.parts[0] not in ('artifacts','data','evidencia'):
                raise SystemExit('Ruta de importación no permitida.')
            content=z.read(item['path'])
            if len(content)!=item['bytes'] or hashlib.sha256(content).hexdigest()!=item['sha256']:
                raise SystemExit('Integridad incorrecta: '+item['path'])
            target=root.joinpath(*rel.parts)
            if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()!=item['sha256']:
                raise SystemExit('Ya existe otra versión: '+str(target)+'. Importar en una copia nueva para conservar la evidencia.')
            staged=Path(temp).joinpath(*rel.parts);staged.parent.mkdir(parents=True,exist_ok=True);staged.write_bytes(content)
        for item in manifest:
            rel=PurePosixPath(item['path']);target=root.joinpath(*rel.parts);target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(Path(temp).joinpath(*rel.parts),target)
print('Resultados importados y hashes comprobados. Reinicia la aplicación para cargar los modelos.')
