# 🎙️ Dublagem

Sim, dá para dublar *Red Dead Revolver*. As falas ditas durante o jogo ficam em arquivos de áudio
separados (`STREAMS.DAT`, formato STMA), e as ferramentas trocam cada uma pela sua gravação,
mantendo o tempo original.

## Estúdio no navegador

O [`estudio.html`](estudio.html) funciona como uma cabine de dublagem: toca o original, faz contagem
3-2-1, mostra o texto grande acendendo no ritmo da fala, desenha uma barra com o tempo limite e grava
pelo microfone.

```powershell
# 1. gere os áudios originais de referência a partir da SUA ISO
py -E -X utf8 tools\stma.py refs ORIGINAL.iso dublagem\cap01_nate.json

# 2. sirva a pasta do projeto e abra no Chrome
py -m http.server 5500 --bind 127.0.0.1
#    http://localhost:5500/dublagem/estudio.html?roteiro=cap01_nate.json
```

Atalhos: **O** ouvir original · **R** gravar · **Espaço** parar · **P** ouvir take · **S** salvar ·
**↑/↓** trocar de fala. Escolha a pasta `work\dub\raw` no botão do topo, e cada take é salvo como
`<stream>.webm`.

## Do take ao jogo

```powershell
py -E -X utf8 tools\stma.py prepall ORIGINAL.iso                # converte, corta silêncio, nivela, ajusta o tempo
py -E -X utf8 tools\build.py ORIGINAL.iso work\RDR-PTBR.iso     # grava as falas na ISO nova
```

## Roteiros

| Roteiro | Personagem | Falas | Situação |
|---|---|---|---|
| [`cap01_nate.json`](cap01_nate.json) | Nate Harlow (pai do Red) | 9 | 🎙️ gravado, em teste |

Quer dublar alguém? Abra uma issue dizendo o personagem. O texto de cada fala está nas tabelas
`snd_*.csv` dos arquivos do jogo, e a gente monta o roteiro junto.

## Limites conhecidos

- Cada fala precisa caber no tempo original (até 40% mais longa, o `prep` acelera).
- As **cutscenes** têm voz, música e efeitos misturados num áudio estéreo só. Dublar exige separar a voz
  (ex.: Demucs) e remixar: está em pesquisa.
- Algumas falas só tocam em situações específicas do jogo. Para testar, é preciso provocar a situação.
