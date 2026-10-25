# Ben Além: especificação técnica de animação (v0.1, para aprovação)

Documento de implementação da etapa 20 da _Animation Motion Bible_. **Nenhuma cena do livro foi produzida.** O que existe é um teste técnico isolado (seção 3.3), feito com uma pose extraída do PDF de prova para confirmar que a abordagem proposta funciona no pipeline de render do HyperFrames.

---

## 0. Resumo executivo

1. **Descoberta principal:** no PDF `AF-BEN-ALEM-SeloP`, Ben e todos os personagens são **bitmaps achatados, um por pose**, em dois tons (preto/branco) com canal alfa e textura de pincel seco. Não são vetores. Fundos, objetos de cena (pula-pula, rede, linhas de movimento) e tipografia (fonte _SketchnoteText_) são vetoriais. A resolução dos bitmaps no PDF é de 100 ppi. Ben ocupa de 300 a 1.400 px de largura, o que é insuficiente para vídeo.
2. **Consequência:** “animar os vetores do Illustrator” não se aplica ao Ben. Para preservar o desenho e a textura, a arquitetura recomendada é um **rig de recorte (cut-out) raster com deformação em malha, renderizado em WebGL dentro do HyperFrames, combinado com substituição de desenhos** para viradas, expressões e poses extremas. É o modelo de produção de séries infantis em Toon Boom Harmony ou Spine, implementado em código.
3. **Viabilidade confirmada na prática:** num teste de 3 s renderizado pelo CLI do repositório, consegui (a) deformação em malha localizada sobre o bitmap do Ben (squash/stretch com volume preservado, arco de coluna, orelhas dobrando), (b) poses do personagem em _twos_ enquanto outros elementos correm em _ones_, (c) o `MorphSVGPlugin` do GSAP renderizando corretamente e (d) onion skin e diferença entre frames como ferramentas de revisão.
4. **Bloqueio:** para construir o Ben é preciso o **arquivo-fonte em camadas** (PSD, Procreate ou equivalente, em alta resolução) e **desenhos complementares** do ilustrador: áreas ocultas repintadas, vistas e expressões. A seção 5 traz a lista exata.
5. **Decisões que peço para aprovar:** seção 10.

---

## 1. Como li a Motion Bible

Converti os princípios em **regras verificáveis**. “Está fluido” não pode ser o critério de aceite. Cada regra abaixo tem um teste correspondente na seção 7.

| Princípio da Bible                    | Regra operacional neste projeto                                                                                                                         | Como é verificada                                           |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| Squash & stretch com volume           | `sx · sy ≈ 1` (tolerância ±4%) em toda deformação do tronco; deformação localizada por região, nunca `scale` no personagem inteiro                       | Telemetria do rig: área da malha por frame                  |
| Antecipação                           | Toda ação com deslocamento maior que 15% da altura do Ben tem pose de antecipação de pelo menos 4 frames no sentido oposto                               | Curva do centro de massa: sinal invertido antes do impulso  |
| Slow in / slow out                    | Nenhum canal do corpo com velocidade constante por mais de 8 frames, salvo deslocamento de câmera ou ciclo intencional                                   | 2ª derivada ≈ 0 em janelas longas é sinalizada              |
| Arcos                                 | Cabeça, focinho, ponta da cauda e ponta das orelhas seguem trajetórias curvas em ações acima de 6 frames                                                 | Rastro de pontos (arc trail) plotado sobre onion skin       |
| Follow-through / overlap              | Orelhas e cauda nunca começam nem terminam no mesmo frame que o tronco: atraso de 2 a 4 frames e assentamento de 8 a 20 frames                           | Detector de “partida simultânea” por canal                  |
| Ação secundária                       | Olhos antecipam a cabeça em 2 a 4 frames; secundários dependem do estado emocional (seção 6.7)                                                           | Revisão de lista + telemetria de offset                     |
| Patas sem deslizar                    | Pata em fase de contato: deslocamento em X no mundo ≤ 1 px por frame                                                                                     | Detector de foot-slide                                      |
| Continuidade entre estados            | Transições preservam posição, orientação e velocidade (sem “pop”)                                                                                        | Pico de pixels alterados entre frames consecutivos          |
| Física cartoon consistente            | Uma única constante de gravidade por “mundo” (Terra, sonho, Lua) e regras de suspensão no ápice                                                          | Ajuste parabólico da curva vertical                         |

A pergunta da seção 7 da Bible (_o que o personagem deseja, sente, nota, como reage, como o corpo expressa_) vira um campo obrigatório do roteiro de cada plano: o **beat sheet de atuação** (seção 7.1). Nenhum plano é animado sem ele.

---

## 2. Diagnóstico do material recebido

Arquivos recebidos: duas cópias **idênticas** (mesmo SHA-256) de `AF-BEN-ALEM-SeloP.pdf`. São 22 páginas, exportadas do Adobe Illustrator 25.2 em 2021, com spread de 1162 × 780 pt (proporção 3:2). O PDF **não** preserva os dados editáveis do Illustrator (não há `AIPrivateData`).

### 2.1 Natureza das imagens (verificado com `pdfimages` e `pdftocairo`)

