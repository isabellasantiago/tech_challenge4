"""Opt-in checks using downloaded videos and the real MediaPipe model."""
import os
import tempfile
import unittest
from pathlib import Path

from anomaly_detection.mobiphysio_dataset import REFERENCE_VIDEO, REGRESSION_VIDEO, LOWER_SCORE_VIDEOS, _md5
from anomaly_detection.mobiphysio_video import analyze_video
from anomaly_detection.patient_monitor import PatientMonitor
from anomaly_detection.video_integration import VideoFunctionAdapter


@unittest.skipUnless(os.environ.get("MOBIPHYSIO_REAL_TESTS") == "1", "requer vídeos e modelo reais")
class MobiPhysioRealTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ.get("MOBIPHYSIO_DATASET_DIR", "data/MobiPhysioResearch"))
        cls.reference = cls.root / REFERENCE_VIDEO["filename"]
        cls.example = cls.root / REGRESSION_VIDEO["filename"]
        for metadata in (REFERENCE_VIDEO, REGRESSION_VIDEO, *LOWER_SCORE_VIDEOS):
            path = cls.root / metadata["filename"]
            if not path.is_file():
                raise RuntimeError(f"Vídeo ausente: {path}; execute o download com --include-reference")
            if _md5(path) != metadata["md5"]:
                raise RuntimeError(f"Checksum diverge do Dataverse: {path}")

    def monitor(self):
        return PatientMonitor(video_analyzer=VideoFunctionAdapter(analyze_video))

    def test_annotated_reference_without_heuristic_alert(self):
        # Score máximo é uma referência independente de qualidade geral, não uma
        # anotação da excursão angular nem uma validação clínica do limiar.
        monitor = self.monitor()
        self.assertEqual(monitor.process_video_analysis("TESTE", str(self.reference)), [])
        data = monitor.get_patient_history("TESTE")[0]["data"]
        self.assertEqual(data["status"], "CONCLUIDA")
        self.assertEqual(data["findings"], [])

    def test_lower_overall_scores_do_not_imply_low_angular_excursion(self):
        # Estes scores combinam fatores distintos e não rotulam a regra geométrica.
        for metadata in LOWER_SCORE_VIDEOS:
            with self.subTest(video=metadata["filename"]):
                monitor = self.monitor()
                self.assertEqual(monitor.process_video_analysis(
                    "TESTE", str(self.root / metadata["filename"])), [])
                data = monitor.get_patient_history("TESTE")[0]["data"]
                self.assertEqual(data["status"], "CONCLUIDA")
                self.assertEqual(data["findings"], [])

    def test_real_sample_generates_traceable_alert(self):
        monitor = self.monitor()
        alerts = monitor.process_video_analysis("TESTE", str(self.example))
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].priority.name, "P4_LOW")
        self.assertFalse(alerts[0].simulated)
        self.assertEqual(alerts[0].details["exercise_code"], "E09")
        self.assertLess(min(alerts[0].details["angular_excursion_degrees"].values()), 15)
        for side, samples in alerts[0].details["percentile_evidence"].items():
            self.assertAlmostEqual(
                samples["p90"]["angle_degrees"] - samples["p10"]["angle_degrees"],
                alerts[0].details["angular_excursion_degrees"][side], delta=0.02,
            )
            for sample in samples.values():
                self.assertGreaterEqual(sample["offset_seconds"], 0)
                self.assertLessEqual(sample["offset_seconds"], 2.3)
        self.assertEqual(monitor.get_patient_history("TESTE")[0]["data"]["status"], "CONCLUIDA")

    def test_no_person_and_invalid_video(self):
        import cv2
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            empty = Path(folder) / "E09_sem_pessoa.mp4"
            writer = cv2.VideoWriter(str(empty), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 240))
            if not writer.isOpened():
                self.fail("codec mp4v indisponível para criar o vídeo de teste")
            for _ in range(30):
                writer.write(np.zeros((240, 320, 3), dtype=np.uint8))
            writer.release()
            monitor = self.monitor()
            self.assertEqual(monitor.process_video_analysis("TESTE", str(empty)), [])
            self.assertEqual(monitor.get_patient_history("TESTE")[0]["data"]["status"], "INCONCLUSIVA")
            invalid = Path(folder) / "E09_invalido.mp4"
            invalid.write_bytes(b"video invalido")
            monitor = self.monitor()
            self.assertEqual(monitor.process_video_analysis("TESTE", str(invalid)), [])
            self.assertEqual(monitor.get_patient_history("TESTE")[0]["data"]["status"], "FALHA")


if __name__ == "__main__":
    unittest.main()
