"""Read models, market observations and Paper records for the local dashboard."""

import json
import time
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from pai.config import PaiError, digest, project, symbols
from pai.data import audit, rows_frame
from pai.features import indicators


Source = Literal["historical", "live"]
STRATEGIES = ("modelo_sin_llm", "agente_con_llm", "comprar_y_mantener")
TABLES = ("decisions", "orders", "equity", "events")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def records(path):
    if not path.is_file():
        return []
    try:
        frame = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return []
    return frame.astype(object).where(pd.notna(frame), None).to_dict("records")


def live_candles(market, symbol, now_ms, length):
    frame, _ = audit(rows_frame(market.candles(symbol, length)), now_ms, min_rows=60)
    age_limit = project()["paper"]["max_data_age_hours"] * 3600000
    if now_ms - int(frame.close_time.iloc[-1]) > age_limit:
        raise PaiError("Dato atrasado: no se presenta como mercado actual.")
    return frame


def market_view(symbol, frame, source, forecast, observed_ms=None, *, chart_size=180):
    enriched = indicators(frame)
    last = enriched.iloc[-1]
    chart = enriched.tail(chart_size)
    series = [
        {"time": int(row.close_time), "open_time": int(row.open_time),
         "open": float(row.open), "high": float(row.high), "low": float(row.low),
         "close": float(row.close), "sma20": float(row.sma20) if pd.notna(row.sma20) else None}
        for row in chart.itertuples()
    ]
    return {
        "symbol": symbol, "source": source, "close": float(last.close),
        "close_ms": int(last.close_time), "change": float(last["return"]),
        "sma20": float(last.sma20), "dist_sma20": float(last.dist_sma20),
        "vol20": float(last.vol20), "count": len(frame), "observed_ms": observed_ms,
        "forecast": forecast, "chart": series,
    }


def historical_frame(root, symbol, contract):
    path = root / "data" / "processed" / f"{symbol}.csv"
    if not path.is_file() or digest(path) != contract.get("data_sha256"):
        raise PaiError("Falta la muestra histórica verificada del activo.")
    frame = pd.read_csv(path)
    frame, _ = audit(frame, int(frame.close_time.max()), project()["minimum_observations"])
    return frame