| Elemento                                                | Formato no PDF                                                  | Observação                                                                                         |
| ------------------------------------------------------- | --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Ben (todas as poses)                                    | Bitmap indexado + máscara suave, ~100 ppi, 300 a 1.400 px de largura | Na prática são 2 cores (preto puro e branco puro); toda a textura de pincel está na borda do alfa e na fronteira preto/branco |
| Outros personagens (preguiças, elefante, galinha etc.)   | Bitmaps RGB/indexados com máscara                               | Mais “chapados”, menos textura que o Ben                                                            |
| Lua                                                     | Bitmap foto-realista 1567 × 1483                                | Elemento de outra natureza (textura fotográfica)                                                   |
| Fundos, pula-pula, rede, linhas de movimento, balões de texto | **Vetor**                                                  | Fáceis de reconstruir ou exportar como SVG                                                         |
| Texto                                                   | Fonte _SketchnoteText_ e _SketchnoteText-Italic_ (embutidas)    | Verificar a licença para uso em vídeo                                                             |

### 2.2 Implicações

- **Resolução:** o Ben do PDF é cerca de 4 a 8 vezes menor que o necessário (seção 5.4). É preciso o original.
- **Ben não tem partes separadas.** Cada pose é um desenho único. Mover uma orelha deforma tudo o que estiver na mesma região. O teste da seção 3.3 mostra isso: ao dobrar as orelhas, os olhos foram arrastados junto.
- **Áreas ocultas não existem:** por exemplo, o pescoço sob a cabeça, a base da orelha de trás e as patas atrás do corpo.
- **O livro já é uma folha de poses valiosa.** Catalogo cerca de 25 desenhos distintos do Ben: perfil neutro; corrida com olhos de coração; corrida feliz (olhos fechados); preparação e salto com dentes cerrados; giro no ar; silhueta azul (sonho); “PLOFT” (olhos amassados, focinho sanfonado); close frontal; voo de barriga para baixo; voo invertido; mergulho; “pisou na Lua”; amizade. Eles servem de chaves de pose e de modelo para os desenhos complementares.
- **Proporção:** spreads em 3:2 e vídeo em 16:9. Como os fundos são chapados e vetoriais, a extensão lateral é simples; os enquadramentos serão recompostos plano a plano.
- **Cor:** o livro foi feito para impressão (CMYK). Peço um master RGB, ou converto com perfil e valido os swatches, por exemplo o azul-ciano de fundo ≈ `#009FE3`.

---

## 3. Viabilidade técnica no HyperFrames (verificada, não suposta)

### 3.1 Recursos confirmados no repositório (v0.8.163)

| Necessidade                       | Recurso                                                                                                                                       | Status          | Evidência                                                                                      |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | --------------- | ---------------------------------------------------------------------------------------------- |
| Timeline, keyframes, easing       | GSAP 3.15 (adaptador `gsap`, timeline raiz pausada em `window.__timelines`)                                                                    | ✅              | `packages/core/src/runtime/adapters/gsap.ts`, `gsapCdn.ts`                                     |
| Easings customizados              | `CustomEase` cúbico, spring e wiggle reconhecidos pelo runtime                                                                                  | ✅              | `runtime/customEase.ts`, `parsers/springEase`, `runtime/wiggleEase.ts`                         |
| Interpolação de forma SVG         | `MorphSVGPlugin` (CDN jsDelivr, mesma versão do GSAP)                                                                                          | ✅ testado      | Teste da seção 3.3 (orelha vetorial dobrando)                                                  |
| Trajetórias                       | `MotionPathPlugin`                                                                                                                            | ✅              | `gsapCdn.ts → motionPathPluginUrl()`                                                           |
| Deformação em malha de bitmap     | Three.js via adaptador `three` (evento `hf-seek` com o tempo exato do frame)                                                                    | ✅ testado      | Teste da seção 3.3                                                                             |
| Lottie / dotLottie                | Adaptador `lottie` (seek por `goToAndStop`)                                                                                                   | ✅ disponível   | `runtime/adapters/lottie.ts`. Ressalva: o Puppet do After Effects **não** exporta para Lottie |
| Taxa de quadros                   | 24, 30, 60, NTSC (`30000/1001`) etc.                                                                                                          | ✅              | `parseFps.test.ts`; render com `--fps 30` validado                                             |
| Prévia e QA                       | `lint`, `check`, `snapshot --at` (gera contact sheet), `keyframes --shot / --layout strip / --ghost`, `render --quality draft/looks/delivery`   | ✅ usados       | Teste da seção 3.3                                                                             |
| Determinismo                      | Sem `Date.now()`, sem `Math.random()` sem seed, sem fetch durante o render                                                                     | regra           | `CLAUDE.md`, skill `hyperframes-keyframes`                                                     |

Não existe no HyperFrames um sistema pronto de rig, ossos ou skinning para personagens. **Ele precisa ser construído** (seção 4). É a maior parte do trabalho técnico.

### 3.2 Combinação de adaptadores

