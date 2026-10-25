"""Monta uma folha de teste do Ben embutindo SVG, rig.json e as bibliotecas.

Uso: python make_lab.py <dir-com-ben-side.svg> <saida-dir> [lab]
`lab` é a pasta em lab/ com o index.template.html (padrão: ben-rig-test).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def lib(path):
    return (ROOT / path).read_text(encoding="utf-8").replace("export function", "function")


def main(asset_dir, out_dir, lab="ben-rig-test"):
    assets, out = Path(asset_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    html = (ROOT / "lab" / lab / "index.template.html").read_text(encoding="utf-8")
    html = html.replace("<!--BEN_SVG-->", (assets / "ben-side.svg").read_text(encoding="utf-8"))
    html = html.replace("/*__RIG_JS__*/", lib("lib/rig/svg-rig.js"))
    html = html.replace("/*__LOCO_JS__*/", lib("lib/ben/locomotion.js"))
    html = html.replace("/*__RIG_JSON__*/ null", (assets / "ben-side.rig.json").read_text(encoding="utf-8"))
    (out / "index.html").write_text(html, encoding="utf-8")
    print(out / "index.html")


if __name__ == "__main__":
    main(*sys.argv[1:4])
