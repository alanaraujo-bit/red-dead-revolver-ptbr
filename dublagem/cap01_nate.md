# Dublagem — Capítulo 1 (Na Mosca): Nate Harlow

Falas do Nate durante o ataque ao rancho, no jogo (não são da cutscene). Cada fala precisa caber no
tempo do original. Se passar até 40%, `stma.py prep` acelera sozinho; acima disso, regrave mais curto.

| Arquivo (stream) | Original (inglês) | Sugestão PT-BR | Máx. |
|---|---|---|---|
| nate_bullseye_01 | Red! Run up the hill, boy! We're gettin' raided! | Red! Sobe o morro, garoto! É um ataque! | 2,99 s |
| nate_bullseye_02 | Don't let me down, son! | Não me decepciona, filho! | 1,83 s |
| nate_bullseye_03 | I need ya now, son! | Preciso de você agora, filho! | 1,75 s |
| nate_bullseye_04 | Come on, Red, it's now or never! | Vamos, Red, é agora ou nunca! | 2,22 s |
| nate_bullseye_05 | Check round back, Red! | Olha lá atrás, Red! | 1,24 s |
| nate_bullseye_06 | Red! Come help, quick! | Red! Vem ajudar, rápido! | 2,13 s |
| nate_bullseye_07 | Falling Star! No! | Falling Star! Não! | 2,01 s |
| nate_bullseye_08 | What do you want? | O que vocês querem? | 0,98 s |
| nate_bullseye_09 | If it's gold you're after, there ain't none here! | Se é ouro que vocês querem, aqui não tem! | 2,94 s |

Referência de voz: `work/audio/nate_bullseye_NN.wav` (original decodificado).

## Como gravar: estúdio
1. Servidor local (na pasta do projeto): `py -m http.server 5500 --bind 127.0.0.1`
2. Abra no Chrome: http://localhost:5500/dublagem/estudio.html (outro roteiro: `?roteiro=arquivo.json`).
3. "Escolher pasta de gravação" → `work\dub\raw` (uma vez por sessão). Permita o microfone.
4. Para cada fala: O ouve o original, R grava (contagem 3-2-1, o texto acende no ritmo do tempo e a barra
   mostra o limite), Espaço para antes, P ouve o take e R refaz. Com "salvar ao terminar", cada take é
   salvo como `<stream>.webm`, e o novo substitui o anterior. "Tocar o original junto" serve de guia no
   fone. E edita o texto só na página; para mudar de vez, edite o `.json` do roteiro e mande um PR.
- Ambiente silencioso, microfone a ~20 cm, sem música ao fundo. Tom: pai desesperado, gritando por cima
  de tiros.

## Como entra no jogo
```
py -E -X utf8 tools\stma.py prepall "<sua ISO original>.iso"
py -E -X utf8 tools\build.py "<sua ISO original>.iso" work\test.iso
```
`prepall` converte todos os takes de `work\dub\raw` (corta silêncio, nivela e acelera até 1,4× se passar).
`build.py` grava cada `work/dub/<stream>.wav` por cima do stream original dentro do STREAMS.DAT.

Cutscenes: o áudio delas (`01_bull_*_PLII.stm`) é estéreo com voz, música e efeitos já misturados.
Dublar exige separar a voz (ex.: Demucs) e remixar. Fica para depois.