A arquitetura usa ao mesmo tempo o adaptador `gsap` (DOM, SVG, câmera) e o `three` (personagens em WebGL). O teste confirmou que os dois são acionados no mesmo frame durante o render. A captura reportou `beginframe capture · software gpu`, o caminho determinístico.

### 3.3 Teste técnico executado (não é cena)

- **Conteúdo:** uma única pose de perfil do Ben extraída do PDF (página 6, a da régua; 1398 × 972 px), aplicada como textura num plano subdividido de 48 × 32 quadrados. O plano recebe três deformadores sobre a imagem inteira: squash/stretch ancorado nas patas com volume preservado, arco de coluna e rotação da região das orelhas com peso crescente da base à ponta. A ação é um pulo curto com antecipação, impulso, ápice, queda, impacto e recuperação elástica. Ao lado há uma orelha vetorial testando o MorphSVG.
- **Exposição:** os parâmetros do Ben ficam numa timeline própria, amostrada em _twos_ (15 poses/s); a orelha vetorial fica em _ones_ (30/s).
- **Render:** 1280 × 720, 30 fps, 90 frames em 9,6 s (captura 7,4 s).
- **Resultados medidos (diferença de pixels entre frames consecutivos):**
  - Ben muda **apenas nos frames pares** (padrão `0 / N / 0 / N…`). Os _twos_ funcionam.
  - A orelha vetorial muda **todo frame**. _Ones_ e _twos_ convivem na mesma cena.
  - No frame 18 (decolagem `expo.out` em 0,17 s, amostrada em _twos_), mais de 219 mil pixels mudaram de uma vez. Esse salto lê como “pop”. Disso sai a **regra da seção 6.2: ações rápidas e impactos em _ones_**.
  - Ao girar a região das orelhas, **os olhos foram arrastados junto**. A pose inteira como um bitmap só não é suficiente, e isso prova a necessidade de separar as partes (seção 5).
  - O onion skin dos frames 9 a 51 mostra o arco do pulo e o espaçamento comprimindo no ápice: a ferramenta de revisão funciona.
- **Fonte do teste:** `projects/ben-alem/lab/spike-raster-mesh/` (a imagem do livro não é versionada; veja o README da pasta).

---

## 4. Arquitetura de animação proposta

### 4.1 Escolha da técnica de personagem

| Opção                                                                  | Fidelidade ao desenho                                | Expressividade                                   | Esforço                                   | Veredito                                         |
| ---------------------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------ | ----------------------------------------- | ------------------------------------------------ |
| **A. Cut-out raster + malha WebGL + substituição de desenhos**         | **Total**: o próprio bitmap do ilustrador             | Alta: deformação localizada, ossos, troca de desenho | Médio-alto (motor de rig próprio)       | **Recomendada**                                  |
| B. Vetorizar o bitmap (potrace) e animar em SVG                        | Boa, mas o pincel vira centenas de nós e perde finura | Baixa: MorphSVG entre traços complexos gera “derretimento” | Médio                            | Só para objetos simples                          |
| C. Lottie (After Effects + Duik/Rubberhose)                            | Boa em vetor                                         | Sem puppet/mesh no Lottie                        | Médio, e exige animador em AE             | Útil para objetos (hélice, luzes do disco)       |
| D. Spine ou Rive (editor externo + runtime web)                        | Total                                                | Muito alta (malhas, IK)                          | Licença (Spine Pro) e animador humano no editor; runtime fora dos adaptadores oficiais | Alternativa se entrar um animador humano |
| E. Quadro a quadro pelo ilustrador                                     | Total                                                | Máxima                                           | Altíssimo (milhares de desenhos)          | Inviável como base; usado pontualmente (smears, giros) |

A opção A preserva a textura de pincel, que é a identidade do Ben, e ainda permite deformação real em vez de `scaleX/scaleY` global. Isso atende diretamente à seção 10 da Bible.

### 4.2 Camadas do sistema

```
┌───────────────────────────────────────────────────────────────────────┐
│ 8. Cena HyperFrames (composição por plano, sub-composições, áudio)    │
├───────────────────────────────────────────────────────────────────────┤
│ 7. Câmera 2D (mundo com planos de paralaxe; pan/tilt/zoom/track/hold) │
├───────────────────────────────────────────────────────────────────────┤
│ 6. Exposição (ones/twos por grupo de canais, amostragem por frame)    │
├───────────────────────────────────────────────────────────────────────┤
│ 5. Secundários (molas determinísticas: orelhas, cauda, respiração)    │
├───────────────────────────────────────────────────────────────────────┤
│ 4. Biblioteca de movimentos (benWalk, benJump… → timelines GSAP)      │
├───────────────────────────────────────────────────────────────────────┤
│ 3. Controladores do Ben (parâmetros de alto nível, expressões)        │
├───────────────────────────────────────────────────────────────────────┤
│ 2. Motor de rig (esqueleto, malhas, skinning, lattice, slots)         │
├───────────────────────────────────────────────────────────────────────┤
│ 1. Assets (partes PNG/WebP + rig.json: pivôs, malhas, pesos, ordem)   │
└───────────────────────────────────────────────────────────────────────┘
```

