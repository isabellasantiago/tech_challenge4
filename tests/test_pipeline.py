import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID

from anomaly_detection.alert_system import AlertSource, AlertSystem
from anomaly_detection.patient_monitor import PatientMonitor
from anomaly_detection.video_integration import VideoAnalyzerStub
from tech_challenge4.cli import main

ACOUSTICS = {
    "participant_id": "303", "duration_seconds": 3,
    "acoustic_metrics": {"mean_energy": 0.02, "pitch_mean_hz": 120,
                         "pitch_std_dev_hz": 22, "pause_ratio": 0.1},
    "acoustic_flags": [], "transcript": "Participant transcript",
}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.report = self.root / "report.json"
        self.alerts = self.root / "alerts.jsonl"

    def run_cli(self, extra=(), stub=True):
        args = ["--patient-id", "P", "--audio-dir", str(self.root),
                "--report", str(self.report), "--alerts", str(self.alerts)]
        if stub:
            args += ["--openai-stub", "--video-stub"]
        with patch("audio_analisys.main.AudioAnalyzer.analyze_participant_folder", return_value=ACOUSTICS), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main(args + list(extra))

    def test_offline_outputs_risk_uuid_and_append(self):
        self.assertEqual(self.run_cli(), 0)
        report = json.loads(self.report.read_text())
        lines = [json.loads(line) for line in self.alerts.read_text().splitlines()]
        self.assertEqual(report["execution_status"], "PARCIAL")
        self.assertEqual(report["current_status"]["risk_level"], "CRITICO")
        self.assertFalse(report["evaluation_complete"])
        self.assertEqual(report["alert_summary"]["critical"], 1)
        self.assertEqual(report["alert_summary"]["high"], 6)
        self.assertEqual(report["alert_summary"]["medium"], 3)
        self.assertEqual(report["alert_summary"]["low"], 1)
        self.assertEqual(len(lines), len(report["alerts"]))
        self.assertTrue(any(a["source"] == "VIDEO_ANALYSIS" and a["simulated"] for a in lines))
        self.assertEqual(report["findings"]["audio"][0]["audio_metrics"], ACOUSTICS["acoustic_metrics"])
        ids = {a["id"] for a in lines}
        for identifier in ids:
            UUID(identifier)
        self.assertEqual(self.run_cli(), 0)
        all_lines = [json.loads(line) for line in self.alerts.read_text().splitlines()]
        self.assertEqual(len(all_lines), len(lines) * 2)
        self.assertEqual(len({a["id"] for a in all_lines}), len(all_lines))

    def test_simulation_does_not_raise_real_risk(self):
        monitor = PatientMonitor(video_analyzer=VideoAnalyzerStub())
        monitor.process_video_analysis("P", "stub")
        report = monitor.generate_patient_report("P")
        self.assertEqual(report["current_status"]["risk_level"], "INDETERMINADO")
        monitor.alert_system.create_alert("P", AlertSource.MANUAL, "test", "real", severity="BAIXO")
        self.assertEqual(monitor.generate_patient_report("P")["current_status"]["risk_level"], "ATENCAO")

    def test_no_key_and_api_failure_continue_other_modalities(self):
        from audio_analisys.clinical_nlp_service import ClinicalNLPService
        for error in (ValueError("OPENAI_API_KEY ausente"), RuntimeError("API falhou")):
            with patch.object(ClinicalNLPService, "__init__", side_effect=error):
                self.assertEqual(self.run_cli(stub=False), 0)
            report = json.loads(self.report.read_text())
            self.assertEqual(report["current_status"]["audio_analysis"], "FALHA")
            self.assertEqual(report["current_status"]["video_analysis"], "NAO_INTEGRADO")
            self.assertEqual(report["analysis_count"]["prescriptions"], 2)
            self.assertEqual(report["analysis_count"]["vital_signs"], 3)
            self.assertEqual(report["findings"]["audio"][0]["acoustic_result"], ACOUSTICS)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
                ClinicalNLPService()

    def test_jsonl_failure_is_partial_and_nonzero_with_report(self):
        self.alerts.mkdir()
        self.assertEqual(self.run_cli(), 1)
        report = json.loads(self.report.read_text())
        self.assertEqual(report["execution_status"], "PARCIAL")
        self.assertTrue(report["output_errors"])
        self.assertGreater(len(report["alerts"]), 0)

    def test_jsonl_write_and_close_failures(self):
        from tech_challenge4.outputs import LocalAlertSink
        alert = AlertSystem().create_alert("P", AlertSource.MANUAL, "test", "test")
        sink = LocalAlertSink(self.alerts)
        real_stream = sink.stream
        with patch.object(sink, "stream") as stream, contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            stream.write.side_effect = OSError("disco cheio")
            stream.close.side_effect = OSError("erro no fechamento")
            sink(alert)
            sink.close()
        real_stream.close()
        self.assertEqual(len(sink.errors), 2)

    def test_console_errors_do_not_prevent_jsonl_persistence(self):
        from tech_challenge4.outputs import LocalAlertSink
        failures = [BrokenPipeError("stdout fechado"),
                    UnicodeEncodeError("ascii", "á", 0, 1, "não representável")]
        for index, error in enumerate(failures):
            with self.subTest(error=type(error).__name__):
                path = self.root / f"console-{index}.jsonl"
                sink = LocalAlertSink(path)
                alerts = AlertSystem()
                alerts.register_callback(sink)
                with patch("tech_challenge4.outputs.print", side_effect=error, create=True):
                    alert = alerts.create_alert("P", AlertSource.MANUAL, "teste", "evidência")
                    sink.close()
                stored = [json.loads(line) for line in path.read_text().splitlines()]
                self.assertEqual(stored, [alert.to_dict()])
                self.assertEqual(sink.errors, [{"output": "console", "error": str(error)}])

    def test_permanent_stdout_failure_preserves_outputs_and_returns_nonzero(self):
        class BrokenConsole(io.StringIO):
            def write(self, text):
                raise BrokenPipeError("stdout fechado")

        args = ["--patient-id", "P", "--audio-dir", str(self.root),
                "--report", str(self.report), "--alerts", str(self.alerts),
                "--openai-stub", "--video-stub"]
        with patch("audio_analisys.main.AudioAnalyzer.analyze_participant_folder", return_value=ACOUSTICS), \
                contextlib.redirect_stdout(BrokenConsole()), contextlib.redirect_stderr(io.StringIO()):
            result = main(args)
        self.assertEqual(result, 1)
        report = json.loads(self.report.read_text())
        lines = [json.loads(line) for line in self.alerts.read_text().splitlines()]
        self.assertEqual(len(report["alerts"]), 11)
        self.assertEqual({a["id"]: a for a in lines}, {a["id"]: a for a in report["alerts"]})
        self.assertEqual(report["execution_status"], "PARCIAL")
        self.assertTrue(report["output_errors"])
        self.assertTrue(all(error["output"] == "console" for error in report["output_errors"]))

    def test_report_failure_is_nonzero(self):
        self.report.mkdir()
        self.assertEqual(self.run_cli(), 1)
        self.assertTrue(self.alerts.is_file())

    def test_invalid_then_valid_csv_rows(self):
        csv = self.root / "vitals.csv"
        csv.write_text("timestamp,heart_rate,systolic_bp,diastolic_bp,spo2,temperature,respiratory_rate\n"
                       "2026-11-13T08:00:00,bad,120,80,101,,16\n"
                       "2026-11-13T09:00:00,72,120,80,100,36.5,16\n")
        self.assertEqual(self.run_cli(["--vitals-csv", str(csv)]), 0)
        report = json.loads(self.report.read_text())
        self.assertEqual(report["current_status"]["vital_signs"], "PARCIAL")
        first, second = report["findings"]["vital_signs"]
        self.assertEqual(len(first["data_errors"]), 3)
        self.assertEqual(len(second["results"]), 6)
        self.assertEqual(second["status"], "CONCLUIDA")

    def test_external_function_loaded_without_monitor_changes(self):
        module = self.root / "cae_example.py"
        module.write_text('def analyze_video(path):\n    return {"status": "CONCLUIDA", "findings": []}\n')
        sys.path.insert(0, str(self.root))
        self.addCleanup(sys.path.remove, str(self.root))
        self.addCleanup(sys.modules.pop, "cae_example", None)
        from audio_analisys.main import ClinicalNLPStub
        from audio_analisys.clinical_nlp_service import ClinicalNLPService
        assessment = ClinicalNLPStub().analyze_clinical_risk({})
        with patch.object(ClinicalNLPService, "__init__", return_value=None), \
                patch.object(ClinicalNLPService, "analyze_clinical_risk", return_value=assessment):
            self.assertEqual(self.run_cli(["--video", "real.mp4", "--video-analyzer", "cae_example:analyze_video"], stub=False), 0)
        report = json.loads(self.report.read_text())
        self.assertEqual(report["current_status"]["video_analysis"], "CONCLUIDA")
        # Exerce a lógica de conclusão com substitutos; não constitui aceite da etapa 2.
        self.assertEqual(report["execution_status"], "COMPLETA")

    def test_bad_plugin_does_not_prevent_other_modalities(self):
        self.assertEqual(self.run_cli(["--video", "a.mp4", "--video-analyzer", "absent_module:analyze_video"], stub=False), 0)
        report = json.loads(self.report.read_text())
        self.assertEqual(report["current_status"]["video_analysis"], "FALHA")
        self.assertEqual(report["analysis_count"]["prescriptions"], 2)

    def test_complete_no_real_alerts_is_stable(self):
        monitor = PatientMonitor()
        for source in ("audio_analysis", "video_analysis", "vital_signs", "prescription", "prescription"):
            monitor.record_modality_result("P", source, {"status": "CONCLUIDA"})
        self.assertEqual(monitor.generate_patient_report("P")["current_status"]["risk_level"], "ESTAVEL")

    def test_missing_csv_preserves_other_modalities(self):
        self.assertEqual(self.run_cli(["--vitals-csv", str(self.root / "missing.csv")]), 0)
        report = json.loads(self.report.read_text())
        self.assertEqual(report["current_status"]["vital_signs"], "FALHA")
        self.assertEqual(report["analysis_count"]["prescriptions"], 2)
        self.assertEqual(report["current_status"]["audio_analysis"], "SIMULADA")

    def test_bad_timestamp_does_not_block_next_reading(self):
        csv = self.root / "vitals.csv"
        csv.write_text("timestamp,heart_rate,systolic_bp,diastolic_bp,spo2,temperature,respiratory_rate\n"
                       "bad,72,120,80,98,36.5,16\n"
                       "2026-11-13T09:00:00,72,120,80,98,36.5,16\n")
        self.assertEqual(self.run_cli(["--vitals-csv", str(csv)]), 0)
        report = json.loads(self.report.read_text())
        self.assertEqual(report["current_status"]["vital_signs"], "PARCIAL")
        self.assertEqual(len(report["findings"]["vital_signs"][1]["results"]), 6)

    def test_missing_audio_preserves_other_modalities(self):
        args = ["--patient-id", "P", "--audio-dir", str(self.root / "missing"),
                "--report", str(self.report), "--alerts", str(self.alerts), "--openai-stub"]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(args), 0)
        report = json.loads(self.report.read_text())
        self.assertEqual(report["current_status"]["audio_analysis"], "FALHA")
        self.assertEqual(report["analysis_count"]["prescriptions"], 2)
        self.assertEqual(report["analysis_count"]["vital_signs"], 3)
