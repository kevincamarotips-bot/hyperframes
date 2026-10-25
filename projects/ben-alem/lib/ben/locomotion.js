// Locomoção do Ben (vista de perfil) sobre o rig SVG.
//
// A fase do ciclo de corrida vem da distância percorrida (`x`), não do tempo:
// acelerando, freando ou em velocidade constante, a pata em contato fica parada
// no chão. As poses de pulo (`air`), freada (`brake`) e os acentos de atuação são
// pesos misturados por cima do ciclo. Tudo é função pura do estado do driver,
// então o seek do HyperFrames sempre reproduz o mesmo frame.

const TAU = Math.PI * 2;
const DEG = 180 / Math.PI;
const mix = (a, b, t) => a + (b - a) * t;

// fase de cada pata no ciclo: traseiras, depois dianteiras (galope curto)
const PAWS = [
  ["paw_back_a", 0.0],
  ["paw_back_b", 0.12],
  ["paw_front_a", 0.5],
  ["paw_front_b", 0.62],
];
const FLIGHT = { paw_back_a: 34, paw_back_b: 26, paw_front_a: -36, paw_front_b: -28 }; // patas esticadas no ar
const BRAKE = { paw_back_a: 6, paw_back_b: 10, paw_front_a: -30, paw_front_b: -22 }; // dianteiras fincadas

