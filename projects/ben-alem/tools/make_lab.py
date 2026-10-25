"""Monta a folha de teste do rig embutindo SVG, rig.json e o motor de rig.

Uso: python make_lab.py <dir-com-ben-side.svg> <saida-dir>
"""

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def main(asset_dir, out_dir):
    assets, out = Path(asset_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    html = (ROOT / "lab/ben-rig-test/index.template.html").read_text(encoding="utf-8")
    rig_js = (ROOT / "lib/rig/svg-rig.js").read_text(encoding="utf-8").replace("export function", "function")
    html = html.replace("<!--BEN_SVG-->", (assets / "ben-side.svg").read_text(encoding="utf-8"))
    html = html.replace("/*__RIG_JS__*/", rig_js)
    html = html.replace("/*__RIG_JSON__*/ null", (assets / "ben-side.rig.json").read_text(encoding="utf-8"))
    (out / "index.html").write_text(html, encoding="utf-8")
    shutil.copy(assets / "ben-side.rig.json", out / "ben-side.rig.json")
    print(out / "index.html")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