**1. Assets.** São PNGs RGBA das partes e um `rig.json` que descreve a hierarquia de ossos, os pivôs (extraídos da camada `PIVOTS` do arquivo-fonte), a malha de cada parte (grade ou triangulação pela silhueta), os pesos de skinning, os slots de substituição e a ordem de desenho. O `rig.json` é gerado por script a partir dos arquivos exportados e pode ser editado à mão.

**2. Motor de rig (WebGL / Three.js).**

- _Esqueleto_ hierárquico 2D: cada osso tem posição, rotação, escala e cisalhamento locais.
- _Skinning_ linear: cada vértice da malha recebe até 3 ossos com pesos, gerados automaticamente por distância geodésica e retocados à mão.
- _Deformadores_ aplicados após o skinning: **lattice FFD 4 × 3** no tronco (squash/stretch localizado com volume preservado), **bend** ao longo da coluna e **taper** nas orelhas.
- _Slots_ de substituição: cada slot tem desenhos alternativos (olhos abertos, fechados, coração, amassados; vista de perfil, frontal, 3/4) trocados em frames exatos.
- _Ordem de desenho_ dinâmica, para quando uma orelha passa atrás da cabeça.
- Renderização com alfa pré-multiplicado e mipmaps, para não gerar halo na borda do pincel.

**3. Controladores do Ben.** Um único objeto de parâmetros animáveis pelo GSAP; o rig traduz cada parâmetro em ossos e deformadores:

```
ben.root.x/y/rot          ben.body.squash   ben.body.bend   ben.body.lean
ben.head.rot/tilt/push    ben.look.x/y      ben.eyes.state  ben.eyes.blink
ben.earL/earR.angle/flop/droop               ben.tail.angle/curl/wag
ben.pawFL/FR/BL/BR.lift/phase                ben.mouth.state  ben.view
ben.emotion  (estado que modula os secundários, seção 6.7)
```

**4. Biblioteca de movimentos.** São funções puras que recebem parâmetros e devolvem uma timeline GSAP sobre o objeto de controladores, sem efeito colateral e sem tempo de relógio. Os nomes são convenções deste projeto, não APIs existentes:

```js
benIdle({ duration, emotion, breath = 0.3 })
benWalk({ from, to, speed, cycleFrames = 12 })      // passos calculados a partir da distância
benRun({ from, to, cycleFrames = 8, effort })
benStop({ overshoot = 0.15 })
benTurn({ to: "left" | "right" })
benLookAt({ target, leadFrames = 3, headFollow = 0.7 })
benAnticipateJump({ depth, frames })
benJump({ height, distance, hang, world = "earth" })
benFall({ fromHeight })
benLand({ impact })                                  // escolhe squash e duração pela velocidade de chegada
benRecover({ wobble })
benReact({ kind: "surprise" | "frustration" | "joy" | "wonder", intensity })
benBlink({ at, kind: "normal" | "slow" | "double" })
```

Cada função devolve também **metadados de estado final** (posição, orientação, velocidade, pose), consumidos pela função seguinte para garantir continuidade (seção 8.5).

**5. Secundários determinísticos.** Orelhas, cauda e pequenas massas usam molas amortecidas cuja entrada é a aceleração do osso pai. Para manter o seek determinístico em qualquer ordem, a simulação roda em **passo fixo de 1/240 s a partir do início do plano**, com cache por frame: o mesmo tempo sempre dá o mesmo resultado. As piscadas usam PRNG com seed fixa por plano (mulberry32), nunca `Math.random()`.

**6. Exposição.** A timeline do personagem é amostrada em tempo quantizado (`floor(t · 15) / 15` para _twos_), com regras por grupo de canais (seção 6.2). Translação durante tracking de câmera fica em _ones_ para não tremer contra o fundo.

**7. Câmera.** É um contêiner de mundo com planos de profundidade (fundo, meio, personagens, primeiro plano). Pan, tilt e zoom aplicam paralaxe por plano. A câmera sempre fica em _ones_. Na subida vertical (do pula-pula à Lua), o tilt acompanha o Ben com atraso controlado e o céu troca de cor por camadas.

**8. Cena.** Uma composição HyperFrames por plano, com `data-composition-id` próprio, montada numa composição-mestre. A timeline GSAP raiz controla DOM, SVG e câmera; o canvas dos personagens escuta `hf-seek`.

### 4.3 Estrutura de pastas proposta

```
projects/ben-alem/
  docs/                      # este documento, beat sheets, folhas de timing
  source/                    # (não versionado) originais do ilustrador
  assets/characters/ben/     # partes exportadas + rig.json
  assets/characters/<npc>/
  assets/sets/<cena>/        # SVGs dos cenários
  lib/rig/                   # motor: skeleton, mesh, skinning, lattice, slots, renderer
  lib/ben/                   # controladores, expressões, motions/*.js
  lib/physics/               # molas determinísticas, gravidade por "mundo"
  lib/camera/                # rig de câmera e paralaxe
  lib/timing/                # eases nomeados, exposição, PRNG
  tools/                     # export de partes → rig.json, telemetria/QA, onion skin, gráficos de curva
  lab/                       # testes de movimento (folhas de teste, não cenas)
  scenes/                    # (etapa futura)
```

