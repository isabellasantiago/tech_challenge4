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
export OPENAI_API_KEY='sua-chave'
uv run tech-challenge4 --patient-id PAC-DEMO-001 \
  --audio-dir src/audio_analisys/data/daicwoz/303_P \
  --video /caminho/video.mp4 --video-analyzer modulo_cae:analyze_video
```

Instale previamente o módulo do Cae e suas dependências no mesmo ambiente
Python. A função deve seguir o [contrato de vídeo](src/anomaly_detection/INTEGRACAO_VIDEO.md).
O adaptador já valida os dados e os converte ao tipo interno. Falha ao importar o
módulo ou processar o vídeo fica registrada como `FALHA` e não impede as outras
modalidades. Sem `--video`/`--video-analyzer` e sem `--video-stub`, o estado é
`NAO_INTEGRADO`. `--video` e `--video-analyzer` devem ser usados juntos.

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
- Código **1**: falha operacional ao gravar relatório ou JSONL, informada no stderr.
  Uma falha no JSONL permite continuar o processamento e salvar o relatório parcial.
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

**Etapa 2:** receber o módulo e o vídeo reais do Cae, suas regras e o instante
esperado do achado; instalar/configurar e executar com chamada real à OpenAI.
Aceitar apenas após conferir evidências e obter `COMPLETA`. Essa validação real
permanece pendente; a configuração não exige novos componentes de integração se
o contrato for cumprido.

Limitações: não há transcrição automática, Azure, streaming, banco, canal externo,
eGeMAPS ou Isolation Forest. As regras farmacológicas e os limiares são limitados;
o dataset DAIC-WOZ não valida por si só um cenário de saúde pós-parto.

[Plano](docs/Plano.md) · [Arquitetura e decisões](docs/Arquitetura-e-System-Design.md)
