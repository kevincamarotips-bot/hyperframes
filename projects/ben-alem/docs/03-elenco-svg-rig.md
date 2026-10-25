# Elenco em SVG com partes separadas para o rig (v0.1)

Os 10 personagens do livro além do Ben, recriados em SVG a partir das imagens do PDF de prova e separados em partes para animação. Mesmo processo do Ben (`02-ben-svg-rig.md`), generalizado.

## Gerador genérico

`tools/build_character_svg.py <config.json> <imagens-fonte> <saída>`, com uma configuração por personagem em `tools/characters/<nome>.json`:

- **paleta**: as cores do desenho (levantadas por k-means na imagem); cada pixel é classificado na cor mais próxima;
- **ossos**: nome, pai e pivô (px da imagem-fonte);
- **partes**: região (polígono), camadas de cor, cor de base (`under`) e áreas ocultas (`extend`). Há três tipos especiais:
  - `eye`: olho com elipse ajustada e pupila independente. Os pivôs de olho e pupila são calculados pela geometria detectada;
  - `svg`: peça desenhada em geometria limpa, para o que é translúcido no original (vidros, hélice, capô, cúpula);
  - `shared`: camada que não reivindica pixels, como o aro da escotilha desenhado por cima da tartaruga.

Regras do gerador, aprendidas na revisão:

1. Cada parte reivindica só pixels **das suas cores** dentro da região. Uma perna atrás de uma mancha não rouba a mancha.
2. **Olhos primeiro**, e sem reivindicar pixels: a cabeça continua inteira por baixo.
3. **Sobras**: um pixel sem dono vai para a parte mais próxima que tem a cor dele, até um alcance máximo. A área dos olhos fica fora dessa regra.
4. **Áreas ocultas** (`extend`) só existem dentro da silhueta e onde ficam escondidas: sob uma parte desenhada na frente ou sobre a mesma cor.
5. **1 px de sobreposição** entre peças vizinhas, na base e nas camadas. As juntas não deixam fresta de antialiasing.

## Personagens

| Personagem | Fonte | Partes (ossos) | Objetos de cena | Redesenhado em geometria limpa |
| --- | --- | --- | --- | --- |
| Salsicha | p. 5, 187×378 | corpo, coleira, cabeça, **mandíbula**, 2 orelhas cacheadas, 2 olhos, 4 patas, cauda | — | — |
| Preguiça A | p. 12, 466×344 | corpo, cabeça, 2 olhos, 2 braços na barra, braço esticado | barra do trapézio + cordas | cordas |
| Preguiça B | p. 12, 387×464 | idem | barra + cordas | cordas |
| Porco-espinho | p. 13, 273×501 | corpo com espinhos, cabeça, olho, 2 patas | cacho de balões (um osso) | — |
| Galinha | p. 14, 993×309 | corpo, asa, cabeça (crista e barbela), olho, pata | asa-delta, barra de controle | — |
| Elefante | p. 15, 661×962 | corpo, cabeça (orelha), **tromba**, olho, braço, perna, cauda | velame, cordas, mochila | — |
| Pinguim | p. 16, 1071×658 | corpo, cabeça (bico), nadadeira, olho | avião: asas, montantes, leme, trens de pouso | capô, **hélice** (osso próprio, gira), traços de giro |
| Tartaruga | p. 17, 464×1097 | casco, cabeça, 2 braços, 2 olhos | foguete, chama externa e núcleo (ossos próprios), manches, aro da escotilha | — |
| Alienígena | p. 21, 414×218 | cabeça, corpo, braço (aceno), 2 olhos (escuros, com brilho como pupila) | disco voador | cúpula e brilho |
| Cavalo astronauta | p. 20, 242×349 | corpo (traje), cabeça (crina, focinho), 2 orelhas, 2 olhos, 2 braços, 2 pernas, cauda | — | bolha do capacete e brilhos |

Cada personagem pendurado ou voando tem o pivô raiz onde o movimento nasce: o alto das cordas no trapézio, o velame no paraquedas, a barra na asa-delta e o nó dos barbantes nos balões. Assim, balançar é girar a raiz.

## Teste de rig do elenco (não é cena)

`lab/cast-rig-test/index.template.html` coloca os 10 personagens numa grade e dá a cada um um movimento característico. Por exemplo: a mandíbula do salsicha morde, as preguiças balançam no trapézio, a hélice gira, a chama do foguete tremula, o alienígena acena e o cavalo acena com os dois braços. Todos piscam. `tools/make_cast_lab.py` embute SVGs e rigs.

Achado da revisão: na preguiça, corpo e braços precisam girar juntos em torno das mãos na barra. Se só o corpo gira, a junta do ombro descola.

## Limitações conhecidas

- **Resolução das fontes**: galinha (~130 px), alienígena (~60 px de corpo) e porco-espinho foram traçados de imagens muito pequenas, ampliadas antes do traçado. As formas estão fiéis, mas detalhes finos (dedos, crista) estão simplificados.
- **Balões** formam um grupo único: no original eles se sobrepõem com transparência. Para animar cada balão separadamente, é preciso redesenhá-los um a um.
- **Tartaruga**: não há máscara da escotilha. Movimentos grandes fazem a tartaruga aparecer fora do vidro (o aro cobre só as bordas).
- **Hélice, capô, cúpula e bolha** foram redesenhados: são aproximações limpas do que no livro é translúcido.
- As **vistas** são as do livro (uma pose por personagem). Viradas e poses novas exigem desenhos novos.

## Arte não versionada no fork público

Só o gerador, as configurações (coordenadas e paletas, sem arte) e os testes estão neste fork. Os SVGs e rigs gerados ficam no repositório privado `ben-alem`.
