import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class ClinicalNLPService:

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY não configurada no arquivo .env")
        self.client = OpenAI(api_key=api_key)

    def _build_system_prompt(self) -> str:
        return """
Você é um sistema especialista e neutro de triagem clínica em saúde mental.
Sua função é analisar a transcrição da fala de um paciente e as métricas acústicas extraídas de sua voz para classificar o nível de risco de forma fundamentada, objetiva e sem alucinações.

REGRAS DE ANÁLISE E GROUNDING:
1. ANCORAGEM ESTRITA AO TEXTO: Apenas identifique sintomas ou fatos que foram EXPLICITAMENTE ditos pelo participante. É estritamente proibido inventar dados de contexto não mencionados.
2. ESTRESSE OCUPACIONAL vs DEPRESSÃO CLÍNICA: Queixas cotidianas, estresse de trabalho (ex: rotina de motorista, turnos), preocupações financeiras normais ou cansaço pontual NÃO devem ser classificados como risco ALTO. Risco ALTO ou CRÍTICO exige relatos explícitos de anedonia (perda total de prazer), desesperança profunda, apatia severa ou incapacidade funcional.
3. PONDERAÇÃO ACÚSTICA: Marcadores de áudio (pausas e baixa energia) servem como sinais de apoio. Se a pessoa relata uma rotina fisicamente desgastante, é esperado que o tom de voz reflita cansaço sem que isso signifique necessariamente um transtorno depressivo.

ESTRUTURA DE SAÍDA (RESPOSTA EXCLUSIVAMENTE EM JSON):
{
  "text_risk_level": "BAIXO" | "MEDIO" | "ALTO",
  "identified_symptoms": ["apenas sintomas realmente citados no texto"],
  "multimodal_risk_assessment": {
    "overall_risk": "BAIXO" | "MEDIO" | "ALTO" | "CRITICO",
    "justification": "Explicação objetiva baseada APENAS em fatos presentes na transcrição e nos dados acústicos."
  },
  "clinical_recommendation": "Recomendação proporcional ao risco real identificado."
}
"""

    def analyze_clinical_risk(self, audio_analysis_result: dict) -> dict:
        """Envia os dados do áudio e texto para o LLM gerar o diagnóstico multimodal em JSON."""
        system_prompt = self._build_system_prompt()

        user_content = f"""
POR FAVOR, ANALISE OS SEGUINTES DADOS DA PACIENTE:

[DADOS ACÚSTICOS DA VOZ]
- Duração do Áudio: {audio_analysis_result['duration_seconds']}s
- Média do Pitch (F0): {audio_analysis_result['acoustic_metrics']['pitch_mean_hz']} Hz
- Variação do Pitch (Std Dev): {audio_analysis_result['acoustic_metrics']['pitch_std_dev_hz']} Hz
- Taxa de Pausas/Silêncio: {audio_analysis_result['acoustic_metrics']['pause_ratio'] * 100:.1f}%
- Energia Média (RMS): {audio_analysis_result['acoustic_metrics']['mean_energy']}
- Alertas Acústicos: {audio_analysis_result['acoustic_flags']}

[TRANSCRIÇÃO DA FALA]
"{audio_analysis_result['transcript']}"
"""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",  # Rápido e excelente para JSON estruturado
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.2,  # Baixa temperatura para respostas mais consistentes e clínicas
        )

        # Parse do JSON retornado pelo modelo
        clinical_report = json.loads(response.choices[0].message.content)
        return clinical_report