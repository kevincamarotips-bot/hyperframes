# Ben em SVG com partes separadas para o rig (v0.1)

Decisão do cliente: os personagens são recriados em SVG a partir das imagens do PDF de prova, já separados em partes para animação. Este documento cobre o Ben de perfil, a vista principal. Os outros personagens e vistas vêm depois da aprovação deste.

## Como o SVG é gerado

`tools/build_ben_svg.py` parte da maior pose de perfil do livro (página 6, a da régua; 1398 × 972 px).

1. Classifica cada pixel em preto, branco ou fundo, com a imagem ampliada 2× para curvas mais suaves.
2. Recorta as regiões de cada parte e **estende as áreas que o desenho esconde**: base das orelhas, raiz da cauda, topo das patas, pescoço e o branco sob as pinceladas pretas. Sem isso, girar uma parte abriria buraco.
3. Traça cada parte com potrace, o que preserva a borda de pincel seco do desenho original.
4. Os olhos são elipses ajustadas ao arco do desenho. **As pupilas são círculos independentes**, para o olhar se mover. As expressões de olho (feliz ∩, fechado reto, coração) são slots.
5. Grava `ben-side.svg` (pose de repouso, um `<g data-part>` por parte) e `ben-side.rig.json` (ossos, pivôs, hierarquia, ordem de desenho e slots).

**Fidelidade medida** (render do SVG comparado com a imagem do livro, pixel a pixel): preto 99,4%, branco 98,6% e fundo 99,7% de coincidência (IoU). Só 0,24% dos pixels diferem de classe, quase todos em bordas antialiasadas.

## Partes, ossos e ordem de desenho

```
root (chão) ─ body ─┬─ tail
                    ├─ paw_back_a · paw_back_b · paw_front_a · paw_front_b
                    └─ head ─┬─ ear_back · ear_front
                             ├─ eye_back ─ eye_back_pupil
                             ├─ eye_front ─ eye_front_pupil
                             └─ nose
```

Ordem de desenho (de trás para frente): `tail`, 4 patas, `body_white`, `head`, `body_black`, `scalp`, `ear_back`, `ear_front`, `eye_back`, `eye_front`.

- `body_white` e `body_black` seguem o mesmo osso. O preto do corpo fica **por cima** da cabeça porque as pinceladas da sela avançam sobre o rosto no desenho original.
- `scalp` é pelo preto atrás da base das orelhas, preso à cabeça. Quando a orelha gira, aparece pelo, não céu.
- Nas juntas, a parte da frente passa alguns pixels por cima da vizinha, o que elimina a fresta de antialiasing entre peças.

## Motor de rig

`lib/rig/svg-rig.js`: cada osso tem um estado animável `{ x, y, rot, sx, sy }` no espaço do pai. O rig compõe as matrizes de mundo e escreve o `transform` de cada parte. A hierarquia de ossos é independente da ordem de desenho.

- Os canais reescrevem os transforms no momento da atribuição, porque o HyperFrames faz seek no GSAP com callbacks suprimidos (`onUpdate` não dispara durante o render).
- Slots são canais numéricos (`tl.set(rig.slot("eye_back"), { i: 2 }, t)`), também seguros para seek.
- **Twos:** a timeline do personagem fica pausada e é percorrida pela raiz com `ease: steps(n)`, em degraus de 1/15 s.

## Teste de articulações (não é cena)

`lab/ben-rig-test/index.template.html` exercita, em 5 s: respiração, olhar (olhos antes da cabeça, orelhas atrasando), piscada, cauda abanando, antecipação, pulo, aterrissagem com squash e recuperação elástica, e olhos felizes no fim. As amplitudes ficam acima do uso normal, para expor buracos. `tools/make_lab.py` embute o SVG e o rig no template.

Resultado: `hyperframes lint` sem erros, render a 30 fps. Snapshots e folha explodida revisados. Três defeitos achados e corrigidos: crescente de céu na borda do olho ao girar a orelha, lasca preta da cauda ao abanar e lascas no topo das patas.

## Limitações conhecidas

- **Squash/stretch ainda é escala do osso inteiro** (com volume preservado). A deformação localizada do tronco, como a flexão de coluna e a compressão só embaixo, é a próxima etapa: deformação dos pontos dos paths por lattice.
- **Orelhas giradas além de ~25°** mostram o recorte reto do `scalp`. Para dobras maiores, a orelha precisa de dois segmentos (base e ponta) com deformação de path.
- **Viradas (frontal, 3/4, costas) e poses extremas** não saem desta vista. São desenhos novos em SVG, feitos a partir das outras poses do livro, usando a mesma ferramenta.
- As **pupilas** são círculos perfeitos; no livro elas são levemente irregulares.

## Arte não versionada

O repositório é público. O SVG e o `rig.json` gerados a partir da arte do livro **não** são versionados; só as ferramentas e o motor. Para gerar:

```bash
python tools/build_ben_svg.py <ben-pose.png> <saida>   # ben-pose.png: ver lab/spike-raster-mesh/README.md
python tools/make_lab.py <saida> <saida>/lab
npx hyperframes snapshot <saida>/lab --at 0,1,2.84,3.53
```
