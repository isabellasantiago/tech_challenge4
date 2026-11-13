# Orientações para a entrega e integração do módulo de vídeo

A integração multimodal já está implementada na `main`. A entrega da frente de vídeo é um analisador independente que processe um vídeo real e devolva o contrato abaixo. O adaptador existente carrega a função, valida o resultado e o encaminha ao monitor.

Referências: [Arquitetura e System Design](Arquitetura-e-System-Design.md), especialmente as seções 4.3, 5 e 10, e [Guia de integração de vídeo](../src/anomaly_detection/INTEGRACAO_VIDEO.md).

Para exercitar a pipeline e suas falhas esperadas, consulte os [cenários de testes manuais](Cenarios-Testes-Manuais.md).

## 1. Preparação

Atualize o projeto e instale as dependências existentes:

```bash
git switch main
git pull --ff-only origin main
uv sync --frozen
```

O projeto requer Python 3.14+. As dependências do analisador, os modelos e seus pesos devem ser instalados e disponibilizados no mesmo ambiente usado pelo comando `tech-challenge4`. Documente como fazer isso e informe eventuais requisitos de hardware.

## 2. Responsabilidade do analisador

Exponha uma função Python importável:

```python
def analyze_video(video_path: str) -> dict:
    ...
```

O analisador recebe o caminho do vídeo, carrega os modelos necessários, processa o arquivo e devolve um dicionário Python. Ele deve ser independente de `PatientMonitor` e `AlertSystem`.

A escolha e a configuração dos modelos pertencem ao analisador. O contrato não exige métodos adicionais de postura, movimento ou detecção de objetos, nem um modelo específico. A implementação deve documentar o movimento ou evento efetivamente avaliado.

O código de integração existente cuida da associação ao paciente, da conversão de severidades em prioridades, da criação dos alertas e da gravação do relatório e do JSONL.

## 3. Contrato do resultado

Exemplo ilustrativo de formato — os valores e evidências da entrega devem vir da análise real:

```python
{
    "status": "CONCLUIDA",
    "findings": [
        {
            "type": "DESVIO_POSTURAL",
            "description": "Inclinação acima do limite configurado.",
            "severity": "MEDIO",
            "offset_seconds": 12.5,
            "frame_number": 375,
            "rule": "Descrever a regra e o limite utilizados"
        }
    ],
    "summary": "Um desvio identificado."
}
```

### Campos do resultado

| Campo | Tipo | Obrigatoriedade |
|---|---|---|
| `status` | Texto | Obrigatório: `CONCLUIDA`, `INCONCLUSIVA` ou `SIMULADA`. |
| `findings` | Lista de dicionários | Obrigatório; pode estar vazia. |
| `summary` | Texto | Obrigatório e não vazio para resultado `INCONCLUSIVA`; opcional nos demais. |
| `duration_seconds` | Número finito não negativo | Opcional. |
| `frames_analyzed` | Inteiro não negativo | Opcional. |

### Campos de cada achado

| Campo | Tipo | Obrigatoriedade |
|---|---|---|
| `type` | Texto não vazio | Obrigatório. |
| `description` | Texto não vazio | Obrigatório. |
| `severity` | Texto | Obrigatório; usar um dos valores da tabela abaixo. |
| `offset_seconds` | Número finito não negativo | Opcional; segundos desde o início do vídeo. |
| `frame_number` | Inteiro não negativo | Opcional; quadro original, começando em zero. |
| `confidence` | Número finito de 0 a 1 | Opcional; informar apenas se produzido pelo analisador. |

Ângulos medidos, limites, regra aplicada e outras evidências podem ser incluídos dentro de cada achado, desde que sejam serializáveis em JSON. Os campos opcionais indisponíveis devem ser omitidos. Não invente confiança, data de gravação ou evidências que não tenham sido medidas.

### Severidades aceitas

| Severidade | Prioridade criada pela integração |
|---|---|
| `CRITICO` | `P1_CRITICAL` |
| `ALTO` | `P2_HIGH` |
| `MEDIO` | `P3_MEDIUM` |
| `BAIXO` | `P4_LOW` |

Use exatamente essas grafias. Severidades desconhecidas tornam o resultado inválido. Inclua em `findings` somente achados que devem gerar alertas: a integração cria um alerta por achado de resultado concluído.

## 4. Resultados sem achados, inconclusão e falhas

