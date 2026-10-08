### Arquitetura da Solução de Áudio

Como o objetivo é capturar aspectos da fala que vão além do texto (como tom, fadiga e tristeza) sem fazer fine-tuning de modelos complexos do zero, a pipeline pode ser dividida em **duas camadas complementares**:

```
 ┌────────────────────────────────────────────────────────┐
 │                   Gravação (DAIC-WOZ)                  │
 └───────────────────────────┬────────────────────────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
 ┌───────────────────────┐       ┌────────────────────────┐
 │  Camada Acústica/Tom  │       │ Camada Texto/Conteúdo  │
 │  (librosa)            │       │(transcrição do dataset)│
 └──────────┬────────────┘       └──────────┬─────────────┘
            │                               │
            └────────────────┬──────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │        Módulo de Análise e Fusão de Anomalias        │
 │     (Métricas do áudio + Risco clínico detectado)      │
 └────────────────────────────────────────────────────────┘

```
---

### 1. Camada Acústica (Prosódia & Extração de Sinais)

Aqui extraímos as características físicas da voz que indicam fadiga, tristeza ou estado depressivo:

* **Métricas Principais:**
* **Pitch ($F_0$ / Frequência Fundamental):** Voz monótona ou plana (baixa variabilidade de pitch) é um indicador forte de estado depressivo/apatia.
* **Energy / RMS:** Sons com baixa energia/amplitude contínua indicam cansaço ou fala fraca/fadiga.
* **Silêncio e Pausas:** Medir a duração das pausas entre frases e palavras (fala lentificada).
* **Formantes ($F_1, F_2$):** Mudanças no trato vocal indicando tensão ou relaxamento muscular atípico.

### Parametrização dos Marcadores Prosódicos

A tabela abaixo resume os limiares operacionais adotados pelo `AudioAnalyzer` para a detecção de anomalias acústicas no dataset DAIC-WOZ:

| Métricas Acústicas | Limiar de Alerta (*Threshold*) | Indicador Clínico | Referência Bibliográfica |
| :--- | :--- | :--- | :--- |
| **Monotonia Vocal** (`pitch_std_dev_hz`) | `< 20.0 Hz` | Embotamento afetivo (*flat affect*) | Cummins et al. (2015) |
| **Lentificação da Fala** (`pause_ratio`) | `> 0.35` (35%) | Lentificação psicomotora e fadiga | Mundt et al. (2007) |
| **Baixa Energia Vocal** (`mean_energy`) | `< 0.01` (RMS) | Astenia e exaustão física | Scherer et al. (2013) |

* **Ferramentas:** `librosa` (para extração do conjunto padrão *eGeMAPS* de marcadores acústicos).

### 2. Camada de Conteúdo & Transcrição

Com a transcrição do áudio utilizamos para extrair termos de risco ou sentimentos:

* As transcrições utilizadas nessa camada foram oferecidas pelo proprio dataset.
* **OpenAI API / Prompting (In-Context Learning):**
* Injetar a transcrição e pedir para o LLM classificar menções a sintomas de saúde mental, dores, exaustão puerperal, anhedonia ou ansiedade.


### 3. Fusão e Regra de Alerta (Detecção de Anomalias)

Uma anomalia de áudio é disparada no relatório final quando ocorre a combinação dos fatores:

* **Alerta Amarelo (Apenas Acústico):** Variação de pitch abaixo de $X$ desvios-padrão + tempo de silêncio acima de $Y$ segundos (indica fadiga/apatia vocal mesmo sem o texto revelar nada).
* **Alerta Vermelho (Acústico + Texto):** Baixa energia vocal + transcrição contendo termos de alto risco (ex.: "não consigo levantar", "dor insuportável", "exaustão extrema").

----

### Score de Patient Health Questionnaire-8 (PHQ-8)
| Participante | PHQ-8 Score | PHQ-8 Binary | Diagnóstico (Ground Truth) |
| :---: | :---: | :---: | :--- |
| **303** | 0 | 0 | 🟢 Controle (Sem depressão) |
| **304** | 6 | 0 | 🟢 Controle (Sintomas leves) |
| **307** | 4 | 0 | 🟢 Controle (Sintomas leves) |
| **320** | 11 | 1 | 🔴 **Caso de Risco / Depressão Moderada** |
| **321** | 20 | 1 | 🔴 **Caso de Risco / Depressão Grave** |

---
#### Links mostrados no vídeo
- [Librosa](https://pypi.org/project/librosa/)
- [Artigo](https://www.psychiatry.org/news-room/apa-blogs/vocal-biomarkers-for-mental-health)
- [Dataset - DAIC WOZ](https://www.kaggle.com/datasets/saifzaman123445/daicwoz)