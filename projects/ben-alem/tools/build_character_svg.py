"""Recria um personagem do livro em SVG, separado em partes para o rig.

Genérico, dirigido por uma configuração JSON em tools/characters/<nome>.json:
paleta, ossos (pai + pivô), partes (região, camadas de cor, extensões ocultas)
e olhos (elipse + pupila independente). Coordenadas sempre em px da imagem-fonte.

Uso:
  python build_character_svg.py <config.json> <dir-das-imagens-fonte> <saida-dir>

Cada parte reivindica os pixels da sua região (a de menor `priority` vence onde
regiões se cruzam). Por baixo das camadas de cor vai um preenchimento com a cor
`under`, que também cobre as áreas `extend` — o que o desenho esconde e precisa
existir quando a parte gira.
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import potrace
from PIL import Image


def hex_rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


class Builder:
    def __init__(self, cfg, src_dir):
        self.cfg = cfg
        self.up = cfg.get("upscale", 2)
        im = Image.open(Path(src_dir) / cfg["source"]).convert("RGBA")
        if "crop" in cfg:
            x0, y0, x1, y1 = cfg["crop"]
            im = im.crop((x0, y0, x1, y1))
            self.offset = (x0, y0)
        else:
            self.offset = (0, 0)
        self.W, self.H = im.size
        big = np.array(im.resize((self.W * self.up, self.H * self.up), Image.LANCZOS)).astype(np.float32)
        self.shape = big.shape[:2]
        alpha = big[..., 3]
        sigma = cfg.get("smooth", 0.0) * self.up
        if sigma > 0:
            alpha = cv2.GaussianBlur(alpha, (0, 0), sigma)
        self.alpha = alpha >= cfg.get("alphaCut", 128)
        names = list(cfg["palette"].keys())
        cols = np.stack([hex_rgb(cfg["palette"][n]) for n in names])
        rgb = big[..., :3]
        if sigma > 0:
            rgb = cv2.GaussianBlur(rgb, (0, 0), sigma * 0.5)
        dist = ((rgb[:, :, None, :] - cols[None, None]) ** 2).sum(-1)
        self.cls = np.argmin(dist, -1)
        self.names = names
        self.ys = np.arange(self.shape[0])[:, None]
        self.xs = np.arange(self.shape[1])[None, :]

    # --- utilidades em coordenadas da fonte ---------------------------------
    def P(self, pts):
        ox, oy = self.offset
        return np.array([((x - ox) * self.up, (y - oy) * self.up) for x, y in pts], np.int32)

    def poly(self, polys):
        m = np.zeros(self.shape, np.uint8)
        if polys == "all":
            return np.ones(self.shape, bool)
        if polys and isinstance(polys[0][0], (int, float)):
            polys = [polys]
        for pts in polys:
            cv2.fillPoly(m, [self.P(pts)], 1)
        return m.astype(bool)

    def color(self, names):
        idx = [self.names.index(n) for n in names]
        return self.alpha & np.isin(self.cls, idx)

    @staticmethod
    def fill_holes(mask):
        m = mask.astype(np.uint8)
        h, w = m.shape
        flood = m.copy()
        cv2.floodFill(flood, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 1)
        return mask | (flood == 0)

    def clean(self, mask, px):
        if px <= 0:
            return mask
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(px * self.up) * 2 + 1,) * 2)
        m = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, k)
        return cv2.morphologyEx(m, cv2.MORPH_CLOSE, k).astype(bool)

    def trace(self, mask, turd=None):
        ys, xs = np.nonzero(mask)
        if len(xs) == 0:
            return ""
        turd = turd if turd is not None else 4 * self.up
        x0, y0 = max(xs.min() - 2, 0), max(ys.min() - 2, 0)
        crop = mask[y0:ys.max() + 3, x0:xs.max() + 3]
        path = potrace.Bitmap(~crop).trace(turdsize=turd, alphamax=1.1, opticurve=True, opttolerance=0.3)
        ox, oy = self.offset

        def p(pt):
            return f"{(pt.x + x0) / self.up + ox:.1f},{(pt.y + y0) / self.up + oy:.1f}"

        out = []
        for curve in path:
            d = [f"M{p(curve.start_point)}"]
            for seg in curve:
                if seg.is_corner:
                    d.append(f"L{p(seg.c)}L{p(seg.end_point)}")
                else:
                    d.append(f"C{p(seg.c1)} {p(seg.c2)} {p(seg.end_point)}")
            out.append("".join(d) + "Z")
        return "".join(out)

    # --- olhos ----------------------------------------------------------------
    def eye(self, part, claimed):
        region = self.poly(part["region"]) & claimed
        white = region & self.color(part.get("white", ["white"]))
        n, lab, stats, _ = cv2.connectedComponentsWithStats(white.astype(np.uint8), 8)
        k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        m = self.fill_holes(lab == k)
        cnts, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        pts = max(cnts, key=cv2.contourArea).reshape(-1, 2).astype(np.float32)
        (cx, cy), (w, h), ang = cv2.fitEllipse(pts)
        ox, oy = self.offset
        e = {"cx": cx / self.up + ox, "cy": cy / self.up + oy, "rx": w / 2 / self.up, "ry": h / 2 / self.up, "rot": ang}
        inner = np.zeros(self.shape, np.uint8)
        cv2.ellipse(inner, (int(cx), int(cy)), (int(w / 2 * 0.92), int(h / 2 * 0.92)), ang, 0, 360, 1, -1)
        dark = inner.astype(bool) & self.color(part.get("pupil", ["black"]))
        ys, xs = np.nonzero(dark)
        if len(xs):
            pupil = {"cx": xs.mean() / self.up + ox, "cy": ys.mean() / self.up + oy,
                     "r": max(1.2, float(np.sqrt(len(xs) / np.pi)) / self.up)}
        else:
            pupil = {"cx": e["cx"], "cy": e["cy"], "r": min(e["rx"], e["ry"]) * 0.3}
        if "pupilR" in part:
            pupil["r"] = part["pupilR"]
        full = np.zeros(self.shape, np.uint8)
        # área do olho (com folga): o branco que sobra fora da elipse não vai parar em outra parte
        pad = 4 * self.up
        cv2.ellipse(full, (int(cx), int(cy)), (int(w / 2 + pad), int(h / 2 + pad)), ang, 0, 360, 1, -1)
        return e, pupil, full.astype(bool)

    # --- montagem -------------------------------------------------------------
    def build(self):
        cfg = self.cfg
        parts = cfg["parts"]
        # olhos primeiro: o branco deles não pode ser reivindicado pela cabeça
        order = sorted(range(len(parts)), key=lambda i: parts[i].get("priority", -1 if parts[i].get("type") == "eye" else i))
        taken = np.zeros(self.shape, bool)
        owner = np.full(self.shape, -1, np.int16)  # índice da parte dona de cada pixel
        eye_area = np.zeros(self.shape, bool)
        claims = {}
        for i in order:
            part = parts[i]
            if part.get("type") == "svg":
                claims[part["name"]] = ("svg",)
                continue
            reg = self.poly(part.get("region", "all")) & ~taken
            if part.get("type") == "eye":
                # olhos não reivindicam pixels: a cabeça continua inteira por baixo
                e, pupil, full = self.eye(part, reg)
                claims[part["name"]] = ("eye", e, pupil)
                eye_area |= full
            else:
                # a parte só reivindica pixels das suas cores: uma perna atrás de uma
                # mancha do corpo não rouba a mancha
                layer_names = [n for lay in part.get("layers", [[n] for n in self.names]) for n in lay]
                reg = reg & self.color(layer_names)
                claims[part["name"]] = ("region", reg)
                if not part.get("shared", False):
                    owner[reg & (owner < 0)] = i
                    taken |= reg
        # sobras: pixel do desenho sem dono vai para a parte mais próxima que tem a cor dele
        unowned = self.alpha & (owner < 0) & ~eye_area
        if unowned.any():
            best = np.full(self.shape, np.inf, np.float32)
            best_idx = np.full(self.shape, -1, np.int16)
            for i, part in enumerate(parts):
                kind = claims[part["name"]]
                if kind[0] != "region" or part.get("noFallback") or not kind[1].any():
                    continue
                names = [n for lay in part.get("layers", [[n] for n in self.names]) for n in lay]
                dist = cv2.distanceTransform((~kind[1]).astype(np.uint8), cv2.DIST_L2, 3)
                dist = np.where(self.color(names), dist, np.inf)
                upd = dist < best
                best[upd] = dist[upd]
                best_idx[upd] = i
            reach = self.cfg.get("fallbackReach", 30) * self.up
            for i, part in enumerate(parts):
                sel = unowned & (best_idx == i) & (best <= reach)
                if sel.any():
                    claims[part["name"]] = ("region", claims[part["name"]][1] | sel)
                    owner[sel] = i
        silhouette = self.fill_holes(self.alpha)
        groups = []
        eye_pivots = {}
        char = cfg["name"]
        for idx, part in enumerate(parts):
            name = part["name"]
            kind = claims[name]
            if kind[0] == "svg":
                # peça desenhada em geometria limpa (vidros, hélices, capôs translúcidos no original)
                groups.append(f'<g id="{char}-{name}" data-part="{name}">{part["svg"]}</g>')
                continue
            if kind[0] == "eye":
                groups.append(self.eye_svg(char, part, kind[1], kind[2]))
                eye_pivots[part.get("bone", name)] = [round(kind[1]["cx"], 1), round(kind[1]["cy"], 1)]
                eye_pivots[part.get("pupilBone", name + "_pupil")] = [round(kind[2]["cx"], 1), round(kind[2]["cy"], 1)]
                continue
            reg = kind[1]
            layers = part.get("layers", [[n] for n in self.names])
            masks = [self.color(lay) & reg for lay in layers]
            union = np.zeros(self.shape, bool)
            for m in masks:
                union |= m
            union = self.clean(union, part.get("clean", 0.6))
            if part.get("fillHoles", True):
                union = self.fill_holes(union)
            under = part.get("under")
            ext = None
            if "extend" in part:
                # área oculta: só dentro da silhueta e onde fica escondida — sob uma parte
                # desenhada na frente, ou sobre pixels da mesma cor
                in_front = np.isin(owner, [j for j in range(idx + 1, len(parts))])
                same = self.color([under]) if under else np.zeros(self.shape, bool)
                ext = self.poly(part["extend"]) & silhouette & (in_front | same)
                union |= ext
            body = []
            grow = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(part.get("grow", 1) * self.up) * 2 + 1,) * 2)
            if under:
                # recolhe a base onde a borda é de outra cor: sem halo sob o contorno
                k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * self.up + 1,) * 2)
                base = cv2.erode(union.astype(np.uint8), k).astype(bool) | (union & self.color([under]))
                # 1 px de sobra dentro da silhueta: as juntas entre peças não deixam fresta
                base |= cv2.dilate(base.astype(np.uint8), grow).astype(bool) & silhouette & self.color([under])
                if ext is not None:
                    base |= ext
                body.append(self.path(self.trace(base), cfg["palette"][under]))
            for lay, m in zip(layers, masks):
                if under and lay == [under]:
                    continue
                m = self.clean(m & union, part.get("cleanLayer", 0.4))
                m |= cv2.dilate(m.astype(np.uint8), grow).astype(bool) & silhouette & self.color(lay) & union
                fill = cfg["palette"][lay[0]]
                body.append(self.path(self.trace(m, turd=2 * self.up), fill))
            extra = part.get("svg", "")
            groups.append(f'<g id="{char}-{name}" data-part="{name}">{"".join(body)}{extra}</g>')

        ox, oy = self.offset
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{ox} {oy} {self.W} {self.H}" '
               f'width="{self.W}" height="{self.H}" id="{char}" data-character="{char}">'
               + "\n".join(groups) + "</svg>")
        part_bones = {p["name"]: p["bone"] for p in parts if p.get("bone") and p["bone"] != p["name"]}
        rig = {
            "character": char,
            "source": cfg.get("sourceNote", cfg["source"]),
            "units": "px da fonte",
            # pivôs de olhos e pupilas vêm da geometria detectada
            "bones": [{**b, "pivot": eye_pivots.get(b["name"], b["pivot"])} for b in cfg["bones"]],
            "drawOrder": [p["name"] for p in parts],
            "partBones": part_bones,
            "slots": {"eyes": ["open", "happy", "flat"]},
        }
        return svg, rig

    @staticmethod
    def path(d, fill):
        return f'<path d="{d}" fill="{fill}" fill-rule="evenodd"/>' if d else ""

    def eye_svg(self, char, part, e, p):
        name = part["name"]
        pupil_bone = part.get("pupilBone", name + "_pupil")
        ink = part.get("pupilFill", self.cfg["palette"].get("black", "#000000"))
        white = self.cfg["palette"][part.get("white", ["white"])[0]]
        grow = part.get("scleraGrow", 0.8)  # cobre o antialias da borda original
        e = {**e, "rx": e["rx"] + grow, "ry": e["ry"] + grow}
        rx, cx, cy = min(e["rx"], e["ry"]), e["cx"], e["cy"]
        sw = rx * 0.18
        happy = f"M{cx - rx * 0.55:.1f},{cy + rx * 0.12:.1f} Q{cx:.1f},{cy - rx * 0.5:.1f} {cx + rx * 0.55:.1f},{cy + rx * 0.12:.1f}"
        flat = f"M{cx - rx * 0.6:.1f},{cy:.1f} L{cx + rx * 0.6:.1f},{cy:.1f}"
        return (
            f'<g id="{char}-{name}" data-part="{name}">'
            f'<ellipse class="sclera" cx="{cx:.1f}" cy="{cy:.1f}" rx="{e["rx"]:.1f}" ry="{e["ry"]:.1f}" '
            f'transform="rotate({e["rot"]:.1f} {cx:.1f} {cy:.1f})" fill="{white}"/>'
            f'<g data-part="{pupil_bone}"><circle class="pupil" cx="{p["cx"]:.1f}" cy="{p["cy"]:.1f}" r="{p["r"]:.1f}" fill="{ink}"/></g>'
            f'<path class="slot slot-happy" d="{happy}" fill="none" stroke="{ink}" stroke-width="{sw:.1f}" stroke-linecap="round" display="none"/>'
            f'<path class="slot slot-flat" d="{flat}" fill="none" stroke="{ink}" stroke-width="{sw:.1f}" stroke-linecap="round" display="none"/>'
            f"</g>"
        )


def main(cfg_path, src_dir, out_dir):
    cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    svg, rig = Builder(cfg, src_dir).build()
    (out / f'{cfg["name"]}.svg').write_text(svg, encoding="utf-8")
    (out / f'{cfg["name"]}.rig.json').write_text(json.dumps(rig, indent=2, ensure_ascii=False), encoding="utf-8")
    print("ok", cfg["name"])


if __name__ == "__main__":
    main(*sys.argv[1:4])
