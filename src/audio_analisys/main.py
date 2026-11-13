"""Pipeline acústica real; somente a resposta textual pode ser simulada."""
from .audio_analyzer import AudioAnalyzer


class AudioPipelineError(RuntimeError):
    def __init__(self, message, acoustic_result):
        super().__init__(message)
        self.acoustic_result = acoustic_result


def validate_assessment(result):
    if not isinstance(result, dict):
        raise ValueError("avaliação clínica deve ser um dicionário")
    risk = result.get("multimodal_risk_assessment", {})
    if (not isinstance(risk, dict) or risk.get("overall_risk") not in
            {"BAIXO", "MEDIO", "ALTO", "CRITICO"}
            or not isinstance(risk.get("justification"), str)
            or result.get("text_risk_level") not in {"BAIXO", "MEDIO", "ALTO"}
            or not isinstance(result.get("identified_symptoms"), list)
            or not all(isinstance(item, str) for item in result["identified_symptoms"])
            or not isinstance(result.get("clinical_recommendation"), str)):
        raise ValueError("resposta clínica inválida")
    return result


class ClinicalNLPStub:
    """Resposta fixa para validar integração; não avalia a transcrição."""
    def analyze_clinical_risk(self, audio_analysis_result):
        return {
            "text_risk_level": "MEDIO", "identified_symptoms": [],
            "multimodal_risk_assessment": {
                "overall_risk": "MEDIO",
                "justification": "Resposta simulada fixa; não é avaliação do áudio.",
            },
            "clinical_recommendation": "Demonstração offline, sem recomendação clínica.",
        }


def run_pipeline(participant_folder: str, nlp_service=None):
    audio_results = AudioAnalyzer().analyze_participant_folder(participant_folder)
    try:
        if nlp_service is None:
            from .clinical_nlp_service import ClinicalNLPService
            nlp_service = ClinicalNLPService()
        assessment = validate_assessment(nlp_service.analyze_clinical_risk(audio_results))
    except Exception as exc:
        raise AudioPipelineError(str(exc), audio_results) from exc
    simulated = isinstance(nlp_service, ClinicalNLPStub)
    return {
        **audio_results,
        "audio_metrics": audio_results["acoustic_metrics"],
        "clinical_assessment": {**assessment, "simulated": simulated},
        "simulated": simulated,
        "model": "stub" if simulated else "gpt-4o-mini",
    }
