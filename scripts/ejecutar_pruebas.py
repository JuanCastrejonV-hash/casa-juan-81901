from pathlib import Path
from datetime import datetime,timezone
import subprocess,sys,json,xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1];out=root/'evidencia';out.mkdir(exist_ok=True)
run=subprocess.run([sys.executable,'-m','pytest','-q','--junitxml='+str(out/'pruebas_junit.xml')],
                   cwd=root,capture_output=True,text=True)
(out/'pruebas_salida.txt').write_text(run.stdout+run.stderr)
if not (out/'pruebas_junit.xml').is_file():raise SystemExit('No se generó el reporte de pruebas. Revisa evidencia/pruebas_salida.txt.')
suite=ET.parse(out/'pruebas_junit.xml').getroot().find('testsuite')
report={'fecha':datetime.now(timezone.utc).isoformat(),'testing_only':True,
 'tests':int(suite.attrib['tests']),'failures':int(suite.attrib['failures']),'errors':int(suite.attrib['errors']),
 'skipped':int(suite.attrib['skipped']),'seconds':float(suite.attrib['time']),
 'scope':'Pruebas controladas; incluyen replay sintético. No acreditan mercado actual, T4 ni ciclos reales del agente.',
 'cases':[x.attrib['name'] for x in suite.findall('testcase')]}
(out/'pruebas.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(run.stdout);raise SystemExit(run.returncode)
