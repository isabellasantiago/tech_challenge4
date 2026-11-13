# Análise de áudio e transcrição

`AudioAnalyzer` lê WAV e transcrição pareada do DAIC-WOZ, recorta os turnos do
participante e extrai energia RMS, média/desvio do pitch e proporção de pausas
com librosa. Os limiares acústicos são indicadores demonstrativos de apoio:
pitch com desvio menor que 20 Hz, pausas acima de 35% e energia RMS abaixo de 0,01.
Essas métricas não constituem eGeMAPS; formantes não são extraídos pelo código.

`run_pipeline` encaminha as métricas e o texto do participante ao
`ClinicalNLPService`, que chama `gpt-4o-mini` e retorna uma avaliação JSON validada.
O monitor converte `multimodal_risk_assessment.overall_risk` em alerta quando
superior a `BAIXO`, preservando justificativa e recomendação. Não há regras locais
separadas de alerta amarelo/vermelho nem classificação clínica automática apenas
pelos limiares acústicos.

```bash
uv run tech-challenge4 --patient-id DEMO \
  --audio-dir src/audio_analisys/data/daicwoz/303_P \
  --openai-stub --video-stub
```

`--openai-stub` usa uma resposta fixa de demonstração, sem avaliar o texto; a
extração acústica continua real. O resultado e seus alertas são simulados e ficam
fora do risco real. Para chamada real, configure `OPENAI_API_KEY` e omita a opção.
Sem chave ou com falha da API, métricas já extraídas são preservadas e a modalidade
fica como `FALHA`, sem impedir as outras modalidades.

Não há Whisper ou transcrição automática. Use a transcrição fornecida no dataset.
DAIC-WOZ não valida, por si só, aplicação clínica em saúde pós-parto; o projeto é
um protótipo acadêmico de apoio, sem diagnóstico autônomo.

Veja os [comandos completos e critérios de aceite](../../README.md).
