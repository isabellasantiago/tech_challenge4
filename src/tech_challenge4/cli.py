"""Um paciente fictício por execução; saídas locais de demonstração."""
import argparse
import json
import sys
from pathlib import Path

from anomaly_detection.patient_monitor import PatientMonitor
from anomaly_detection.video_integration import VideoAnalyzerStub, VideoFunctionAdapter
from .outputs import LocalAlertSink
from .modalities import process_audio, process_vitals, process_prescriptions

DEFAULT_VITALS = Path(__file__).parents[1] / "anomaly_detection/data/sinais_vitais_demo.csv"


def parser():
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--patient-id", required=True)
    command.add_argument("--audio-dir", required=True, type=Path)
    command.add_argument("--openai-stub", action="store_true", help="simular somente resposta OpenAI")
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
    if args.video_stub:
        monitor.video_analyzer = VideoAnalyzerStub()
    elif args.video_analyzer:
        try:
            monitor.video_analyzer = VideoFunctionAdapter.load(args.video_analyzer)
        except Exception as exc:
            monitor.record_modality_result(args.patient_id, "video_analysis", {
                "status": "FALHA", "error": str(exc),
            })
    sink = LocalAlertSink(args.alerts)
    monitor.alert_system.register_callback(sink)
    process_audio(monitor, args)
    process_vitals(monitor, args)
    process_prescriptions(monitor, args)
    if not args.video_analyzer or monitor.video_analyzer is not None:
        monitor.process_video_analysis(args.patient_id, str(args.video or "stub"))
    sink.close()
    for error in sink.errors:
        monitor.record_modality_result(args.patient_id, "output", error)
    try:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(monitor.generate_patient_report(args.patient_id),
                                          ensure_ascii=False, indent=2, allow_nan=False),
                               encoding="utf-8")
    except (OSError, ValueError, TypeError) as exc:
        print(f"Erro ao gravar relatório: {exc}", file=sys.stderr)
        return 1
    if not any(error.get("output") == "console" for error in sink.errors):
        print(f"Relatório: {args.report}")
    return 1 if sink.errors else 0
