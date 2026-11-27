"""Señal del cierre t; ejecución en apertura t+1; valoración en cierre t+1."""
import numpy as np
import pandas as pd
from .config import PaiError

def simulate(meta,pred,threshold=0.001,technical_filter=False,initial=100000,fee=.001,
             passive=False,cash_only=False,slippage_bps=0):
    if not len(meta) or len(meta)!=len(pred):raise PaiError('Simulación: predicciones y fechas desalineadas.')
    cash=float(initial);qty=0.;entry_cost=None;trades=[];records=[];total_cost=0.;slip=slippage_bps/10000
    for k,(_,r) in enumerate(meta.iterrows()):
        desired=(True if passive else float(pred[k])>threshold and (not technical_filter or r.close_t>r.sma20)) and not cash_only
        price=float(r.open_next);cost=0.;action='MANTENER' if qty else 'EFECTIVO'
        if desired and qty==0:
            fill=price*(1+slip);new_qty=cash/(fill*(1+fee));notional=new_qty*fill;cost=notional*fee
            entry_cost=notional+cost;cash-=entry_cost;qty=new_qty;action='COMPRAR'
        elif not desired and qty>0:
            fill=price*(1-slip);gross=qty*fill;cost=gross*fee;proceeds=gross-cost
            cash+=proceeds;trades.append(proceeds-entry_cost);qty=0.;entry_cost=None;action='VENDER'
        total_cost+=cost
        equity=cash+qty*float(r.close_next)
        records.append({'fecha':r.target_date,'emision':r.issue_date,'precio_ejecucion':price,
                        'fecha_ejecucion':r.get('execution_date',r.target_date) if action in ('COMPRAR','VENDER') else None,
                        'senal':bool(desired),'accion':action,'posicion':qty,'efectivo':cash,
                        'costos':cost,'patrimonio':equity,'liquidacion_final':False})
    if qty>0:
        fill=float(meta.iloc[-1].close_next)*(1-slip);gross=qty*fill;cost=gross*fee
        proceeds=gross-cost;cash+=proceeds;trades.append(proceeds-entry_cost);qty=0.;total_cost+=cost
        records[-1].update(posicion=0.,efectivo=cash,patrimonio=cash,
                           fecha_liquidacion=meta.iloc[-1].target_date,
                           costos=records[-1]['costos']+cost,liquidacion_final=True)
    curve=pd.DataFrame(records)
    path=np.r_[initial,curve.patrimonio.to_numpy()];peaks=np.maximum.accumulate(path)
    dd=float(np.max(1-path/peaks))
    summary={'rendimiento_neto':float(cash/initial-1),'max_drawdown':dd,
             'operaciones_cerradas':len(trades),'win_rate':float(np.mean(np.asarray(trades)>0)) if trades else None,
             'costos_totales':float(total_cost),'patrimonio_final':float(cash)}
    return curve,summary

def choose_rule(meta,pred,thresholds):
    rows=[]
    for d in thresholds:
        if not d>0:raise PaiError('Los umbrales deben ser positivos y fijados antes de TE.')
        for filt in [False,True]:
            _,result=simulate(meta,pred,d,filt)
            rows.append({'delta':d,'filtro_sma20':filt,**result})
    table=pd.DataFrame(rows).sort_values(['rendimiento_neto','max_drawdown','delta','filtro_sma20'],
                                        ascending=[False,True,True,True],kind='stable')
    best=table.iloc[0]
    return {'threshold':float(best.delta),'technical_filter':bool(best.filtro_sma20)},table
