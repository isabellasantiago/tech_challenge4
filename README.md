# Tech Challenge 4

Comando integrado (um paciente fictício por execução):

```bash
uv sync
uv run tech-challenge4 --patient-id PAC-DEMO-001 --audio-dir src/audio_analisys/data/daicwoz/303_P
```

Entradas clínicas fixas: `src/anomaly_detection/data/sinais_vitais_demo.csv` e duas
prescrições sintéticas cronológicas. `--vitals-csv` permite outro CSV.
Saídas padrão: `output/report.json` e `output/alerts.jsonl` (acréscimo).
Altere-as com `--report PATH` e `--alerts PATH`.
