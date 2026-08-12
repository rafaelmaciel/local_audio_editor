# Audio Editor Local

Editor de áudio web executado localmente com Python + Flask + FFmpeg.

## Requisitos

- Python 3.10+
- FFmpeg instalado e disponível no PATH
- Navegador moderno

### Linux Mint / Ubuntu
No final da execução o navegador será aberto

```bash
./run.sh
```

### Windows
No final da execução o navegador será aberto.
Caso o bat não identifique o FFmpeg instalado, ele será instalado e o bat precisará ser executado novamente.

```bash
run.bat
```

### Acesso a aplicação

http://127.0.0.1:5000

## Uso

1. Informe uma pasta local contendo músicas.
2. Clique em "Carregar biblioteca".
3. Selecione uma música.
4. Reproduza e selecione um trecho no waveform.
5. Use os controles de corte, volume e fade.
6. Exporte uma nova cópia.

## Suporte a vídeo

O editor também aceita arquivos de vídeo e trabalha somente sobre a faixa de áudio.

Formatos reconhecidos:
- MP4
- MKV
- AVI
- MOV
- WebM
- MPEG/MPG
- M4V

Ao exportar um vídeo, a imagem é mantida e o áudio é processado com FFmpeg.


## Ajustes em lote

A interface permite aplicar a todas as músicas da pasta ajustes de timbre (graves, médios e agudos), intensidade dinâmica por compressão e volume. Os originais não são sobrescritos.


## Pré-visualização em tempo real

Os controles de graves, médios, agudos, intensidade e volume podem ser
ouvidos em tempo real usando a Web Audio API do navegador. A prévia usa
a mesma música selecionada no player e não modifica o arquivo original.

O mesmo conjunto de ajustes continua disponível para processamento em lote
pelo Python/FFmpeg.


## Nivelamento
A aplicação analisa LUFS, LRA e True Peak com FFmpeg/EBU R128, calcula as médias da pasta e permite usar essas médias como alvos de nivelamento.


## Substituição segura

O modo padrão de processamento é **Substituir arquivos originais**.
O FFmpeg sempre gera primeiro um arquivo completo em uma área temporária.
Somente após sucesso o original é substituído. Também existe a opção de
criar novos arquivos sem alterar a coleção original.


## Correção do processamento em pastas externas

Quando o modo de substituição está ativo, os arquivos temporários agora são
criados **na mesma pasta do arquivo original**. Isso evita falhas de `rename`
ou `replace` causadas por arquivos temporários em outro filesystem ou
partição, algo comum quando a aplicação roda em um diretório e a biblioteca
de músicas está em outro disco.


## Modo Karaoke

O módulo Karaoke permite:
- escolher Soprano, Mezzo-soprano, Contralto, Tenor, Barítono ou Baixo;
- analisar uma música ou uma pasta;
- estimar tom e faixa melódica;
- calcular uma transposição recomendada de -12 a +12 semitons;
- aplicar uma transposição individual;
- aplicar recomendações diferentes a cada música da pasta;
- preservar a duração/BPM da música durante a transposição.

A detecção de faixa é uma estimativa baseada no conteúdo melódico do áudio.
Ela não substitui uma análise vocal isolada do cantor, pois instrumentos e
backing vocals podem influenciar a estimativa. A etapa seguinte poderá usar
separação de stems para analisar especificamente a voz principal.

A configuração visual é separada da lógica de processamento de áudio.

## Desenvolvido em conjunto com IA