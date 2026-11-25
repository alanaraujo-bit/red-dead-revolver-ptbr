# Documentação técnica

Tudo o que foi descoberto sobre os formatos do jogo e como a cadeia de ferramentas funciona.
Os comandos usam `ORIGINAL.iso` para a sua cópia da ISO americana (`SLUS-20500`, CRC do ELF `E169BAF8`).
A ISO original nunca é alterada; o resultado é uma ISO nova. Glossário e estilo: [GLOSSARIO.md](GLOSSARIO.md).

## Como remontar

```powershell
cd tools
py -E -X utf8 selftest.py ORIGINAL.iso      # formatos ida-e-volta
py -E -X utf8 extract.py  ORIGINAL.iso ..\work\source.json
py -E -X utf8 check.py    ORIGINAL.iso      # símbolos, %s, glifos, largura
py -E -X utf8 fontneeds.py ORIGINAL.iso     # glifos por fonte (+ layouts)
py -E -X utf8 fontpatch.py ORIGINAL.iso ..\work\fonts_out damaged bosshealth arial14 regulatorcondensed courier18 mapscreen tgs_jp abalinesm
py -E -X utf8 build.py    ORIGINAL.iso ..\work\RDR-PTBR.iso
```

Requer Python 3.14 (`py`) e Pillow (`py -m pip install --user pillow`).
`extract.py` mantém os IDs estáveis: frases novas entram no fim, as antigas nunca mudam de ID.

## Arquivos de tradução (`traducao/`)

- `b01.json` … `b13.json`: `{id: texto}` — ids de `work/source.json` (a frase em inglês fica lá).
- `_override.json`: `{"tabela/chave": texto}` para quando a mesma frase em inglês pede traduções diferentes.
- `_pck.json`: `{inglês: português}` para os `.pck`. O português precisa ter no máximo o mesmo
  número de bytes (latin-1); o montador completa com espaços centralizados.
  Nunca encurtar com NUL: as strings ficam em tabelas de constantes de script.
- `_subs.json`: legendas (`*_en.txt`, UTF-16) `{"linha1<TAB>linha2": "pt1<TAB>pt2"}`. O jogo tira as aspas do Excel.
- Texturas: `work/tex_out/*.tex` (gerados com `tools/texpatch.py ISO nome.tex imagem.png work/tex_out [--flip] [--alpha]`).
  As imagens de origem (Gemini) ficam em `work/tex/loteN/`. Regra: só traduzir o que um jogador americano
  consegue ler no original; texto miúdo ilegível fica como enfeite.
- `_keys.json`: `{chave: texto}` com linhas **novas** na `swat.strtbl` (todas as cópias). Use para
  rótulos literais dos layouts (`Restart Level`, `Chapter 1`, `Player Options`...). Flags do `build.py`
  para bisseção: `--no-keys`, `--keys-only "A|B"`. Rodapés ficam em posições fixas: prefira textos curtos
  ("Abrir" em vez de "Selecionar").

## Formatos descobertos

- **Dave** (`*.DAT`): cabeçalho `Dave`/`DAVE`, entradas de 16 bytes em `0x800`, nomes em 6 bits com
  prefixo do nome anterior (`Dave`), dados deflate. Remontado preservando ordem e alinhamento de setor.
- **strtbl**: UTF-16; linhas na ordem de bucket do hash, hash = ELF/PJW da chave (`strtbl.elf_hash`).
- **fonttex**: registros `code u32, x, y, w, h u8, yoff s8, xadj s8`, ordenados por código; o final
  lista as páginas (fim de cada página). Páginas `.tex` 128x128, paleta RGBA (alfa PS2 0–128).
  A palavra 5 do cabeçalho (offset `0x14`) é o ascendente (= −yoff mínimo da fonte original). O jogo
  **não desenha** glifos cujo topo passe dele. Por isso o `fontpatch.py` aumenta esse valor para cobrir as
  maiúsculas acentuadas.
- **tex soltos**: cabeçalho de 14 bytes (`u16 w, h, fmt`...). O código de formato varia (0x0E, 0x01...), então
  vale decidir pelo tamanho: paleta de 256 cores + 8 bpp, 16 cores + 4 bpp, 8 bpp cinza, 24/32 bpp RGB
  (`texpatch.py decode_any/direct`). Paletas são BGRA em ordem simples; a cor direta é RGB. Muitas texturas de
  interface são uma cor só, com a arte no **alfa** (`texpatch.py --alpha`). A maioria fica gravada de cabeça
  para baixo (`--flip`).
- **RSC0** (`*.rsc`, um por cenário/modelo): cópias próprias das texturas 3D (cartazes, placas, a sala do menu).
  Diretório de pares (offset, tag), com cada textura em blocos `MIP0` (96 bytes de cabeçalho + pixels com
  swizzle PSMT8/PSMT4), `PAL0` (16 bytes + RGBA, alfa 0–128, ordem CSM1 em 256 cores) e `TEX0` (nome em +160).
  Pode ser uma variante da arte solta (outra paleta). O `rscpatch.py` reescreve o nível 0 requantizando na
  paleta do pacote. Texturas com mipmap no pacote ainda são puladas (o build avisa).
