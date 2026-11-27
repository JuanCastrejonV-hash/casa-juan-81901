"""Bundle the verified historical dashboard into an HTML file for offline review."""

import json
import re
import secrets
import sys
from pathlib import Path

from fastapi.testclient import TestClient

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from backend.app import Settings, create_app
from backend.store import Store


def snapshot():
    keys = [secrets.token_urlsafe(40) for _ in range(3)]
    settings = Settings(*keys, root=root)
    store = Store(":memory:")
    try:
        # These endpoints read the delivered files. The export has no market or Ollama connection.
        app = create_app(settings=settings, store=store, market=object(), llm=object())
        with TestClient(app) as client:
            data = {}

            def add(path):
                response = client.get("/api" + path, headers={"X-API-Key": keys[0]})
                response.raise_for_status()
                data[path] = response.json()
                return data[path]

            assets = add("/lab/catalog")["assets"]
            add("/config")
            for asset in assets:
                symbol = asset["symbol"]
                if asset["history"]:
                    add(f"/lab/market/{symbol}?source=historical")
                    add(f"/lab/research/{symbol}")
                if asset["replay_status"] == "available":
                    add(f"/lab/replay/{symbol}")
            return data
    finally:
        store.close()


def inline_assets(data):
    distribution = root / "frontend" / "dist"
    html = (distribution / "index.html").read_text(encoding="utf-8")
    js = re.compile(r'<script type="module"[^>]* src="(/assets/[^"]+\.js)"></script>')
    css = re.compile(r'<link rel="stylesheet"[^>]* href="(/assets/[^"]+\.css)">')
    seed = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":")).replace("<", "\\u003c")

    def inline_script(match):
        path = distribution / match.group(1).lstrip("/")
        code = path.read_text(encoding="utf-8").replace("</script", "<\\/script")
        return f"<script>window.__PAI_ARCHIVE__={seed};</script>\n<script type=\"module\">{code}</script>"

    def inline_style(match):
        path = distribution / match.group(1).lstrip("/")
        return "<style>" + path.read_text(encoding="utf-8").replace("</style", "<\\/style") + "</style>"

    html, js_count = js.subn(inline_script, html)
    html, css_count = css.subn(inline_style, html)
    if js_count != 1 or css_count != 1:
        raise RuntimeError("Compila el frontend en un bundle único antes de exportar la vista.")
    return html


if __name__ == "__main__":
    path = root / "Abrir_Casa_Juan_81901.html"
    data = snapshot()
    path.write_text(inline_assets(data), encoding="utf-8")
    print(f"{path.name} · {len(data['/lab/catalog']['assets'])} activos")
