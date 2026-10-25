"""Recria o Ben (vista de perfil) em SVG, separado em partes para o rig.

Entrada: a pose de perfil extraída do PDF de prova (página 6, a da régua) como
PNG RGBA. Saída: um SVG com um <g> por parte (pose de repouso, sem transforms)
e um rig.json com pivôs, hierarquia e ordem de desenho.

As partes são traçadas da arte original (potrace) para preservar a borda de
pincel; as áreas que o desenho esconde (base das orelhas, raiz da cauda, topo
das patas, pescoço) são estendidas para que nada abra buraco quando a parte gira.

Uso:
  python build_ben_svg.py <ben-pose.png> <saida-dir>
Requer: numpy, pillow, opencv-python-headless, potracer.
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import potrace
from PIL import Image

UP = 2  # traça em 2x para curvas mais suaves; o SVG fica nas unidades da fonte
INK = "#000000"
PAPER = "#ffffff"

# Regiões em px da fonte (1398 × 972). Ver docs/02-ben-svg-rig.md.
TAIL_REGION = [(0, 380), (300, 380), (300, 418), (262, 440), (240, 480), (234, 530),
               (222, 575), (205, 640), (188, 700), (160, 780), (0, 780)]
TAIL_ROOT_EXT = [(150, 425), (330, 418), (345, 500), (268, 500), (240, 488)]
HEAD_REGION = [(700, 425), (1390, 425), (1390, 610), (1130, 610), (1120, 590), (1060, 585),
               (960, 585), (880, 560), (800, 500), (730, 470)]
HEAD_FACE_TOP = 530  # acima disto, a região da cabeça sai do corpo (evita “fantasma” branco)
MUZZLE_ONLY_X = 1135  # à direita disto e acima de 610 é só focinho, nunca corpo
NOSE_BOX = (1270, 360, 1398, 480)
PAW_SPLITS = [("paw_back_a", 300, 409), ("paw_back_b", 409, 500),
              ("paw_front_a", 790, 903), ("paw_front_b", 903, 1000)]
PAW_TOP_Y = 815
SEAM = 6
EAR_SPLIT_X = 935
EYE_SEEDS = {"eye_back": (838, 360), "eye_front": (1036, 370)}


def poly_mask(shape, pts, scale=UP):
    m = np.zeros(shape, np.uint8)
    cv2.fillPoly(m, [np.array([(x * scale, y * scale) for x, y in pts], np.int32)], 1)
    return m.astype(bool)


def fill_holes(mask):
    m = mask.astype(np.uint8)
    h, w = m.shape
    flood = m.copy()
    pad = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(flood, pad, (0, 0), 1)
    return mask | (flood == 0)


def largest_component(mask):
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    if n <= 1:
        return mask
    k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return lab == k


def trace(mask, turd=8):
    """Bool mask (em UP×) → string `d` em unidades da fonte."""
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return ""
    x0, y0 = max(xs.min() - 2, 0), max(ys.min() - 2, 0)
    crop = mask[y0:ys.max() + 3, x0:xs.max() + 3]
    path = potrace.Bitmap(~crop).trace(turdsize=turd, alphamax=1.0, opticurve=True, opttolerance=0.2)

    def P(p):
        return f"{(p.x + x0) / UP:.1f},{(p.y + y0) / UP:.1f}"

    out = []
    for curve in path:
        d = [f"M{P(curve.start_point)}"]
        for seg in curve:
            if seg.is_corner:
                d.append(f"L{P(seg.c)}L{P(seg.end_point)}")
            else:
                d.append(f"C{P(seg.c1)} {P(seg.c2)} {P(seg.end_point)}")
        out.append("".join(d) + "Z")
    return "".join(out)


def fit_eye(white, seed):
    """Elipse alinhada aos eixos, ajustada pelo arco superior do branco do olho
    (embaixo o olho encosta no focinho e os contornos se fundem)."""
    sx, sy = seed[0] * UP, seed[1] * UP
    box = np.zeros_like(white)
    box[(seed[1] - 110) * UP:(seed[1] + 62) * UP, (seed[0] - 100) * UP:(seed[0] + 100) * UP] = True
    comp = cv2.connectedComponents((white & box).astype(np.uint8), connectivity=8)[1]
    m = comp == comp[sy, sx]
    cnts, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    pts = max(cnts, key=cv2.contourArea).reshape(-1, 2).astype(np.float64)
    pts = pts[pts[:, 1] < (seed[1] + 45) * UP]
    x, y = pts[:, 0], pts[:, 1]
    # A·x² + C·y² + D·x + E·y = 1
    A, C, D, E = np.linalg.lstsq(np.stack([x * x, y * y, x, y], 1), np.ones_like(x), rcond=None)[0]
    cx, cy = -D / (2 * A), -E / (2 * C)
    k = 1 + A * cx * cx + C * cy * cy
    e = {"cx": cx / UP, "cy": cy / UP, "rx": float(np.sqrt(k / A)) / UP, "ry": float(np.sqrt(k / C)) / UP, "rot": 0.0}
    # esclera = branco real do olho (arco superior irregular do pincel) ∪ elipse ajustada (base)
    return e, m


def ellipse_mask(shape, e, grow=0.0):
    m = np.zeros(shape, np.uint8)
    cv2.ellipse(m, (int(e["cx"] * UP), int(e["cy"] * UP)),
                (int((e["rx"] + grow) * UP), int((e["ry"] + grow) * UP)), e["rot"], 0, 360, 1, -1)
    return m.astype(bool)


def pupil_of(black, eye):
    inside = ellipse_mask(black.shape, eye, grow=-3) & black
    ys, xs = np.nonzero(inside)
    return {"cx": xs.mean() / UP, "cy": ys.mean() / UP, "r": float(np.sqrt(len(xs) / np.pi)) / UP}


def ear_base_extension(ear, eye):
    """Prolonga a base da orelha para dentro do olho que a cobre."""
    ys, xs = np.nonzero(ear & ellipse_mask(ear.shape, eye, grow=2))
    if len(xs) == 0:
        ys, xs = np.nonzero(ear)
        keep = ys > ys.max() - 40 * UP
        ys, xs = ys[keep], xs[keep]
    pts = np.stack([xs, ys], 1)
    pts = np.concatenate([pts, pts + [0, 70 * UP]])
    hull = cv2.convexHull(pts.astype(np.int32))
    m = np.zeros(ear.shape, np.uint8)
    cv2.fillConvexPoly(m, hull, 1)
    return m.astype(bool) & ellipse_mask(ear.shape, eye, grow=-6)


def clean_paw(paw):
    """Pata = parte visível (abaixo do corpo) + topo em meia-elipse lisa que some sob
    o corpo. Corta as lascas de branco do corpo que o recorte por faixa arrasta junto."""
    ys, xs = np.nonzero(paw)
    top, bottom = ys.min(), ys.max()
    low = paw & (np.arange(paw.shape[0])[:, None] > top + (bottom - top) * 0.35)
    lys, lxs = np.nonzero(low)
    x0, x1 = lxs.min(), lxs.max()
    body = paw.copy()
    body[:, :x0] = False
    body[:, x1 + 1:] = False
    m = np.zeros(paw.shape, np.uint8)
    cx, rx = (x0 + x1) // 2, (x1 - x0) // 2
    mid = top + (bottom - top) // 3
    cv2.ellipse(m, (int(cx), int(mid)), (int(rx * 0.96), int(mid - top + 34 * UP)), 0, 180, 360, 1, -1)
    cv2.rectangle(m, (int(cx - rx * 0.96), int(mid)), (int(cx + rx * 0.96), int(mid + 4 * UP)), 1, -1)
    return largest_component(body | m.astype(bool))


def smooth(mask, px):
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (px * UP * 2 + 1,) * 2)
    m = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, k)
    return cv2.morphologyEx(m, cv2.MORPH_OPEN, k).astype(bool)


def main(src, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    im = Image.open(src).convert("RGBA")
    W, H = im.size
    big = np.array(im.resize((W * UP, H * UP), Image.LANCZOS)).astype(np.float32)
    alpha = big[..., 3] >= 128
    lum = big[..., :3] @ np.array([0.299, 0.587, 0.114])
    black = alpha & (lum < 110)
    white = alpha & (lum >= 110)
    shape = alpha.shape
    ys_grid = np.arange(shape[0])[:, None]

    fits = {k: fit_eye(white, s) for k, s in EYE_SEEDS.items()}
    eyes = {k: f[0] for k, f in fits.items()}
    sclera = {k: fill_holes(f[1] | ellipse_mask(white.shape, f[0])) for k, f in fits.items()}
    pupils = {k: pupil_of(black, e) for k, e in eyes.items()}
    eyes_mask = ellipse_mask(shape, eyes["eye_back"], 1.5) | ellipse_mask(shape, eyes["eye_front"], 1.5)

    nx0, ny0, nx1, ny1 = NOSE_BOX
    nose = black & poly_mask(shape, [(nx0, ny0), (nx1, ny0), (nx1, ny1), (nx0, ny1)])

    # as orelhas ficam atrás dos olhos: não recortar pelo olho evita vão na borda
    ears_all = black & (np.arange(shape[0])[:, None] < 410 * UP) & ~nose
    xs_grid = np.arange(shape[1])[None, :]
    ear_back = largest_component(ears_all & (xs_grid < EAR_SPLIT_X * UP))
    ear_front = largest_component(ears_all & (xs_grid >= EAR_SPLIT_X * UP))
    # fechamento só dentro do olho: une a base estendida à orelha sem mexer no contorno visível
    def close_inside_eye(ear, eye):
        full = ear | ear_base_extension(ear, eye)
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (12 * UP + 1,) * 2)
        closed = cv2.morphologyEx(full.astype(np.uint8), cv2.MORPH_CLOSE, k).astype(bool)
        return full | (closed & ellipse_mask(ear.shape, eye, grow=-2))

    ear_back_full = close_inside_eye(ear_back, eyes["eye_back"])
    ear_front_full = close_inside_eye(ear_front, eyes["eye_front"])

    def scalp_for(ear, eye):
        """Couro preto atrás da base da orelha, preso à cabeça: quando a orelha gira,
        o que aparece no topo do olho é pelo preto, não o céu."""
        top = int((eye["cy"] - eye["ry"]) * UP)
        band = ear & (ys_grid > top - 40 * UP)
        # alcança a borda do olho e passa por baixo da esclera (desenhada por cima)
        k = np.ones((5 * UP * 2 + 1,) * 2, np.uint8)
        under_eye = cv2.dilate(band.astype(np.uint8), k).astype(bool) & ellipse_mask(ear.shape, eye, grow=-1)
        return band | under_eye | ear_base_extension(ear, eye)

    scalp = scalp_for(ear_back, eyes["eye_back"]) | scalp_for(ear_front, eyes["eye_front"])

    tail_reg = poly_mask(shape, TAIL_REGION)
    tail = alpha & tail_reg
    silhouette = fill_holes(largest_component(alpha))
    tail_black = tail | (poly_mask(shape, TAIL_ROOT_EXT) & silhouette)  # preto também sob a ponta branca
    tail_white = white & tail

    head_reg = poly_mask(shape, HEAD_REGION)
    # branco por baixo das pinceladas pretas do corpo também: o preto é desenhado por cima
    head_white = fill_holes(largest_component(alpha & head_reg & ~nose))
    # o topo da cabeça sob as pinceladas do corpo não precisa da borda de pincel:
    # suavizado, não deixa “dentes” brancos escaparem quando a cabeça gira
    head_white = (head_white & white) | (smooth(head_white, 6) & black)

    paws = {}
    for name, x0, x1 in PAW_SPLITS:
        band = (xs_grid >= x0 * UP) & (xs_grid < x1 * UP) & (ys_grid > PAW_TOP_Y * UP)
        p = largest_component(white & band)
        paws[name] = clean_paw(p)
    paw_proper = np.zeros(shape, bool)
    for name, x0, x1 in PAW_SPLITS:
        paw_proper |= white & (xs_grid >= x0 * UP) & (xs_grid < x1 * UP) & (ys_grid > PAW_TOP_Y * UP)

    # o corpo sobrepõe cauda e patas em SEAM px: sem fresta de antialiasing nas juntas
    seam = np.ones((SEAM * UP * 2 + 1,) * 2, np.uint8)
    # sobreposição só na garupa (topo); ao longo da coxa ela viraria uma lasca preta
    # quando a cauda abana
    tail_core = np.where(ys_grid < 520 * UP, cv2.erode(tail_reg.astype(np.uint8), seam).astype(bool), tail_reg)
    paw_core = paw_proper & (ys_grid > (PAW_TOP_Y + SEAM) * UP)
    excluded = tail_core | ears_all | nose | eyes_mask | paw_core
    excluded |= head_reg & (ys_grid < HEAD_FACE_TOP * UP)
    excluded |= (xs_grid > MUZZLE_ONLY_X * UP) & (ys_grid < 610 * UP)
    body_region = alpha & ~excluded
    body_white = fill_holes(largest_component(body_region))
    # o preto do corpo inclui as pontas de pincel que avançam sobre o rosto (a cabeça fica por baixo)
    body_black = largest_component(black & ~(tail_core | ears_all | nose | eyes_mask | paw_core))

    def under_ink(mask, px=3):
        """Recolhe o branco onde a borda é preta: evita halo branco sob o contorno preto."""
        k = np.ones((px * UP * 2 + 1,) * 2, np.uint8)
        return cv2.erode(mask.astype(np.uint8), k).astype(bool) | (mask & white)


    def path(d, fill):
        return f'<path d="{d}" fill="{fill}" fill-rule="evenodd"/>' if d else ""

    def ell(e, fill, cls):
        return (f'<ellipse class="{cls}" cx="{e["cx"]:.1f}" cy="{e["cy"]:.1f}" rx="{e["rx"]:.1f}" '
                f'ry="{e["ry"]:.1f}" fill="{fill}"/>')

    def eye_group(name):
        e, p = eyes[name], pupils[name]
        rx = e["rx"]
        cx, cy = e["cx"], e["cy"]
        arc_w = rx * 0.16
        happy = (f'M{cx - rx * 0.55:.1f},{cy + rx * 0.12:.1f} Q{cx:.1f},{cy - rx * 0.5:.1f} '
                 f'{cx + rx * 0.55:.1f},{cy + rx * 0.12:.1f}')
        flat = f'M{cx - rx * 0.6:.1f},{cy + rx * 0.05:.1f} L{cx + rx * 0.6:.1f},{cy + rx * 0.05:.1f}'
        r = p["r"] * 1.15
        hx, hy = p["cx"], p["cy"]
        heart = (f'M{hx:.1f},{hy + r * 0.9:.1f} C{hx - r * 1.6:.1f},{hy - r * 0.1:.1f} {hx - r * 0.9:.1f},'
                 f'{hy - r * 1.4:.1f} {hx:.1f},{hy - r * 0.55:.1f} C{hx + r * 0.9:.1f},{hy - r * 1.4:.1f} '
                 f'{hx + r * 1.6:.1f},{hy - r * 0.1:.1f} {hx:.1f},{hy + r * 0.9:.1f}Z')
        return (
            f'<g id="ben-{name}" data-part="{name}">'
            f'<path class="sclera" d="{trace(sclera[name])}" fill="{PAPER}"/>'
            f'<g id="ben-{name}-pupil" data-part="{name}_pupil">'
            f'<circle class="pupil" cx="{p["cx"]:.1f}" cy="{p["cy"]:.1f}" r="{p["r"]:.1f}" fill="{INK}"/></g>'
            f'<path class="slot slot-happy" d="{happy}" fill="none" stroke="{INK}" stroke-width="{arc_w:.1f}" '
            f'stroke-linecap="round" display="none"/>'
            f'<path class="slot slot-flat" d="{flat}" fill="none" stroke="{INK}" stroke-width="{arc_w:.1f}" '
            f'stroke-linecap="round" display="none"/>'
            f'<path class="slot slot-heart" d="{heart}" fill="{INK}" display="none"/>'
            f'</g>'
        )

    # pivôs (px da fonte): articulações anatômicas
    e_b, e_f = eyes["eye_back"], eyes["eye_front"]
    paw_pivots = {}
    for name, p in paws.items():
        ys, xs = np.nonzero(p & paw_proper)
        paw_pivots[name] = [round(xs.mean() / UP, 1), round(ys.min() / UP, 1)]
    parts = [
        # nome, pai, pivô
        ("root", None, [650, 885]),
        ("body", "root", [650, 640]),
        ("tail", "body", [250, 470]),
        *[(n, "body", paw_pivots[n]) for n in paws],
        ("head", "body", [1000, 560]),
        ("ear_back", "head", [round(e_b["cx"] - 5, 1), round(e_b["cy"] - e_b["ry"] * 0.55, 1)]),
        ("ear_front", "head", [round(e_f["cx"] + 10, 1), round(e_f["cy"] - e_f["ry"] * 0.55, 1)]),
        ("eye_back", "head", [round(e_b["cx"], 1), round(e_b["cy"], 1)]),
        ("eye_front", "head", [round(e_f["cx"], 1), round(e_f["cy"], 1)]),
        ("eye_back_pupil", "eye_back", [round(pupils["eye_back"]["cx"], 1), round(pupils["eye_back"]["cy"], 1)]),
        ("eye_front_pupil", "eye_front", [round(pupils["eye_front"]["cx"], 1), round(pupils["eye_front"]["cy"], 1)]),
        ("nose", "head", [1318, 452]),
    ]
    draw_order = ["tail", "paw_back_a", "paw_back_b", "paw_front_a", "paw_front_b", "body_white",
                  "head", "body_black", "scalp", "ear_back", "ear_front", "eye_back", "eye_front"]

    groups = {
        "tail": path(trace(tail_black), INK) + path(trace(tail_white, turd=4), PAPER),
        "body_white": path(trace(under_ink(body_white)), PAPER),
        "body_black": path(trace(body_black, turd=4), INK),
        "head": path(trace(under_ink(head_white)), PAPER) + f'<g id="ben-nose" data-part="nose">{path(trace(nose), INK)}</g>',
        "scalp": path(trace(scalp), INK),
        "ear_back": path(trace(ear_back_full), INK),
        "ear_front": path(trace(ear_front_full), INK),
        **{n: path(trace(p), PAPER) for n, p in paws.items()},
    }
    body_parts = {"body_white", "body_black"}
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'id="ben" data-character="ben" data-view="side">']
    for name in draw_order:
        if name in ("eye_back", "eye_front"):
            svg.append(eye_group(name))
        else:
            part = "body" if name in body_parts else name
            svg.append(f'<g id="ben-{name}" data-part="{part}">{groups[name]}</g>')
    svg.append("</svg>")
    (out / "ben-side.svg").write_text("\n".join(svg), encoding="utf-8")

    rig = {
        "character": "ben",
        "view": "side",
        "source": "AF-BEN-ALEM-SeloP.pdf, página 6 (régua), 1398×972 px",
        "units": "px da fonte",
        "groundY": 885,
        "bones": [{"name": n, "parent": p, "pivot": pv} for n, p, pv in parts],
        "drawOrder": draw_order,
        "partBones": {"body_white": "body", "body_black": "body", "scalp": "head"},
        "slots": {"eyes": ["open", "happy", "flat", "heart"]},
        "eyes": {k: {**{kk: round(vv, 2) for kk, vv in e.items()}, "pupil": {kk: round(vv, 2) for kk, vv in pupils[k].items()}}
                 for k, e in eyes.items()},
    }
    (out / "ben-side.rig.json").write_text(json.dumps(rig, indent=2, ensure_ascii=False), encoding="utf-8")

    # máscaras de cada parte (para a folha explodida e a checagem de fidelidade)
    np.savez_compressed(out / "masks.npz", black=black, white=white, alpha=alpha)
    print("ok", {k: round(v["rx"], 1) for k, v in eyes.items()}, paw_pivots)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
