# Teste técnico: malha WebGL sobre bitmap + twos + MorphSVG

Este é um teste de viabilidade, não uma cena. Ele confirma no pipeline de render do HyperFrames três coisas: a deformação em malha sobre o bitmap do Ben, as poses do personagem em _twos_ (15 poses/s) junto com elementos em _ones_, e o `MorphSVGPlugin`. Os resultados estão na seção 3.3 de `../../docs/01-especificacao-tecnica-animacao.md`.

A imagem do livro não é versionada. Para recriá-la a partir do PDF de prova:

```bash
mkdir -p /tmp/ben-img && pdfimages -png -f 6 -l 6 AF-BEN-ALEM-SeloP.pdf /tmp/ben-img/img
python3 -c "from PIL import Image; im=Image.open('/tmp/ben-img/img-000.png').convert('RGB'); im.putalpha(Image.open('/tmp/ben-img/img-001.png').convert('L')); im.save('assets/ben-pose.png')"
```

Na extração do PDF inteiro, esses mesmos arquivos aparecem como `img-016` e `img-017`. Depois:

```bash
npx hyperframes lint .
npx hyperframes snapshot . --at 0,0.45,0.66,0.95,1.45,1.6,2.0,2.8
npx hyperframes render . --quality draft --fps 30 --output spike.mp4
```