---

## 5. Preparação dos arquivos do ilustrador

### 5.1 O que pedir primeiro

1. **O arquivo `.ai` original** e, sobretudo, **os arquivos de pintura de origem do Ben** (PSD, Procreate, Krita…) **em camadas e na resolução nativa**. Se o `.ai` só contém os bitmaps incorporados, a resolução deles determina o teto de qualidade.
2. Confirmar como o Ben foi desenhado (pincel raster em Photoshop ou Procreate, ou pincel vetorial rasterizado). Isso decide se novos desenhos podem ser feitos no mesmo pincel.
3. Licença da fonte _SketchnoteText_ para vídeo, caso o texto do livro apareça em tela.

### 5.2 Separação do Ben em partes (vista de perfil, principal)

| Parte                       | Pivô (anatomia)                         | Notas de preparação                                                                                                       |
| --------------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `torso`                     | Centro de massa (entre as patas)        | Silhueta inteira do corpo, preto e branco. **Repintar** a área sob a cabeça e sob a cauda                                  |
| `head`                      | Base do pescoço                         | Máscara branca do focinho e da face; **sem** olhos nem orelhas. Repintar a borda que encosta no torso com sobra de ~40 px  |
| `snoutTip`                  | Base da ponta preta                     | Ponta preta do focinho separada (pequenas reações)                                                                       |
| `earFront`, `earBack`       | Base de cada orelha                     | Inteiras, inclusive o trecho hoje escondido atrás dos olhos e da cabeça                                                   |
| `eyeFront`, `eyeBack`       | Centro do círculo                       | Círculo branco. **As pupilas são desenhadas proceduralmente** (círculos pretos), para o olhar se mover livremente         |
| Variações de olho (slots)   | idem                                    | Fechado feliz (∩), fechado neutro, coração, amassado (PLOFT), arregalado, semicerrado                                     |
| `mouth` (slot)              | Canto da boca                           | Sorriso de linha, dentes cerrados (esforço), boca aberta (surpresa)                                                       |
| `tail`                      | Base da cauda                           | Inteira, com a ponta branca. Será malha com cadeia de 4 ossos                                                             |
| `pawFL/FR/BL/BR`            | Topo da pata (encaixe sob o torso)      | Os quatro “ovais” brancos separados; os de trás são repintados inteiros                                                   |
| `furTufts` (opcional)       | —                                       | Tufos sobrepostos para esconder emendas nas articulações                                                                  |
| `motionLines` (biblioteca)  | —                                       | Traços de velocidade e tremor no estilo do livro, para efeitos                                                            |

**Regras de pintura:** cada parte com sobra repintada (overlap) onde encosta em outra; as bordas internas de emenda feitas com o mesmo pincel, para a junta não aparecer quando a peça gira até ~25°; sem sombras ou contornos novos; mesmas duas cores.

### 5.3 Desenhos complementares (substituição)

Estimo de 40 a 60 desenhos adicionais do Ben ao longo do curta. Mínimo para a biblioteca da seção 8:

- **Vistas:** perfil direita (base), frontal (há um close no livro), 3/4 frente, 3/4 costas e “de barriga” para voo e giros. A vista esquerda é espelhada; o livro já faz isso.
- **Cabeça em virada:** 2 intermediários entre perfil e frente.
- **Poses extremas de ação:** agachamento de salto, extensão máxima, enrolado no ar (giro), queda de cabeça, aterrissagem esparramada.
- **Smears:** 2 a 3 frames de borrão para giros e arrancadas.
- **Expressões completas de rosto:** curiosidade, frustração, surpresa, alegria, encantamento, concentração.

### 5.4 Especificação de exportação

- **Resolução-alvo de entrega:** 1920 × 1080 (16:9), 30 fps. Para o maior enquadramento do livro (a página da régua) com zoom de câmera de até 1,5×, a largura do Ben deve ser de **≥ 2.600 px** nos assets. Para entrega em 4K, dobrar.
- **Formato:** PNG RGBA 8 bits, sRGB, uma prancheta por parte, recorte justo com 16 px de margem transparente.
- **Nomes:** `ben_<vista>_<parte>[_<variante>].png`, por exemplo `ben_side_earFront.png` e `ben_side_eye_heart.png`.
- **Pivôs:** camada `PIVOTS` com pequenos círculos nomeados (`pivot_earFront`…). O script de importação lê essas posições.
- **Cenários:** exportar do Illustrator como **SVG** (atributos de apresentação, IDs a partir dos nomes de camada, texto convertido em contorno ou com fonte licenciada), uma camada por elemento animável (rede, elástico laranja, nuvens, balões, sol).
- **Personagens secundários:** separação leve, só do que se move na cena (braços das preguiças, tromba do elefante, asa da galinha, hélice do avião, chamas do foguete).

---

## 6. Padrões de timing, easing, spacing e deformação

Referência: **30 fps**. Os números são pontos de partida, ajustados na revisão.

### 6.1 Folha de timing do Ben (frames a 30 fps)

