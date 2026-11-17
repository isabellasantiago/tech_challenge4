# Integração de vídeo MobiPhysio

O analisador está em `anomaly_detection.mobiphysio_video:analyze_video` e é
independente do monitor. Usa o dataset MobiPhysio (Harvard Dataverse,
DOI `10.7910/DVN/XSI0QN`) e aceita somente vídeos cujos nomes ou diretórios
identifiquem E07, E08 ou E09. Os nomes publicados são E07 (Hip Joint Flexion),
E08 (Both Leg Flexion) e E09 (Back Extension).

## Instalação e amostra do dataset

Requer Python 3.14+, `uv` e conexão à internet para baixar, na primeira análise,
o modelo PoseLandmarker Lite. Os seis vídeos de exemplo estão no repositório:

```powershell
uv sync --frozen --extra video
```

São dois vídeos por exercício, de participantes distintos e com vista lateral.
Os IDs e checksums estão em `data/MobiPhysioResearch/sample_manifest.json`. Para
baixar a amostra novamente, execute:

```bash
uv run --extra video python -m anomaly_detection.mobiphysio_dataset
```

Defina `MOBIPHYSIO_DATASET_DIR` para
alterar o destino do download. A licença informada pelo Dataverse é CC0 1.0.

## Método e limitações

MediaPipe PoseLandmarker Lite processa aproximadamente três quadros por segundo
e mede em 2D o ângulo ombro-quadril-joelho, convertendo as coordenadas
normalizadas para pixels com a largura e a altura reais do quadro. Para E07 e E08, esse ângulo é usado
como proxy do quadril; para E09, como proxy do ângulo tronco-quadril. A heurística
compara os percentis 10–90 das medidas: excursão menor que 15° gera
`BAIXA_EXCURSAO_ANGULAR_HEURISTICA`, severidade `BAIXO`. Para concluir, é necessário medir pelo menos três quadros,
60% das amostras e pelo menos uma amostra em cada terço do vídeo. E08 exige
essa cobertura para ambos os lados nos mesmos quadros. Esses limites são
heurísticos e não garantem que um ciclo completo tenha sido capturado. Cobertura
insuficiente, ausência de pessoa ou taxa de quadros desconhecida ou inválida
retorna `INCONCLUSIVA`; arquivo ausente, inválido ou erro de processamento gera
exceção. Se o contêiner informar a quantidade esperada de quadros e a decodificação
terminar mais de um quadro antes dela, o analisador sinaliza `FALHA` por exceção.
Há tolerância de um quadro porque o contador reportado por alguns MP4s MobiPhysio
difere em um quadro da quantidade efetivamente decodificada.

Resultado observado nos seis clipes baixados: E07 e E08 concluem sem achados; os
dois clipes E09 concluem com baixa excursão estimada em 5,62° e 3,31°. O achado
resume o clipe inteiro. `sampled_frame_interval` e `sampled_interval_seconds`
informam o intervalo de amostragem, inclusive seus extremos, e não o início ou
o instante de um desvio. O campo `percentile_evidence` registra, para cada lado,
o ângulo, quadro e instante dos dois valores amostrados usados nos percentis
aproximados de 10% e 90%. Esses instantes identificam medições, não o início ou
o fim de um erro. Não se emite `offset_seconds` para o achado global.

O limite é demonstrativo e **não foi validado clinicamente**. O módulo não treina
nem usa o score EAAQ do dataset, não diagnostica e não estima confiança. A análise
usa CPU; não requer GPU. Na primeira execução, o modelo é baixado da origem oficial
do MediaPipe e armazenado em `~/.cache/tech-challenge4/pose_landmarker_lite.task`,
com SHA-256 verificado. Defina `MEDIAPIPE_POSE_MODEL_PATH` para apontar a um
arquivo local com o mesmo hash:
`59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a`.

## Uso na pipeline

Passe o caminho de um vídeo do conjunto, mantendo o código do exercício no nome:

```bash
uv run --extra video tech-challenge4 --patient-id DEMO \
  --audio-dir src/audio_analisys/data/daicwoz/303_P --openai-stub \
  --video data/MobiPhysioResearch/E07_P02_AR_VFL_GM.mp4 \
  --video-analyzer anomaly_detection.mobiphysio_video:analyze_video
```

`list_target_videos(dataset_dir)` lista apenas os MP4s E07/E08/E09. A função
retorna o contrato `CONCLUIDA` ou `INCONCLUSIVA`, e lança exceção para falhas. O
adaptador e o monitor validam a resposta e convertem os achados em alertas.

## Validação reproduzível

Para incluir o vídeo de referência independente, execute:

```bash
uv run --extra video python -m anomaly_detection.mobiphysio_dataset --include-reference
MOBIPHYSIO_REAL_TESTS=1 uv run --extra video python -m unittest discover -s tests -v
```

Além dos seis vídeos, o comando baixa `E09_P02_AR_VFL_GM.mp4` (Dataverse file
ID 11798560, MD5 `a45b591d0828f97a96a27bbdf7174130`). Na planilha pública
[Physiotherapist Exercise Marking](https://dataverse.harvard.edu/api/access/datafile/13453292),
três avaliadores deram nota geral 100/100 a esse vídeo. O analisador retornou
`CONCLUIDA` sem achado para ele. No mesmo arquivo, E09 P21 e P05 receberam,
respectivamente, notas médias gerais 54,76 e 71,43/100; ambos também foram
concluídos sem achados pela regra angular. A opção `--include-reference` também
baixa esses dois clipes, verificando seus checksums. No questionário E09 da
[publicação](https://doi.org/10.1016/j.dib.2026.112635), a pergunta 3 trata da
amplitude/completude do exercício; os três avaliadores atribuíram zero a esse
item para o vídeo P21. O método atual não implementa a pontuação EAAQ e a regra
de 15° não permite concluir se o exercício foi completado. As notas combinam outros
fatores e não são rótulos da regra específica de 15°: esse contraste não prova
um erro de implementação da regra nem valida sua capacidade de detectar os
problemas considerados pelos avaliadores. Os testes com vídeo real também
verificam o alerta no E09 P32, um vídeo gerado sem pessoa
(`INCONCLUSIVA`) e um arquivo inválido (`FALHA`). Os testes reais são opt-in e
requerem o modelo e os vídeos; a suíte padrão os registra como ignorados.

Em 16/11/2026, a pipeline foi executada sem stubs com o vídeo real
`E09_P32_AL_VFL_GM.mp4` e o áudio DAIC-WOZ 303. O relatório registrou
`execution_status: COMPLETA`, as quatro modalidades concluídas, duas prescrições
e áudio com `model: gpt-4o-mini`, `simulated: false`. O vídeo produziu 5,62°,
alerta `VIDEO_ANALYSIS` `P4_LOW` não simulado e oito amostras, dos quadros 0 a 56
(0 a aproximadamente 2,253 s). Os valores usados para os percentis foram
148,43° no quadro 56 (2,253 s) e 154,05° no quadro 8 (0,322 s). O relatório e
o JSONL locais estão em `output/video-completo-percentis-report.json` e
`output/video-completo-percentis-alerts.jsonl` (ignorados pelo Git).

Os scores consultados são por vídeo e não anotam eventos no tempo. O resultado
é uma estatística global, portanto o intervalo amostrado não identifica quando
teria ocorrido um desvio. A regra e a cobertura mínima são demonstrativas,
não validadas clinicamente, e nenhuma conclusão sobre postura segura ou risco
clínico decorre desse teste.
