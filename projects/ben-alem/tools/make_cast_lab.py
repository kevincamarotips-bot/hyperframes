"""Monta o teste de rig do elenco embutindo todos os SVGs, rigs e o motor.

Uso: python make_cast_lab.py <dir-com-os-svgs> <saida-dir>
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAST = [("salsicha", "Salsicha"), ("preguica_a", "Preguiça A"), ("preguica_b", "Preguiça B"),
        ("porco_espinho", "Porco-espinho"), ("galinha", "Galinha"), ("elefante", "Elefante"),
        ("pinguim", "Pinguim"), ("tartaruga", "Tartaruga"), ("alienigena", "Alienígena"), ("cavalo", "Cavalo")]


def main(asset_dir, out_dir):
    assets, out = Path(asset_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    html = (ROOT / "lab/cast-rig-test/index.template.html").read_text(encoding="utf-8")
    cells, rigs = [], {}
    for name, label in CAST:
        svg = (assets / f"{name}.svg").read_text(encoding="utf-8")
        cells.append(f'<div class="cell">{svg}<span>{label}</span></div>')
        rigs[name] = json.loads((assets / f"{name}.rig.json").read_text(encoding="utf-8"))
    rig_js = (ROOT / "lib/rig/svg-rig.js").read_text(encoding="utf-8").replace("export function", "function")
    html = html.replace("<!--CAST_SVGS-->", "\n".join(cells))
    html = html.replace("/*__RIG_JS__*/", rig_js)
    html = html.replace("/*__CAST_RIGS__*/ null", json.dumps(rigs, ensure_ascii=False))
    (out / "index.html").write_text(html, encoding="utf-8")
    print(out / "index.html")


if __name__ == "__main__":
    main(*sys.argv[1:3])
