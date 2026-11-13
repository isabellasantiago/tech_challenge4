### 📌 Diretrizes Rápidas
* *Sem Fine-Tuning:* Vamos usar modelos pré-treinados SOTA (extração de características, visão e prompting/In-Context Learning).
* *Sem Chat/Interface:* Não precisa de front-end ou interação com usuário, só da pipeline Python processando os dados e gerando um relatório/JSON com os alertas de anomalia.
* *Cloud/Ferramentas:* Uso livre de APIs (OpenAI, Azure, AWS) ou bibliotecas open-source rodando localmente.

### 💡 Proposta Multimodal (Saúde da Mulher)

*1. Modalidade Áudio (Processamento de Voz e Tom)*
* *Cenário:* Detecção de fadiga, tristeza ou desânimo na fala em consultas de acompanhamento pós-natal (indicadores de depressão pós-parto / ansiedade puerperal).
* *Como fazer:* Extração de recursos acústicos (pitch, ritmo, variação de energia, pausas) via librosa/parselmouth + transcrição (Whisper).
* *Datasets Abertos:*
* [AudioSet (Google Research)](https://research.google.com/audioset/?utm_source=gemini) - Dataset recomendado no edital (contém áudios de choro, respiração, fala cansada).
* [DAIC-WOZ (Kaggle)](https://www.google.com/search?q=https://www.kaggle.com/datasets/ziyaddawish/daicwoz&utm_source=gemini) - Entrevistas clínicas abertas focadas em ansiedade e depressão.

*2. Modalidade Vídeo (Visão Computacional & Pose)*
* *Cenário:* Análise postural em fisioterapia pélvica ou exercícios pós-parto/gestacionais para prevenção de lesões ou diástase.
* *Como fazer:* Passar um vídeo MP4 curto no *MediaPipe Pose* (ou YOLOv8) para calcular ângulos de articulações e disparar alerta se a postura/movimento fugir do padrão seguro.
* *Exemplo de Input:* Vídeos curtos de domínio público / YouTube de fisioterapia pélvica e exercícios gestacionais.

*3. Modalidade Dados Estruturados / Séries Temporais (Sinais Vitais)*
* *Cenário:* Monitoramento de batimentos cardíacos fetais (Cardiotocografia) e picos de pressão arterial (risco de pré-eclampsia).
* *Como fazer:* Aplicar *Isolation Forest* ou *Z-Score* sobre dados temporais numéricos em CSV para flagar anomalias de pressão e desvios de frequência.
* *Datasets Abertos:*
* [Cardiotocography CTG (UCI Repository)](https://www.google.com/search?q=https://archive.ics.uci.edu/dataset/27/cardiotocography&utm_source=gemini) - Exames de frequência cardíaca fetal e contrações uterinas.
* [Maternal Health Risk (Kaggle)](https://www.google.com/search?q=https://www.kaggle.com/datasets/catherinesenne/maternal-health-risk-data&utm_source=gemini) - Indicadores de pressão, glicemia e risco na gestação.