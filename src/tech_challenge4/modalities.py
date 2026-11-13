"""Processamento isolado: uma falha não interrompe as demais modalidades."""
import csv
from datetime import datetime
from anomaly_detection.vital_signs_detector import VitalSignsReading, POSSIBLE_RANGES
from .demo_inputs import demo_prescriptions


def process_audio(monitor, args):
    evidence = {}
    try:
        from audio_analisys.main import run_pipeline, ClinicalNLPStub, AudioPipelineError
        try:
            result = run_pipeline(str(args.audio_dir), ClinicalNLPStub() if args.openai_stub else None)
        except AudioPipelineError as exc:
            evidence = exc.acoustic_result
            raise
        monitor.process_audio_analysis(args.patient_id, result["clinical_assessment"])
        monitor.record_modality_result(args.patient_id, "audio_analysis", {
            "status": "SIMULADA" if result["simulated"] else "CONCLUIDA", **result,
        })
    except Exception as exc:
        monitor.record_modality_result(args.patient_id, "audio_analysis", {
            "status": "FALHA", "error": str(exc), "acoustic_result": evidence,
        })


def process_vitals(monitor, args):
    count = 0
    try:
        with args.vitals_csv.open(newline="", encoding="utf-8") as stream:
            for line, row in enumerate(csv.DictReader(stream), 2):
                count += 1
                try:
                    timestamp = datetime.fromisoformat(row.get("timestamp", ""))
                except (ValueError, TypeError) as exc:
                    monitor.record_modality_result(args.patient_id, "vital_signs", {
                        "status": "PARCIAL", "line": line, "error": f"timestamp inválido: {exc}",
                    })
                    continue
                monitor.process_vital_signs(args.patient_id, VitalSignsReading(
                    timestamp, **{key: row.get(key) for key in POSSIBLE_RANGES},
                ))
        if not count:
            raise ValueError("CSV sem leituras")
    except Exception as exc:
        monitor.record_modality_result(args.patient_id, "vital_signs", {
            "status": "FALHA", "error": str(exc),
        })


def process_prescriptions(monitor, args):
    for prescription in demo_prescriptions(args.patient_id):
        try:
            monitor.process_prescription(prescription)
        except Exception as exc:
            monitor.record_modality_result(args.patient_id, "prescription", {
                "status": "FALHA", "error": str(exc),
            })