| Ação                               | Antecipação | Ação principal                | Hold / ápice | Assentamento | Observação                                          |
| ---------------------------------- | ----------- | ----------------------------- | ------------ | ------------ | --------------------------------------------------- |
| Piscada normal                     | —           | fecha 2f, fechado 1f          | —            | abre 3f      | Intervalo de 2 a 6 s, aleatório com seed            |
| Piscada lenta (encantamento)       | —           | fecha 4f, fechado 4f          | —            | abre 6f      |                                                     |
| Olhar (`benLookAt`)                | —           | olhos 3f → cabeça 6–10f       | —            | orelhas 6–10f | Olhos lideram em 2–4f                              |
| Caminhada (ciclo completo)         | —           | 12f por ciclo                 | —            | parada 6–8f  | Patas curtas pedem passos rápidos                  |
| Corrida                            | 4f          | 8f por ciclo                  | —            | parada 8–12f | “Patinhas rápidas” do livro: 6f                    |
| Salto curto (fracasso)             | 6–8f        | impulso 3f, voo 10–12f        | 2f           | 6–10f        | Altura baixa e voo curto contam a dificuldade      |
| Salto alto (pula-pula)             | 8–12f       | impulso 3–4f, voo 30–45f      | 6–10f        | —            | Encadeia com o próximo quique                      |
| Surpresa (take)                    | 4f abaixa   | 3f estica                     | 6–12f        | 8f           |                                                     |
| Impacto (PLOFT)                    | —           | 1–2f de contato               | 4–6f amassado | 10–14f      | Squash extremo + tremor de 3 ciclos                 |

### 6.2 Exposição: ones e twos

| Situação                                                            | Exposição |
| ------------------------------------------------------------------- | --------- |
| Atuação, poses, expressões, ciclos de caminhada                     | **Twos**  |
| Ações rápidas: impulso, impacto, arrancada, smear (≤ 6f)             | **Ones**  |
| Translação do personagem enquanto a câmera faz tracking             | **Ones**  |
| Câmera, paralaxe, objetos em voo (disco, bola, foguete)             | **Ones**  |
| Secundários (orelhas, cauda) durante holds                          | Twos      |

A troca de exposição é declarada por intervalo de tempo no plano e aplicada pelo amostrador (camada 6). O teste da seção 3.3 mostrou o “pop” de uma decolagem rápida em _twos_; essa tabela evita esse problema.

### 6.3 Vocabulário de easing (nomes do projeto → curva GSAP)

| Nome            | Curva                         | Uso                                                       |
| --------------- | ----------------------------- | --------------------------------------------------------- |
| `antic`         | `power2.in`                   | Descida da antecipação (acumula energia)                  |
| `snap`          | `expo.out`                    | Impulso, take de surpresa, virada rápida de cabeça        |
| `rise`          | `power2.out`                  | Subida até o ápice (desacelera contra a gravidade)        |
| `fall`          | `power2.in`                   | Queda (acelera com a gravidade)                           |
| `hang`          | `sine.inOut`                  | Suspensão estilizada no ápice                             |
| `settle`        | `back.out(1.4)`               | Chegada a uma pose com pequena sobra                      |
| `wobble`        | `elastic.out(1, 0.4)`         | Recuperação do corpo após impacto                         |
| `flop`          | `elastic.out(1, 0.3)`         | Orelhas e cauda (mais soltas que o corpo)                 |
| `drift`         | `sine.inOut`                  | Balões, paraquedas, flutuação no espaço                   |
| `linear`        | `none`                        | Apenas deslocamento em trajetória e ciclos                |

Regra: **um mesmo plano não usa a mesma curva em todos os elementos.** O corpo usa `antic`/`snap`/`settle`, os apêndices usam `flop` e o ambiente usa `drift`.

### 6.4 Spacing e física cartoon

- **Gravidade:** queda com deslocamento ∝ t² (`fall`); subida espelhada (`rise`). Constantes por mundo: **Terra** (normal), **sonho/céu** (gravidade 0,6× e ápices mais longos) e **Lua** (0,3×, com quiques lentos).
- **Suspensão:** no ápice de momentos de encantamento, 6 a 10 frames de `hang` com micro-deriva vertical de ≤ 2% da altura do Ben.
- **Impacto:** a duração do squash vem da velocidade de chegada (mais rápido = mais curto e mais forte).
- **Ciclos de passo:** fases _contact → down → passing → up_ adaptadas a quadrúpede (diagonais alternadas). A velocidade de translação é calculada a partir do comprimento do passo e da duração do ciclo, nunca o contrário. Isso evita deslizamento.

### 6.5 Limites de deformação (preservam a identidade)

| Canal                      | Normal          | Extremo (impacto, impulso máximo) |
| -------------------------- | --------------- | --------------------------------- |
| Tronco, eixo vertical      | 0,85 – 1,15     | 0,70 – 1,30                       |
| Volume (`sx · sy`)         | 1 ± 0,04        | 1 ± 0,06                          |
| Arco da coluna             | ±4% da altura   | ±7%                               |
| Orelhas (dobra da ponta)   | até 25°         | até 45°                           |
| Cauda (curvatura)          | até 60° total   | até 110°                          |
| Estiramento de textura     | ≤ 20%           | ≤ 30% (só em 1–2 frames)          |

