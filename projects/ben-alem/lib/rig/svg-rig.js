// Rig 2D para personagens em SVG separados em partes.
//
// O SVG traz a pose de repouso (sem transforms); o rig.json traz ossos com pai e
// pivô. Cada osso tem um estado animável { x, y, rot, sx, sy } em espaço do pai;
// a cada frame o rig compõe as matrizes de mundo e escreve o transform de cada
// <g data-part>. A hierarquia de ossos é independente da ordem de desenho do
// SVG: uma parte pode ficar atrás do corpo e ainda seguir a cabeça.
//
// Determinístico: nada aqui lê relógio. Quem chama decide o tempo (GSAP seek).

export function createRig(svgRoot, rigDef) {
  const bones = new Map();
  // Cada canal reescreve os transforms ao ser atribuído. O HyperFrames faz seek no
  // GSAP com callbacks suprimidos, então não dá para depender de onUpdate.
  let ready = false;
  const makeState = () => {
    const values = { x: 0, y: 0, rot: 0, sx: 1, sy: 1 };
    const state = {};
    for (const key of Object.keys(values)) {
      Object.defineProperty(state, key, {
        enumerable: true,
        get: () => values[key],
        set: (v) => {
          if (values[key] === v) return;
          values[key] = v;
          if (ready) update();
        },
      });
    }
    return state;
  };
  for (const b of rigDef.bones) {
    bones.set(b.name, { name: b.name, parent: b.parent, pivot: b.pivot, state: makeState() });
  }
  const partBone = (part) => (rigDef.partBones && rigDef.partBones[part]) || part;

  const elements = [...svgRoot.querySelectorAll("[data-part]")]
    .filter((el) => bones.has(partBone(el.dataset.part)))
    .map((el) => {
      const ancestor = el.parentElement && el.parentElement.closest("[data-part]");
      return {
        el,
        bone: partBone(el.dataset.part),
        domParentBone: ancestor ? partBone(ancestor.dataset.part) : null,
      };
    });

  function local(b) {
    const { x, y, rot, sx, sy } = b.state;
    const [px, py] = b.pivot;
    return new DOMMatrix()
      .translate(px + x, py + y)
      .rotate(rot)
      .scale(sx, sy)
      .translate(-px, -py);
  }

  function update() {
    const world = new Map();
    const resolve = (name) => {
      if (world.has(name)) return world.get(name);
      const b = bones.get(name);
      const m = b.parent ? resolve(b.parent).multiply(local(b)) : local(b);
      world.set(name, m);
      return m;
    };
    for (const { el, bone, domParentBone } of elements) {
      let m = resolve(bone);
      // partes aninhadas no DOM (pupila dentro do olho, nariz dentro da cabeça) já
      // herdam o transform do ancestral: aplicar só o que falta
      if (domParentBone) m = resolve(domParentBone).inverse().multiply(m);
      el.setAttribute("transform", `matrix(${m.a} ${m.b} ${m.c} ${m.d} ${m.e} ${m.f})`);
    }
    return world;
  }

  /** Posição de mundo de um ponto em espaço de repouso preso a um osso (para QA e IK). */
  function worldPoint(world, boneName, [x, y]) {
    const p = world.get(boneName).transformPoint(new DOMPoint(x, y));
    return [p.x, p.y];
  }

  function setSlot(partName, slot) {
    const g = [...svgRoot.querySelectorAll("[data-part]")].find(
      (el) => el.dataset.part === partName,
    );
    if (!g) return;
    for (const s of g.querySelectorAll(".slot"))
      s.setAttribute("display", s.classList.contains(`slot-${slot}`) ? "inline" : "none");
    const pupil = g.querySelector(".pupil");
    if (pupil) pupil.setAttribute("display", slot === "open" ? "inline" : "none");
  }

  /** Canal de substituição animável: `tl.set(rig.slot("eye_back"), { i: 1 }, t)`. */
  const slots = new Map();
  function slot(partName) {
    if (!slots.has(partName)) {
      const names = (rigDef.slots && rigDef.slots.eyes) || ["open"];
      let i = 0;
      const s = {};
      Object.defineProperty(s, "i", {
        get: () => i,
        set: (v) => {
          const n = Math.max(0, Math.min(names.length - 1, Math.round(v)));
          if (n === i) return;
          i = n;
          setSlot(partName, names[n]);
        },
      });
      slots.set(partName, s);
    }
    return slots.get(partName);
  }

  ready = true;
  update();

  return {
    bone: (name) => bones.get(name).state,
    bones,
    update,
    worldPoint,
    setSlot,
    slot,
  };
}
