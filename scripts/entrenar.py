from pathlib import Path
import sys,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pai.config import ROOT,symbols,PaiError
from pai.data import download
from pai.training import require_t4,train_asset,incident
p=argparse.ArgumentParser();p.add_argument('--symbol',choices=symbols());p.add_argument('--all',action='store_true');args=p.parse_args()
tf,gpu=require_t4(ROOT)
for symbol in symbols() if args.all else [args.symbol or 'BTCUSDT']:
    folder=ROOT/'artifacts'/symbol
    if (folder/'evaluacion_TE.lock.json').is_file():
        print(symbol,'tiene una evaluación reservada o concluida. Se conserva; no se reutiliza TE para seleccionar.');continue
    try:
        if not (ROOT/'data/processed'/f'{symbol}.csv').is_file():download(symbol)
        train_asset(symbol,tf,gpu,ROOT);print(symbol,'modelo, evidencia y resultados guardados.')
    except PaiError as exc:
        incident(ROOT,'entrenamiento_'+symbol,exc,'Corregir el incidente antes de reanudar; conservar los registros.')
        raise