export function createLocomotion(rig, options = {}) {
  const o = {
    stride: 300, // distância por ciclo (unidades do SVG)
    duty: 0.3, // fração do ciclo com a pata no chão
    leg: 65, // pivô da pata → chão
    lift: 34, // altura da pata no balanço
    bob: 16, // quique do corpo (dois por ciclo)
    lean: 3, // corpo inclinado para frente na corrida (graus)
    speedLines: true, // traços de velocidade do livro atrás do Ben
    ...options,
  };
  // contato sem deslizar: o arco da pata cobre exatamente o que o corpo anda no contato
  const sinMax = Math.min(0.85, (o.duty * o.stride) / (2 * o.leg));
  const B = (n) => rig.bone(n);

  const values = {
    x: 0, // posição horizontal do Ben = distância percorrida
    run: 0, // 0 parado … 1 ciclo de corrida completo
    air: 0, // 0 no chão … 1 pose de voo
    brake: 0, // pose de freada
    jy: 0, // altura do pulo (para cima, positivo)
    sq: 1, // squash/stretch vertical ancorado no chão (volume preservado)
    pitch: 0, // inclinação extra do corpo (graus)
    head: 0, // rotação extra da cabeça
    ear: 0, // rotação extra das orelhas (negativo = para trás)
    tail: 0, // rotação extra da cauda
    look: 0, // pupilas: deslocamento horizontal
    lookY: 0, // pupilas: deslocamento vertical
  };
  const driver = {};
  for (const key of Object.keys(values)) {
    Object.defineProperty(driver, key, {
      enumerable: true,
      get: () => values[key],
      set: (v) => {
        if (values[key] === v) return;
        values[key] = v;
        apply();
      },
    });
  }

  function apply() {
    const v = values;
    const phase = v.x / o.stride;
    const a = v.run * (1 - v.air);
    const bounce = 0.5 - 0.5 * Math.cos(2 * TAU * phase);
    const bob = o.bob * a * bounce;

    rig.batch(() => {
      const root = B("root");
      root.x = v.x;
      root.y = -bob - v.jy;
      root.sy = v.sq;
      root.sx = 1 / v.sq;

      B("body").rot = o.lean * a + 2 * a * Math.sin(TAU * phase) - 5 * v.brake + v.pitch;

      for (const [name, offset] of PAWS) {
        const p = (((phase + offset) % 1) + 1) % 1;
        let rot;
        let y;
        if (p < o.duty) {
          rot = Math.asin(mix(-sinMax, sinMax, p / o.duty)) * DEG;
          y = bob; // compensa o quique: a pata segue no chão
        } else {
          const q = (p - o.duty) / (1 - o.duty);
          rot = Math.asin(sinMax) * DEG * Math.cos(Math.PI * q);
          y = bob - o.lift * Math.sin(Math.PI * q);
        }
        rot *= v.run;
        y *= v.run;
        rot = mix(rot, BRAKE[name], v.brake);
        rot = mix(rot, FLIGHT[name], v.air);
        y = mix(y, -10, v.air);
        const paw = B(name);
        paw.rot = rot;
        paw.y = y;
      }

      // cabeça e orelhas respondem ao quique com atraso (follow-through)
      const lag = 2 * TAU * phase - 0.9;
      const head = B("head");
      head.rot = -o.lean * 0.6 * a + 3 * a * Math.sin(lag) + v.head; // cabeça compensa a inclinação
      head.x = 10 * a;
      head.y = 5 * a * Math.sin(lag);
      B("ear_back").rot = -24 * a + 7 * a * Math.sin(lag - 0.7) + v.ear;
      B("ear_front").rot = -21 * a + 7 * a * Math.sin(lag - 1.1) + v.ear * 0.9;
      B("tail").rot = 16 * a + 10 * a * Math.sin(TAU * phase - 1.2) + v.tail;
      for (const eye of ["eye_back_pupil", "eye_front_pupil"]) {
        const pupil = B(eye);
        pupil.x = 12 * v.run + v.look;
        pupil.y = v.lookY;
      }
    });
    if (lines) drawSpeedLines(phase, v.run * (1 - v.air));
  }

  // Traços de velocidade como no livro: riscos curtos atrás do corpo, presos ao
  // osso raiz. Variam a cada meio ciclo (desenho “trocado”, não animado).
  let lines = null;
  if (o.speedLines) {
    const svg = rig.svg;
    const NS = "http://www.w3.org/2000/svg";
    lines = document.createElementNS(NS, "g");
    lines.setAttribute("data-part", "root");
    lines.setAttribute("fill", "none");
    lines.setAttribute("stroke", "#000");
    lines.setAttribute("stroke-width", "7");
    lines.setAttribute("stroke-linecap", "round");
    for (let i = 0; i < 5; i++) lines.appendChild(document.createElementNS(NS, "path"));
    svg.insertBefore(lines, svg.firstChild);
    rig.register(lines);
  }
  const ROWS = [470, 540, 610, 680, 745];
  function drawSpeedLines(phase, strength) {
    lines.setAttribute("opacity", Math.min(1, strength * 1.4).toFixed(3));
    const step = Math.floor(phase * 2);
    [...lines.children].forEach((path, i) => {
      // pseudo-aleatório determinístico por (traço, meio ciclo)
      const r = Math.abs(Math.sin((step + 1) * 12.9898 + i * 78.233) * 43758.5453) % 1;
      const r2 = Math.abs(Math.sin((step + 1) * 4.1414 + i * 19.19) * 24634.6345) % 1;
      const x1 = 120 - 40 * r - 30 * (i % 2);
      const len = (90 + 150 * r2) * strength;
      const y = ROWS[i] + 10 * (r - 0.5);
      const d = "M" + x1 + "," + y + " q" + -len / 2 + "," + (-6 + 12 * r) + " " + -len + ",0";
      path.setAttribute("d", strength > 0.02 && r2 > 0.15 ? d : "");
    });
  }

  apply();
  return { driver, speed: (cycleSeconds) => o.stride / cycleSeconds, options: o };
}

/**
 * Ease para `tweenFromTo` que mantém o personagem em ones até `onesUntil` e em
 * twos (degraus de 1/15 s) depois — ações rápidas em ones, atuação em twos.
 */
export function exposureEase(duration, onesUntil, fps = 15) {
  return (p) => {
    const t = p * duration;
    if (t <= onesUntil) return p;
    // nunca volta antes do ponto de troca: o primeiro degrau de twos parte dele
    return Math.min(1, Math.max(onesUntil, Math.floor(t * fps + 1e-6) / fps) / duration);
  };
}
