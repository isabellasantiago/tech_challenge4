# Tech Challenge 4 — pipeline multimodal

Pipeline demonstrativa para um paciente fictício por execução. Integra áudio e
transcrição DAIC-WOZ, sinais vitais sintéticos, duas prescrições sintéticas e um
analisador de vídeo configurável. Os resultados são sinais de apoio acadêmico,
sem diagnóstico autônomo.

## Instalação e execução offline (etapa 1)

Requer Python 3.14+ e `uv`. Na raiz do repositório:

```bash
uv sync --frozen
uv run tech-challenge4 --patient-id PAC-DEMO-001 \
  --audio-dir src/audio_analisys/data/daicwoz/303_P \
  --openai-stub --video-stub
```

Esse comando extrai métricas do WAV e lê a transcrição reais. `--openai-stub`
substitui apenas a resposta da OpenAI por um resultado fixo identificado como
simulado; não precisa de chave nem de acesso à API. `--video-stub` gera um achado
fixo e não lê vídeo. Ambos produzem alertas com `simulated: true`, excluídos do
cálculo de risco real. O relatório esperado é `PARCIAL`, com risco `CRITICO` devido
à leitura sintética de pressão sistólica de 180 mmHg. Nenhuma chamada real à API
é feita nesse modo. Após instalar as dependências, a demonstração funciona offline.

## Execução com serviços reais (etapa 2)

Configure `OPENAI_API_KEY` no ambiente ou em `.env` (modelo atual: `gpt-4o-mini`).
A transcrição e as métricas acústicas são enviadas à OpenAI. O arquivo `.env` é
ignorado pelo Git; `.env.example` indica a variável necessária.

```bash
uv sync --frozen --extra video
uv run --extra video tech-challenge4 --patient-id PAC-DEMO-001 \
  --audio-dir src/audio_analisys/data/daicwoz/303_P \
  --video data/MobiPhysioResearch/E09_P32_AL_VFL_GM.mp4 \
  --video-analyzer anomaly_detection.mobiphysio_video:analyze_video \
  --report output/e2e-report.json \
  --alerts output/e2e-alerts.jsonl
```

Os seis vídeos da amostra MobiPhysio estão incluídos no repositório.
Na primeira análise, o modelo de pose é baixado. Confira
`execution_status: COMPLETA` em `output/e2e-report.json`; os alertas ficam em
`output/e2e-alerts.jsonl`, que acumula registros entre execuções.

O analisador segue o [contrato de vídeo](src/anomaly_detection/INTEGRACAO_VIDEO.md),
e o adaptador valida os dados e os converte ao tipo interno. Falha ao importar o
módulo ou processar o vídeo fica registrada como `FALHA` e não impede as outras
modalidades. Sem `--video`/`--video-analyzer` e sem `--video-stub`, o estado é
`NAO_INTEGRADO`. `--video` e `--video-analyzer` devem ser usados juntos.

## Módulo de vídeo MobiPhysio

O analisador em `anomaly_detection.mobiphysio_video:analyze_video` filtra E07,
E08 e E09 do MobiPhysio (Harvard Dataverse, DOI `10.7910/DVN/XSI0QN`). E07 é
Hip Joint Flexion, E08 Both Leg Flexion e E09 Back Extension.

Instale a dependência opcional de vídeo:

```bash
uv sync --frozen --extra video
```

Os seis vídeos versionados ficam em `data/MobiPhysioResearch`. São dois por
exercício, com vistas laterais e participantes distintos. MD5, IDs e nomes
ficam registrados em `sample_manifest.json`. Para baixar a amostra novamente,
use `uv run --extra video python -m anomaly_detection.mobiphysio_dataset`;
`MOBIPHYSIO_DATASET_DIR` altera o destino desse download.

O analisador usa MediaPipe PoseLandmarker Lite e uma regra heurística 2D:
excursão angular ombro-quadril-joelho menor que 15° gera um achado de severidade
`BAIXO`. A regra é demonstrativa, não foi validada clinicamente e não usa os
scores EAAQ. São necessários pelo menos três quadros válidos, 60% das amostras e cobertura
dos três terços do vídeo; em E08, ambos os lados devem ser medidos nos mesmos
quadros. Cobertura insuficiente resulta em `INCONCLUSIVA`. O modelo
é baixado na primeira análise e mantido no cache local; detalhes da regra,
modelo e limitações estão em
[INTEGRACAO_VIDEO.md](src/anomaly_detection/INTEGRACAO_VIDEO.md).
Nos seis clipes baixados, E07/E08 concluem sem achados e os dois clipes E09
produzem baixa excursão heurística (5,62° e 3,31°). O achado resume o vídeo todo;
os intervalos de quadros e segundos informam a amostragem, não o instante
de um desvio. Os quadros que contribuem aos percentis são registrados como
evidência das medições.

Exemplo integrado:

```bash
uv run --extra video tech-challenge4 --patient-id DEMO \
  --audio-dir src/audio_analisys/data/daicwoz/303_P --openai-stub \
  --video data/MobiPhysioResearch/E07_P02_AR_VFL_GM.mp4 \
  --video-analyzer anomaly_detection.mobiphysio_video:analyze_video
```

