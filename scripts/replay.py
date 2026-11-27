from pathlib import Path
import sys,argparse,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pai.config import ROOT,symbols
from backend.models import Registry
from backend.llm import OllamaLocal
from backend.app import settings_from_env
from backend.replay import run_replay
p=argparse.ArgumentParser();p.add_argument('--symbol',choices=symbols(),default='BTCUSDT');p.add_argument('--cycles',type=int,default=30);args=p.parse_args()
if args.cycles<20:raise SystemExit('Se requieren al menos 20 ciclos para la demostración.')
s=settings_from_env();result=run_replay(ROOT,args.symbol,args.cycles,Registry(ROOT),OllamaLocal(s.ollama_url,s.ollama_model))
print(json.dumps(result,ensure_ascii=False,indent=2))