Olhos e pupilas **não deformam**: eles se movem e trocam de desenho, porque deformá-los destrói a leitura do personagem.

### 6.6 Overlap

| Elo                          | Atraso em relação ao pai | Assentamento |
| ---------------------------- | ------------------------ | ------------ |
| Olhos → cabeça               | −2 a −4f (olhos lideram) | —            |
| Cabeça → tronco              | +1 a +2f                 | 4–6f         |
| Orelhas (base → ponta)       | +2f por segmento         | 8–14f        |
| Cauda (4 segmentos)          | +1 a +2f por segmento    | 10–20f       |

### 6.7 Secundários por estado emocional

| Estado        | Respiração | Piscadas        | Orelhas             | Cauda                 |
| ------------- | ---------- | --------------- | ------------------- | --------------------- |
| Neutro        | sutil      | 3–5 s           | eretas, pouca mola  | quase parada          |
| Curiosidade   | contida    | 4–6 s (foco)    | giram para o alvo   | leve abano lento      |
| Alegria       | rápida     | 2–3 s           | soltas, muita mola  | abano rápido          |
| Frustração    | pesada     | lenta, longa    | caídas (`droop`)    | baixa, parada         |
| Surpresa      | prende     | nenhuma no take | disparam para cima  | rígida                |
| Encantamento  | lenta      | lenta           | relaxadas           | ondulação lenta       |
| Concentração  | prende     | nenhuma         | apontadas à frente  | rígida                |

Nenhum secundário roda em “loop decorativo”. Todos respondem a uma causa: aceleração do corpo, estado emocional ou estímulo.

---

## 7. Processo de revisão visual

### 7.1 Antes de animar

Beat sheet de atuação por plano (desejo, emoção, atenção, reação, expressão corporal), seguido de **poses-chave estáticas** aprovadas por snapshot.

### 7.2 Ciclo de revisão (para cada movimento)

1. `hyperframes lint` e `hyperframes check`.
2. **Poses-chave:** `hyperframes snapshot --at <tempos das chaves>` gera um contact sheet.
3. **Onion skin e arc trail:** ferramenta do projeto que sobrepõe N frames com opacidade decrescente e desenha a trajetória de pontos do rig (focinho, ponta da orelha, ponta da cauda, patas). Serve para ler arcos e spacing. Protótipo já validado no teste.
4. **Telemetria automática do rig:** a cada frame o rig exporta as posições dos ossos e a área da malha. O script de QA aponta:
   - foot-slide (pata em contato deslizando);
   - velocidade constante prolongada (falta de easing);
   - partes iniciando ou terminando no mesmo frame (falta de overlap);
   - violação de volume e dos limites da seção 6.5;
   - “pop”: pico de pixels alterados entre frames consecutivos (método usado no teste).
5. **Gráficos de curva** (posição e velocidade dos canais principais) exportados em PNG.
6. **Render `--quality draft`** do movimento, entregue em MP4 para assistir em velocidade real, e uma versão a 50%.
7. Correção e repetição. Um movimento só entra na biblioteca depois de passar no checklist da seção 16 da Bible.

### 7.3 Limitação declarada

Eu não assisto vídeo em tempo real. Analiso sequências de frames, onion skins, curvas e métricas, o que cobre bem spacing, arcos, deslizamento, continuidade e volume. **O “feel” final (ritmo, humor, charme) precisa ser aprovado por um diretor humano assistindo ao MP4 em velocidade normal.** Cada entrega traz o vídeo e os artefatos de análise.

---

## 8. Biblioteca de movimentos do Ben

Construída em `lab/` como **folhas de teste neutras** (fundo cinza, chão preto), nunca como cenas.

### 8.1 Locomoção

| Movimento         | Função                | Parâmetros                         | Chaves de pose                                    | Desenhos de substituição |
| ----------------- | --------------------- | ---------------------------------- | ------------------------------------------------- | ------------------------ |
| Caminhada         | `benWalk`             | distância, velocidade, emoção      | contact / down / passing / up (diagonais)         | —                        |
| Corrida           | `benRun`              | distância, esforço, ciclo          | extensão / reunião / suspensão                    | olhos (coração, feliz)   |
| Parada            | `benStop`             | sobra                              | freada / avanço da massa / recuo / assenta         | —                        |
| Mudança de direção | `benTurn`            | lado                               | antecipação / vista frontal / espelho / assenta    | vista frontal            |

### 8.2 Ações

| Movimento            | Função               | Notas                                                                  |
| -------------------- | -------------------- | ---------------------------------------------------------------------- |
| Preparação de salto  | `benAnticipateJump`  | Agachamento + concentração (olhos semicerrados, dentes cerrados)       |
| Salto curto          | `benJump({height: baixo})` | O fracasso: ápice baixo, sem suspensão                           |
| Salto alto           | `benJump({hang})`    | Pula-pula: extensão total, suspensão, giros por substituição           |
| Queda                | `benFall`            | Corpo reage à aceleração; orelhas para cima                            |
| Aterrissagem         | `benLand`            | Squash proporcional à velocidade de chegada                            |
| Recuperação          | `benRecover`         | Balanço, sacudida, ajuste de postura                                   |

