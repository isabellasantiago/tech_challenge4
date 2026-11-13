"""Um paciente fictício por execução; saídas locais de demonstração."""
import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

from anomaly_detection.patient_monitor import PatientMonitor
from anomaly_detection.vital_signs_detector import VitalSignsReading
from .demo_inputs import demo_prescriptions

DEFAULT_VITALS = Path(__file__).parents[1] / "anomaly_detection/data/sinais_vitais_demo.csv"


def parser():
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--patient-id", required=True)
    command.add_argument("--audio-dir", required=True, type=Path)
    command.add_argument("--video", type=Path)
    video = command.add_mutually_exclusive_group()
    video.add_argument("--video-analyzer", metavar="modulo:funcao")
    video.add_argument("--video-stub", action="store_true")
    command.add_argument("--vitals-csv", type=Path, default=DEFAULT_VITALS)
    command.add_argument("--report", type=Path, default=Path("output/report.json"))
    command.add_argument("--alerts", type=Path, default=Path("output/alerts.jsonl"))
    return command


def main(argv=None):
    command = parser()
    args = command.parse_args(argv)
    if not args.patient_id.strip():
        command.error("--patient-id deve ser não vazio")
    if bool(args.video) != bool(args.video_analyzer) and not args.video_stub:
        command.error("use --video com --video-analyzer modulo:funcao")
    if args.report.resolve() == args.alerts.resolve():
        command.error("relatório e JSONL devem ter caminhos diferentes")
    monitor = PatientMonitor()
    monitor.alert_system.register_callback(lambda alert: print(
        f"[{alert.priority.name}] {alert.patient_id}: {alert.message}"
    ))
    with args.vitals_csv.open(newline="") as stream:
        for row in csv.DictReader(stream):
            monitor.process_vital_signs(args.patient_id, VitalSignsReading(
                timestamp=datetime.fromisoformat(row.pop("timestamp")),
                **{key: float(value) for key, value in row.items()},
            ))
    for prescription in demo_prescriptions(args.patient_id):
        monitor.process_prescription(prescription)
    monitor.process_video_analysis(args.patient_id, str(args.video or "stub"))
    try:
        args.alerts.parent.mkdir(parents=True, exist_ok=True)
        with args.alerts.open("a") as stream:
            for alert in json.loads(monitor.alert_system.export_alerts_json(args.patient_id)):
                stream.write(json.dumps(alert, ensure_ascii=False) + "\n")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(monitor.generate_patient_report(args.patient_id),
                                          ensure_ascii=False, indent=2))
    except OSError as exc:
        print(f"Erro ao gravar saídas: {exc}", file=sys.stderr)
        return 1
    return 0