def historical_forecast(folder, contract):
    rows = records(folder / "prediccion_futura.csv")
    if not rows:
        return None
    prediction = rows[0]
    if prediction["symbol"] != contract["symbol"]:
        raise PaiError("El pronóstico archivado corresponde a otro activo.")
    return {
        "value": float(prediction["estimado"]), "threshold": float(contract["threshold"]),
        "technical_filter": bool(contract["technical_filter"]),
        "signal": str(prediction["senal"]).lower() == "true",
        "issue_ms": int(pd.Timestamp(prediction["fecha_corte"]).value // 1_000_000),
        "target_ms": int(pd.Timestamp(prediction["proximo_periodo"]).value // 1_000_000),
    }


def replay_directory(root, symbol):
    return root / "evidencia" / f"replay_{symbol}"


def archived_replay(root, symbol):
    folder = replay_directory(root, symbol)
    summary = read_json(folder / "resumen.json")
    if not summary:
        return None
    if summary.get("mode") != "replay" or summary.get("symbol") != symbol:
        raise PaiError("El resumen archivado no coincide con el activo.")
    return summary


def catalog_entry(root, registry, asset, verification):
    symbol = asset["symbol"]
    folder = root / "artifacts" / symbol
    entry = {**asset, "status": "pending", "message": None, "model": None,
             "history": None, "replay_cycles": None, "replay_status": "missing"}
    replay = archived_replay(root, symbol)
    if replay:
        entry.update(replay_cycles=replay["cycles"], replay_status="available")
    elif (replay_directory(root, symbol) / "replay_iniciado.json").is_file():
        entry["replay_status"] = "interrupted"
    try:
        contract = registry.contract(symbol)
        lock = read_json(folder / "evaluacion_TE.lock.json") or {}
        entry.update(status="ready", model={
            "experiment": contract["selected_experiment"], "version": contract["version"],
            "features": contract["features"], "lookback": contract["lookback"],
            "seed": contract["seed"], "device": contract["training_device"],
            "threshold": contract["threshold"], "technical_filter": contract["technical_filter"],
            "model_sha256": contract["model_sha256"], "scalers_sha256": contract["scalers_sha256"],
            "data_sha256": contract["data_sha256"], "evaluated_at": lock.get("evaluated_at"),
            "metrics": records(folder / "metricas_finales.csv"),
            "partitions": records(folder / "particiones.csv"),
            "inference_error": verification.get("inferencia_y_api", {}).get("errores_por_activo", {}).get(symbol),
        })
        frame = historical_frame(root, symbol, contract)
        forecast = historical_forecast(folder, contract)
        entry["history"] = market_view(symbol, frame, "historical", forecast, chart_size=30)
    except (PaiError, OSError, KeyError, ValueError, TypeError) as exc:
        entry["message"] = str(exc)
    return entry


def research_history(root, symbol, contract):
    """Supply only candles whose close predates the project's formal test set."""
    partitions = records(root / "artifacts" / symbol / "particiones.csv")
    test = next((row for row in partitions if row.get("conjunto") == "TE"), None)
    if not test:
        raise PaiError("Falta la frontera del conjunto TE del proyecto.")
    boundary = pd.to_datetime(test.get("primer_objetivo"), utc=True, errors="coerce")
    if pd.isna(boundary):
        raise PaiError("La fecha de inicio de TE no es válida.")
    cutoff_ms = int(boundary.value // 1_000_000)
    frame = historical_frame(root, symbol, contract)
    relevant = frame.loc[frame.close_time < cutoff_ms]
    if len(relevant) < 600:
        raise PaiError("Se necesitan al menos 600 velas verificadas previas a TE.")
    return {
        "symbol": symbol,
        "excluded_from_ms": cutoff_ms,
        "sha256": contract["data_sha256"],
        "bars": [
            [int(bar.open_time), float(bar.open), float(bar.high), float(bar.low),
             float(bar.close), float(bar.volume)]
            for bar in relevant.itertuples()
        ],
    }


def laboratory_router(root, registry, market, access, llm):
    root = Path(root)
    router = APIRouter(prefix="/api/lab", dependencies=access)

    def require_symbol(symbol):
        if symbol not in symbols():
            raise HTTPException(404, "Activo fuera del catálogo.")

    @router.get("/research/{symbol}")
    def research(symbol: str):
        require_symbol(symbol)
        return research_history(root, symbol, registry.contract(symbol))

    @router.post("/research/{symbol}/ideas")
    def ideas(symbol: str):
        require_symbol(symbol)
        history = research_history(root, symbol, registry.contract(symbol))
        calibration = history["bars"][:int(len(history["bars"]) * .55)]
        observations = {
            "symbol": symbol, "interval": "1d", "candles": len(calibration),
            "median_intraday_range_pct": round(100 * float(pd.Series([
                (bar[2] - bar[3]) / bar[1] for bar in calibration
            ]).median()), 3),
        }
        try:
            return llm.strategy_ideas(observations)
        except PaiError as exc:
            raise HTTPException(503, str(exc)) from exc

    @router.get("/catalog")
    def catalog():
        verification = read_json(root / "evidencia" / "verificacion_entrega.json") or {}
        return {
            "assets": [catalog_entry(root, registry, asset, verification) for asset in project()["assets"]],
            "verification": {
                "tests": verification.get("pruebas"),
                "colab_files": verification.get("archivos_colab_verificados"),
                "notebook_url": verification.get("cuaderno_colab", {}).get("url"),
                "max_prediction_error": verification.get("inferencia_y_api", {}).get("error_maximo_vs_colab"),
            },
            "version": (read_json(root / "VERSION.json") or {}).get("version", "local"),
        }

    @router.get("/market/{symbol}")
    def selected_market(symbol: str, source: Source = "historical"):
        require_symbol(symbol)
        if source == "historical":
            contract = registry.contract(symbol)
            frame = historical_frame(root, symbol, contract)
            forecast = historical_forecast(root / "artifacts" / symbol, contract)
            return market_view(symbol, frame, "historical", forecast)
        try:
            now_ms = market.server_time()
            frame = live_candles(market, symbol, now_ms, 220)
        except PaiError as exc:
            raise HTTPException(503, str(exc)) from exc
        forecast = None
        model_message = None
        try:
            snap = registry.forecast(symbol, frame)
            filter_ok = not snap["technical_filter"] or snap["dist_sma20"] > 0
            forecast = {
                "value": snap["forecast"], "threshold": snap["threshold"],
                "technical_filter": snap["technical_filter"],
                "signal": snap["forecast"] > snap["threshold"] and filter_ok,
                "issue_ms": snap["close_ms"],
                "target_ms": int(pd.Timestamp(snap["target_period"]).value // 1_000_000),
            }
        except PaiError as exc:
            model_message = str(exc)
        return {**market_view(symbol, frame, "live", forecast, now_ms), "model_message": model_message}

    @router.get("/scanner")
    def scanner():
        try:
            now_ms = market.server_time()
        except PaiError as exc:
            raise HTTPException(503, str(exc)) from exc
        rows = []
        for symbol in symbols():
            began = time.monotonic()
            try:
                frame = live_candles(market, symbol, now_ms, 90)
                snapshot = market_view(symbol, frame, "live", None, now_ms, chart_size=30)
                rows.append({"symbol": symbol, "market": snapshot, "error": None,
                             "latency_ms": (time.monotonic() - began) * 1000})
            except PaiError as exc:
                rows.append({"symbol": symbol, "market": None, "error": str(exc), "latency_ms": None})
        return {"updated_ms": now_ms, "rows": rows}

    @router.get("/replay/{symbol}")
    def replay(symbol: str):
        require_symbol(symbol)
        summary = archived_replay(root, symbol)
        if not summary:
            raise HTTPException(404, "Este activo todavía no tiene un replay guardado.")
        folder = replay_directory(root, symbol)
        verification = read_json(folder / "verificacion_inferencia.json") or {}
        start = read_json(folder / "replay_iniciado.json") or {}
        llm = verification.get("ollama") or start.get("llm") or {}
        return {
            **summary,
            "records": {
                key: {table: records(folder / f"{key}_{table}.csv") for table in TABLES}
                for key in STRATEGIES
            },
            "llm": {key: llm.get(key) for key in ("model", "ollama_version", "processor", "local", "digest")},
            "inference_error": verification.get("error_absoluto_maximo_vs_colab"),
        }

    @router.get("/replay/{symbol}/download/{kind}")
    def download(symbol: str, kind: str, strategy: str = "agente_con_llm"):
        require_symbol(symbol)
        if not archived_replay(root, symbol):
            raise HTTPException(404, "Replay no disponible.")
        if kind == "comparison":
            name = "comparacion.csv"
        elif kind in TABLES and strategy in STRATEGIES:
            name = f"{strategy}_{kind}.csv"
        else:
            raise HTTPException(404, "Registro no exportable.")
        file = replay_directory(root, symbol) / name
        if not file.is_file():
            raise HTTPException(404, "Archivo de evidencia no disponible.")
        return FileResponse(file, media_type="text/csv", filename=f"{symbol}_{name}")

    return router