### 8.3 Expressões

Curiosidade, alegria, frustração, surpresa, encantamento e concentração. Cada uma combina slot de olhos, boca, posição de orelhas, inclinação de cabeça e o perfil de secundários da seção 6.7, encapsulados em `benReact`.

### 8.4 Secundários

Piscada, olhar, balanço da cauda, oscilação das orelhas, respiração e ajuste de postura, ativados pela camada 5 conforme a causa.

### 8.5 Transições entre estados

Grafo de estados: `idle ↔ walk ↔ run → stop → idle`, `idle → anticipation → jump → fall → land → recovery → idle` e `surprise → curiosity → joy`. Cada aresta tem uma regra de mistura:

- **Continuidade de posição e orientação:** a função seguinte começa do estado final da anterior (metadados).
- **Continuidade de velocidade:** a primeira tangente da curva seguinte é igual à última da anterior. Sem parada artificial entre caminhar e correr; o ciclo acelera e encurta.
- **Mistura de pose:** 3 a 6 frames de interpolação entre a última pose de um ciclo e a primeira da ação seguinte, com secundários carregando a inércia.

### 8.6 Ordem de construção proposta

1. Rig de perfil + idle + piscada + `benLookAt`
2. Caminhada → parada
3. Corrida → parada
4. Antecipação → salto curto → aterrissagem → frustração (o “teste de atuação” da seção 7 da Bible)
5. Salto alto com suspensão e giro
6. Expressões restantes e transições

---

## 9. Limitações e alternativas

| Limitação                                                            | Impacto visual                                                      | Solução proposta                                                                                           |
| -------------------------------------------------------------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Bitmaps do PDF a 100 ppi                                             | Ben borrado em vídeo                                                | Originais em alta resolução (bloqueante)                                                                  |
| Ben sem partes separadas nem áreas ocultas                           | Deformar uma região arrasta as vizinhas (visto no teste)            | Separação e repintura pelo ilustrador (seção 5.2)                                                         |
| Viradas e rotações 3D não saem de malha 2D                           | Uma cabeça “girando” por deformação parece falsa                    | Substituição de desenhos (seção 5.3) com troca escondida por movimento ou smear                           |
| Textura de pincel estica sob deformação                              | Pinceladas “borrachudas”                                            | Limite de estiramento (seção 6.5); poses extremas por substituição                                        |
| Emendas nas articulações                                             | Linhas visíveis entre peças                                         | Sobras repintadas, tufos sobre as juntas, rotação limitada por peça                                       |
| Não há motor de rig no HyperFrames                                    | Trabalho de engenharia                                              | Motor próprio enxuto (camada 2), validado no teste. Alternativa: runtime Spine/Rive se entrar animador humano |
| Lottie sem puppet/mesh                                               | Não serve para o Ben                                                | Lottie só para objetos vetoriais                                                                          |
| Render WebGL em “software gpu” é mais lento                          | Tempo de render                                                     | O teste fez 90 frames a 720p em 7,4 s. Estimo de 20 a 30 min por render completo de 5 min a 1080p. Iterar em draft por plano |
| Física por mola precisa ser determinística no seek                   | Tremores diferentes entre prévia e render                           | Passo fixo a partir do início do plano + cache (camada 5)                                                 |
| Avaliação de vídeo em tempo real por mim                             | Ritmo e humor                                                       | Métricas + artefatos + aprovação humana do MP4 (seção 7.3)                                                |
| CMYK → RGB                                                           | Cores diferentes do livro                                           | Master RGB ou conversão com perfil e validação de swatches                                                |
| Fonte _SketchnoteText_                                               | Restrição de uso                                                    | Verificar a licença; senão, texto convertido em contorno a partir do arte-final                           |

---

## 10. Decisões para aprovação e próximos passos

**Peço aprovação ou resposta para:**

1. **Técnica:** cut-out raster com malha WebGL e substituição de desenhos (opção A da seção 4.1).
2. **Formato de entrega:** 1920 × 1080, 16:9, 30 fps (ou 4K?).
3. **Exposição:** _twos_ para atuação e _ones_ para ações rápidas, câmera e tracking (seção 6.2).
4. **Acesso aos originais em camadas** do Ben e dos personagens (seção 5.1).
5. **Disponibilidade do ilustrador** para a separação em partes e os ~40–60 desenhos complementares (seções 5.2 e 5.3).
6. **Padrões das seções 6.1 a 6.7** como ponto de partida.
7. Se o texto do livro aparece em tela ou se haverá narração; isso afeta o ritmo de cada plano.

**Depois da aprovação e do recebimento dos arquivos:**

1. Análise do `.ai` e dos originais; script de importação (partes → `rig.json`).
2. Motor de rig mínimo + rig de perfil do Ben + folha de teste de idle, piscada e olhar.
3. Ferramentas de QA (telemetria, onion skin com arc trail, gráficos de curva).
4. Construção da biblioteca na ordem da seção 8.6, com revisão e aprovação a cada movimento.
5. Só então, planejamento de cenas (decupagem, beat sheets de atuação e câmera).
