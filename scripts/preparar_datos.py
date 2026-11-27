from pathlib import Path
import sys,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pai.config import ROOT,symbols,PaiError
from pai.data import download
from pai.training import classical,incident
p=argparse.ArgumentParser();p.add_argument('--symbol',choices=symbols());p.add_argument('--all',action='store_true');args=p.parse_args()
for symbol in symbols() if args.all else [args.symbol or 'BTCUSDT']:
    try:
        if not (ROOT/'data/processed'/f'{symbol}.csv').is_file():download(symbol)
        b,_,metrics=classical(symbol)
        print(symbol,'datos auditados y referencias TR/VA listas. TE reservado.');print(metrics.to_string(index=False))
    except PaiError as exc:
        incident(ROOT,'datos_'+symbol,exc,'Revisar conexión, disponibilidad del par e historia mínima; no rellenar datos.')
        print(symbol,str(exc));raise SystemExit(1)