Uma análise concluída sem desvios retorna:

```python
{
    "status": "CONCLUIDA",
    "findings": [],
    "summary": "Nenhum desvio identificado pela regra avaliada."
}
```

Se o vídeo não permitir a avaliação, por exemplo pela ausência de pessoa no enquadramento, retorne:

```python
{
    "status": "INCONCLUSIVA",
    "findings": [],
    "summary": "Não foi possível avaliar: nenhuma pessoa detectada."
}
```

Arquivo inexistente, formato inválido ou erro de processamento devem gerar uma exceção com mensagem explicativa. O monitor captura a exceção e registra `FALHA`. Não converta esses erros em `CONCLUIDA` com lista vazia.

`SIMULADA` é reservado a resultados de demonstração. A entrega que processa o vídeo real deve retornar `CONCLUIDA` ou `INCONCLUSIVA`, conforme o caso. A integração define automaticamente `simulated: false` nos alertas de resultados concluídos reais; o analisador não precisa criar os alertas.

## 5. Entregáveis

- Módulo com a função `analyze_video(video_path)` e instruções de instalação/importação.
- Referência exata para configuração, por exemplo `modulo_cae:analyze_video`.
- Dependências e versões compatíveis com o ambiente do projeto.
- Modelos e pesos necessários, com instruções de obtenção e configuração.
- Descrição do movimento ou evento avaliado, regra de detecção, limites e severidade atribuída.
- Vídeo real de exemplo, resultado esperado e instante esperado do desvio.
- Preferencialmente, exemplos adicionais sem desvio e sem condições de avaliação.

O exemplo de código deste documento apenas ilustra o contrato e não substitui um detector real.

## 6. Validação da integração com vídeo real

Depois de instalar o módulo e suas dependências no mesmo ambiente, execute a partir da raiz do projeto, substituindo o caminho e a referência da função:

```bash
uv run tech-challenge4 --patient-id DEMO \
  --audio-dir src/audio_analisys/data/daicwoz/303_P \
  --openai-stub \
  --video /caminho/video.mp4 \
  --video-analyzer modulo_cae:analyze_video
```

Esse comando processa o vídeo pelo módulo real e permite validar sua integração sem depender da OpenAI. Não use `--video-stub` nesse teste.

Confira em `output/report.json`:

- `current_status.video_analysis` igual a `CONCLUIDA` para um vídeo avaliável.
- Resultado e evidências em `findings.video`.
- Alertas de origem `VIDEO_ANALYSIS`, com prioridade correspondente à severidade e `simulated: false`.
- Correspondência entre o achado, o instante esperado do desvio e a regra documentada.
- Ausência de alerta de vídeo quando a análise é concluída sem achados.
- Estado `INCONCLUSIVA` com motivo, sem alerta clínico de vídeo, quando não houver condições de avaliação.
- Estado `FALHA` com mensagem quando ocorrer uma exceção ou retorno inválido.

Confira também os alertas no console e em `output/alerts.jsonl`. O JSONL preserva o histórico por acréscimo; o relatório é substituído a cada execução. Para separar as saídas desse teste, use `--report output/teste-cae.json --alerts output/teste-cae-alerts.jsonl`.

Com `--openai-stub`, a execução permanece `PARCIAL` mesmo que o vídeo real tenha sido concluído corretamente. O risco consolidado também considera os sinais vitais e as prescrições sintéticas; ele não depende apenas do vídeo.

## 7. Aceite final da etapa 2

Configure `OPENAI_API_KEY` no ambiente ou no arquivo `.env` e execute sem nenhuma opção de stub:

```bash
uv run tech-challenge4 --patient-id DEMO \
  --audio-dir src/audio_analisys/data/daicwoz/303_P \
  --video /caminho/video.mp4 \
  --video-analyzer modulo_cae:analyze_video
```

O aceite final exige áudio e transcrição processados com chamada real à OpenAI, vídeo real concluído, sinais vitais e duas prescrições avaliados, saídas gravadas e evidências rastreáveis. Nessas condições, o relatório deve apresentar `execution_status: COMPLETA`.

Uma execução `COMPLETA` pode conter alertas e risco elevado: o estado indica que o processamento necessário foi concluído, não que o paciente esteja sem achados.

O mesmo `patient_id` associa as modalidades para a demonstração. Isso não significa que os arquivos e dados sintéticos pertençam ao mesmo paciente real.