- **pck: texto estático** (`pcktext.py`): fluxo de pares u16
  `0002 ffff ffff 0001 | 000b TAM | [0004 X] 0003 Y 0005 N (glifo, avanço)×N ... | 0000`. O `0x04` define o x
  da linha (recuo ou centralização); o `0x05` é a quantidade de glifos. Os glifos da fonte de UI são:
  ASCII = código−32, `€`=96, minúsculas Latin-1 a partir de `à`=102, maiúsculas acentuadas e `®` = próprio
  código Latin-1. Índices inexistentes desenham lixo na tela. Os avanços vêm do texto original e, se não
  houver, de um ajuste linear sobre a `berrylium`. O bloco novo não pode passar do tamanho do original
  (`pcktextscan.py` lista os blocos). Para centralizar: x + largura/2 é constante (`"align": "center"`).
  O cabeçalho é `0002 RGBA 0001` (cor do texto), e o primeiro token é `(id da fonte, tamanho)`. Os ids de
  fonte são locais a cada `.pck` (ver abaixo); a 11 é a fonte de UI completa no j01/logo01. As fontes 17/20/149 usam os mesmos avanços da UI,
  escalados por tamanho/400. Há fontes reduzidas (só os glifos usados). A tabela de códigos delas é uma
  lista crescente de u16 no próprio `.pck`, e algumas não estão no arquivo (deduzidas pela ordem das letras).
  Catálogo: `pcktextscan.py ISO work/pck_static.json` (1411 blocos em 61 `.pck`: diário, lojas, avisos do
  memory card, tela de recompensa, créditos). Tradução: `traducao/_pcktext_capNN.json` (`{pck: {bloco: texto
  ou [linhas]}}`) → `pcktextgen.py` (gera itens "auto" no `_pcktext.json` e troca blocos de fonte reduzida
  para uma fonte completa) → `pcktext.py ISO` → `work/pck_out/`. O modo "auto" quebra o texto na largura do
  original, mantém margem ou centro e ancora vãos de ícone/número. O bloco não pode passar do espaço do
  original + o enchimento `0xCD` (cada glifo = 4 bytes, cada linha = 12). A ferramenta lista os estouros.
- **pck: fontes e campos dinâmicos.** O id de fonte é local a cada `.pck`. A fonte 11 funciona no j01
  (título do diário), mas numa página do diário desenha lixo, e a 12 trava o jogo. Objeto de fonte:
  `05cdcdcd`, ponteiro da classe, número de glifos e três ponteiros (+16 de defasagem), que apontam para
  os pares por glifo, a tabela de códigos u16 e os avanços u16. Antes vem um mapa de bytes
  código−0x20 → glifo. Os pares apontam para fora do arquivo, então ainda não dá para acrescentar glifos.
  As páginas do diário (j02–j19) só têm fontes ASCII (sem acento). Por isso `pcktextgen.py` deixa os blocos
  delas em inglês. Os campos de texto dinâmico (`07cdcdcd`, fonte u16 em +0x18, `abffabff` em +0x20) das
  listas do diário mostram as strings `nameList` do script como estão, sem `swat.strtbl`. Um caractere
  ausente da fonte não ocupa espaço. Por isso `build.py` aplica o `_pck.json` sem acentos nos `.pck`
  j02–j19 (Uísque → Uisque). "---LOCKED---" → "-Bloqueado-", porque "BLOQUEADO" corta no campo.
- **pck: imagens** (`pckimage.py`): objeto `[si][descritor][1][…][01000001 cdcdcd01 4]` + paleta CSM1;
  o descritor tem floats 1/w, 1/h, o ponteiro dos pixels (+0x18) e `(h<<16)|w` (+0x3C). Os pixels são PSMT8
  com swizzle, com defasagem de 16 bytes (usar ponteiro + 16). `encode()` grava uma imagem nova com paleta
  própria. Em `_pcktext.json`, use `"_images": {"0xOBJ": "caminho.png"}`.
- **Vozes** (`stma.py`): `STREAMS.DAT` (DAVE, 8361 `.stm`). Cabeçalho `STMA`: taxa em +0x0C (24000), canais
  em +0x14, tamanho dos dados em +0x18 e áudio a partir de 0x800. O codec é IMA/DVI ADPCM de 4 bits sem
  cabeçalho de bloco, nibble alto primeiro. Recodificar dá bit a bit igual. O texto de cada fala está nos
  `snd_*.csv` dos DATs (ex.: `snd_298.csv` do PERFNEW = Nate no cap. 1). Dublagem: `work/dub/<stream>.wav`
  (`stma.py prep` converte, corta silêncio, normaliza e acelera se passar do tempo). `build.py` grava por
  cima no lugar, cabendo no tamanho original. Roteiro: `dublagem/`. Cutscenes `_PLII` são estéreo
  mixadas (voz + música).
  Gravação: `dublagem/estudio.html` (servidor local, ver `dublagem/cap01_nate.md`) → `stma.py prepall ISO`
  (comprime e normaliza: as vozes originais têm RMS perto de −11 dBFS). Cap. 1: as 9 falas do Nate
  foram dubladas pelo autor do projeto.
- **ISO**: arquivos alterados que crescem vão para o fim da imagem (registro ISO9660 atualizado) +
  4 MiB de zeros no fim — o jogo lê adiante do fim do arquivo e travava sem essa folga.
