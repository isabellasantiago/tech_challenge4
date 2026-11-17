# Cenários de testes manuais da pipeline

Material de apoio para a entrega do módulo do Cae. Veja também as [orientações de integração](Orientacoes-Integracao-Video-Cae.md) e o [README](../README.md).

Execute os comandos a partir da raiz do projeto, após `uv sync --frozen`.

## Comando de referência

```bash
uv run tech-challenge4 --patient-id DEMO \
  --audio-dir src/audio_analisys/data/daicwoz/303_P \
  --openai-stub --video-stub \
  --report output/teste-manual/report.json \
  --alerts output/teste-manual/alerts.jsonl
```

Resultado esperado: 11 alertas (1 crítico, 6 altos, 3 médios e 1 baixo), dos quais 2 simulados; execução `PARCIAL`, risco `CRITICO` e código de saída 0. A análise acústica e a transcrição são reais; as respostas clínica e de vídeo são simuladas.

Os caminhos de saída acima separam esses testes das saídas padrão. O relatório é substituído em cada execução e o JSONL acumula alertas.

## Variações

| Cenário | Como executar a partir do comando de referência | Resultado esperado |
|---|---|---|
| Vídeo não integrado | Remova `--video-stub`, sem adicionar vídeo/analisador. | Vídeo `NAO_INTEGRADO`, relatório `PARCIAL`, nenhum alerta de vídeo e código 0. |
| OpenAI real | Configure `OPENAI_API_KEY` no ambiente ou `.env` e remova `--openai-stub`. | Áudio `CONCLUIDA` se a API responder com dados válidos. O vídeo continua simulado e o relatório parcial. A quantidade de alertas depende da resposta real. |
| Dados inválidos | Use uma cópia do CSV com células inválidas e acrescente `--vitals-csv PATH`. | Erros em `findings.vital_signs`, modalidade parcial, demais medições válidas processadas e código 0 se as saídas forem gravadas. |
| Histórico JSONL | Execute duas vezes usando o mesmo caminho de `--alerts`. | Novas linhas acrescentadas, UUIDs distintos e relatório contendo apenas a última execução. |
| Falha de gravação do relatório | Use um diretório existente como destino de `--report`. | Erro no console e código 1; o JSONL ainda pode ter sido gravado. |
| Falha de gravação do JSONL | Use um diretório existente como destino de `--alerts`. | Processamento continua, relatório parcial com `output_errors` e código 1. |

## Preparar um CSV inválido sem alterar a entrada original

```bash
uv run python - <<'PY'
import csv
from pathlib import Path

source = Path("src/anomaly_detection/data/sinais_vitais_demo.csv")
target = Path("output/teste-manual/sinais-invalidos.csv")
target.parent.mkdir(parents=True, exist_ok=True)
with source.open(newline="", encoding="utf-8") as stream:
    reader = csv.DictReader(stream)
    fields = reader.fieldnames
    rows = list(reader)
rows[0]["heart_rate"] = "invalido"
rows[0]["spo2"] = "101"
rows[0]["temperature"] = ""
with target.open("w", newline="", encoding="utf-8") as stream:
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
print(target)
PY
```

Acrescente `--vitals-csv output/teste-manual/sinais-invalidos.csv` ao comando de referência. Confira três erros de células na primeira leitura e a continuidade das leituras posteriores. A quantidade de alertas pode mudar porque as células inválidas deixam de ser avaliadas.

## Provocar uma falha de gravação

Crie um diretório para ser usado como destino inválido de arquivo:

```bash
mkdir -p output/teste-manual/destino-diretorio
```

No comando de referência, substitua **somente um** dos destinos por `output/teste-manual/destino-diretorio`: primeiro `--report`, depois, em outro teste, `--alerts`. Mantenha os dois caminhos diferentes.

Imediatamente após cada execução, confira o código de saída no Bash:

```bash
echo $?
```

O resultado esperado em ambos os casos é 1.

## Validação do módulo real do Cae

Substitua `--video-stub` por `--video /caminho/video.mp4 --video-analyzer modulo_cae:analyze_video`. Mantenha `--openai-stub` para testar o vídeo sem depender da API. Valide o achado, a severidade e o instante esperado contra o vídeo fornecido.

Esse teste ainda produz uma execução parcial porque a resposta clínica está simulada. Para o aceite final da etapa 2, configure a OpenAI real e remova também `--openai-stub`, seguindo os [critérios da arquitetura](Arquitetura-e-System-Design.md).
