# Como contribuir

Valeu por querer ajudar! 🤠 Este é um projeto de fã, feito com calma e capricho. Toda contribuição boa
é bem-vinda, seja uma vírgula, um print de bug ou uma ferramenta nova.

## Regras de ouro

1. **Nunca envie arquivos do jogo.** Nada de ISO, `.DAT`, texturas extraídas, áudio original ou o
   `work/source.json` (que contém o texto original). O repositório guarda só ferramentas e tradução.
2. **Português nativo, não literal.** Leia o [glossário](docs/GLOSSARIO.md) antes de traduzir.
3. **Só traduza o que é legível.** Se um americano não consegue ler o texto no original (texto miúdo
   de enfeite), ele fica como está. Nunca invente texto.
4. **Teste no jogo** sempre que puder (PCSX2) e mande print.

## Jeitos de ajudar

### 🐞 Reportar problemas
Abra uma [issue](../../issues/new/choose) com o capítulo, o que aconteceu e um print (F8 no PCSX2).
Texto em inglês, texto cortado, letra faltando, travamento: tudo ajuda.

### ✍️ Revisar a tradução
Os textos ficam em [`traducao/`](traducao):

| Arquivo | O que é |
|---|---|
| `b01.json` … `b13.json` | textos das tabelas do jogo, `{id: português}` (o inglês sai da sua ISO via `extract.py`) |
| `_override.json` | quando a mesma frase em inglês precisa de traduções diferentes |
| `_subs.json` | legendas das cenas |
| `_keys.json` | rótulos de interface adicionados à tabela do jogo |
| `_pck.json` | textos dentro das interfaces `.pck` (no máximo o mesmo número de bytes do original) |
| `_pcktext_capNN.json` | texto compilado nas interfaces (diário, avisos, recompensas) |
| `_elf.json` | textos do executável (via patch do PCSX2) |

Depois de editar, rode o verificador. Ele confere símbolos de botão, `%s`, quebras de linha, glifos e largura:

```powershell
cd tools
py -E -X utf8 check.py ORIGINAL.iso
```

### 🎨 Texturas
Texturas com texto em inglês (cartazes, jornais, rótulos, títulos) são redesenhadas em português no mesmo
estilo. Abra uma issue antes, para combinar qual imagem e qual texto. As ferramentas `texpatch.py`,
`rscpatch.py` e `pckimage.py` exportam e importam as imagens (ver [docs/TECNICO.md](docs/TECNICO.md)).

### 🎙️ Dublagem
Veja [`dublagem/`](dublagem). Tem um estúdio no navegador que mostra o texto no tempo certo e grava.

### 🔧 Código e engenharia reversa
- Python 3 + Pillow. Sem dependências novas sem necessidade.
- Cada formato tem seu módulo (`dave.py`, `strtbl.py`, `pcktext.py`, `stma.py`...). Reutilize antes de escrever.
- Toda descoberta de formato vai para o [docs/TECNICO.md](docs/TECNICO.md).
- O `selftest.py` confere ida e volta dos formatos contra a ISO original (somente leitura).

**Desafio aberto:** as páginas do diário usam fontes reduzidas, só com ASCII. Para traduzi-las com acentos,
é preciso entender onde ficam os desenhos dos glifos (os ponteiros apontam para fora do `.pck`) e acrescentar
novos. Os detalhes estão na seção "pck: fontes e campos dinâmicos" do [TECNICO.md](docs/TECNICO.md).

## Fluxo de PR

1. Faça um fork e crie um branch (`traducao-cap03`, `fix-legenda-cap01`...).
2. Commits pequenos, com mensagem clara em português.
3. Abra o PR descrevendo o que mudou e, se possível, com prints do jogo.

Ao contribuir, você concorda em licenciar seu código sob [MIT](LICENSE) e seus textos de tradução e roteiros
sob [CC BY-SA 4.0](LICENSE-TRADUCAO.md).