## Entradas e saídas

- `--patient-id`: identificador fictício, compartilhado por todas as modalidades.
- `--audio-dir`: pasta com um par `*_AUDIO.wav` e `*_TRANSCRIPT.csv` do DAIC-WOZ.
  Há seis participantes em `src/audio_analisys/data/daicwoz/`.
- `--vitals-csv`: padrão `src/anomaly_detection/data/sinais_vitais_demo.csv`,
  distribuído no pacote. Colunas: `timestamp` ISO-8601, `heart_rate`, `systolic_bp`,
  `diastolic_bp`, `spo2`, `temperature`, `respiratory_rate`.
- Prescrições fixas em `src/tech_challenge4/demo_inputs.py`: varfarina às 08h e
  aumento de dose/adição de aspirina às 09h de 13/11/2026, para demonstrar evolução
  e regras locais. Não são orientações terapêuticas.
- `--report`: padrão `output/report.json`, substituído a cada execução.
- `--alerts`: padrão `output/alerts.jsonl`, com acréscimo ao histórico existente.
  Os caminhos de relatório e alertas devem ser distintos.

Exemplo com saídas personalizadas:

```bash
uv run tech-challenge4 --patient-id DEMO \
  --audio-dir src/audio_analisys/data/daicwoz/303_P \
  --openai-stub --video-stub \
  --report output/demo.json --alerts output/demo-alerts.jsonl
```

Cada alerta aparece no console e no JSONL com UUID, paciente, origem, prioridade,
horário, status, evidências e indicação de simulação. Nenhuma notificação é entregue
a uma equipe médica. O relatório contém `findings` por modalidade, `alerts` como
lista completa, contagens em `alert_summary`, evolução das prescrições, limitações
e erros de gravação quando disponíveis. Horários dos achados vitais e prescrições
são os das entradas; horários de emissão são os do processo local.

Células ausentes, não numéricas, não finitas ou fora das faixas possíveis são
registradas em `data_errors`; as demais medições válidas continuam. As faixas de
validação demonstrativas estão em `POSSIBLE_RANGES`, separadas dos limiares de
alerta. SpO₂ de 100% é válida. Com histórico constante, o Z-score é `null` e a
mudança é registrada em `history_change`, sem alerta estatístico adicional.

## Estados, risco e códigos de saída

`execution_status` é `COMPLETA` apenas com áudio/OpenAI real, vídeo real concluído,
sinais válidos, duas prescrições e saídas gravadas. Ausência, falha, dado inválido,
resultado inconclusivo, stub ou erro de gravação tornam a execução `PARCIAL`.

O risco considera apenas alertas reais ativos: P1 → `CRITICO`, P2 → `ALERTA`,
P3/P4 → `ATENCAO`. Sem alertas reais e com avaliação incompleta, é `INDETERMINADO`;
com avaliação completa e sem alertas, `ESTAVEL`. As regras aplicadas às entradas
clínicas sintéticas geram alertas não simulados; as entradas continuam explicitamente
identificadas como sintéticas nas limitações.

- Código **0**: processamento e saídas concluídos, inclusive relatório parcial.
- Código **1**: falha operacional ao gravar relatório, JSONL ou emitir alertas no console,
  informada no stderr quando disponível. Uma falha no console não impede a gravação
  do JSONL. Erros dessas saídas são preservados no relatório parcial, mesmo se o
  próprio stderr falhar.
- Código **2**: argumentos inválidos.

Sem chave ou com erro da OpenAI, as métricas já extraídas são preservadas, o áudio
fica como `FALHA` e as outras modalidades seguem.

## Verificação e critérios de aceite

```bash
uv run python -m unittest discover -s tests -v
uv build --wheel
```

A suíte cobre contrato e estados do vídeo, carregamento externo, SpO₂ 100%, células
inválidas e leituras seguintes válidas, histórico constante, evolução de prescrições,
risco sem simulação, UUIDs entre execuções, JSONL cumulativo e falhas de gravação.
As chamadas à API e o processamento acústico são substituídos nos testes de unidade;
o comando offline acima valida a extração acústica com os arquivos do repositório.

**Etapa 1:** executar o comando offline, obter JSON/JSONL válidos, relatório parcial,
alertas reais e simulados distinguíveis e evidências preservadas. Implementada e
validada com substitutos de contrato.

**Etapa 2:** a execução real sem stubs foi realizada e registrou `COMPLETA`.
O achado de vídeo implementado resume todo o clipe e não localiza um desvio no tempo.
A [validação de vídeo](src/anomaly_detection/INTEGRACAO_VIDEO.md) descreve os
testes com modelo e vídeos reais, uma avaliação independente disponível e suas
limitações.

Limitações: não há transcrição automática, Azure, streaming, banco, canal externo,
eGeMAPS ou Isolation Forest. As regras farmacológicas e os limiares são limitados;
o dataset DAIC-WOZ não valida por si só um cenário de saúde pós-parto.

[Plano](docs/Plano.md) · [Arquitetura e decisões](docs/Arquitetura-e-System-Design.md)
