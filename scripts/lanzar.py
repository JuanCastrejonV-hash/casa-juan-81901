from pathlib import Path
import sys,subprocess,os,time,webbrowser,urllib.request,urllib.error,shutil
root=Path(__file__).resolve().parents[1];os.chdir(root)
if sys.version_info<(3,11):raise SystemExit('Instala Python 3.11 o 3.12 para ejecutar el proyecto.')
venv=root/'.venv';python=venv/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
if not python.is_file():
    subprocess.run([sys.executable,'-m','venv',str(venv)],check=True)
    subprocess.run([str(python),'-m','pip','install','-r','requirements.txt'],check=True)
subprocess.run([str(python),'scripts/configurar.py'],check=True)
if not (root/'frontend/dist/index.html').is_file():raise SystemExit('Falta la interfaz compilada. Ejecuta npm install y npm run build dentro de frontend.')
print('Abriendo el laboratorio local. Para cerrar, presiona Ctrl+C. Ollama se configura por separado, como indica README.md.')
process=subprocess.Popen([str(python),'-m','uvicorn','backend.app:create_app','--factory','--host','127.0.0.1','--port','8000'])
try:
    for _ in range(40):
        if process.poll() is not None:raise SystemExit('El servidor no pudo iniciar; revisa el mensaje anterior.')
        try:
            with urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=.5) as r:
                if r.status==200:webbrowser.open('http://127.0.0.1:8000');break
        except (urllib.error.URLError,TimeoutError):time.sleep(.25)
    process.wait()
except KeyboardInterrupt:
    process.terminate();process.wait(timeout=10)
