import json
from audio_analyzer import AudioAnalyzer
from clinical_nlp_service import ClinicalNLPService


def run_pipeline(participant_folder: str):
    print(f"1. Iniciando análise de áudio e texto da pasta: {participant_folder}")
    audio_analyzer = AudioAnalyzer()
    audio_results = audio_analyzer.analyze_participant_folder(
        participant_folder
    )

    print("2. Enviando conhecimento para o modelo de triagem clínica (LLM)...")
    nlp_service = ClinicalNLPService()
    clinical_results = nlp_service.analyze_clinical_risk(audio_results)

    # Consolidação do Relatório Final do Tech Challenge
    final_report = {
        "participant_id": audio_results["participant_id"],
        "audio_metrics": audio_results["acoustic_metrics"],
        "acoustic_flags": audio_results["acoustic_flags"],
        "clinical_assessment": clinical_results,
    }

    return final_report


if __name__ == "__main__":
    participant_folder = "data/daicwoz/321_P"

    report = run_pipeline(participant_folder)

    print("\n=== RELATÓRIO FINAL DA PIPELINE MULTIMODAL ===")
    print(json.dumps(report, indent=2, ensure_ascii=False))