from pathlib import Path
import secrets,os
root=Path(__file__).resolve().parents[1];path=root/'.env'
if path.exists():
    print('La configuración privada ya existe; se conservó sin cambios.')
else:
    values={k:secrets.token_urlsafe(36) for k in ['PAI_API_KEY','PAI_GATEWAY_KEY','PAI_SESSION_KEY']}
    values.update(OLLAMA_URL='http://127.0.0.1:11434',OLLAMA_MODEL='qwen3:1.7b')
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:f.write('\n'.join(k+'='+v for k,v in values.items())+'\n')
    print('Configuración privada creada en .env. Abre ese archivo local y copia PAI_API_KEY para entrar a la interfaz. No lo compartas.')
