import unittest
from anomaly_detection.patient_monitor import PatientMonitor
from anomaly_detection.video_integration import VideoFunctionAdapter, VideoAnalyzerStub


class VideoTests(unittest.TestCase):
    def monitor(self, result):
        return PatientMonitor(video_analyzer=VideoFunctionAdapter(lambda path: result))

    def test_completed_empty_and_finding(self):
        for findings in ([], [{"type": "POSTURA", "description": "desvio", "severity": "ALTO", "frame_number": 3}]):
            monitor = self.monitor({"status": "CONCLUIDA", "findings": findings})
            alerts = monitor.process_video_analysis("P", "video.mp4")
            self.assertEqual(len(alerts), len(findings))
            if alerts:
                self.assertFalse(alerts[0].simulated)
                self.assertEqual(alerts[0].priority.name, "P2_HIGH")
                self.assertEqual(alerts[0].details["frame_number"], 3)

    def test_inconclusive(self):
        monitor = self.monitor({"status": "INCONCLUSIVA", "findings": [], "summary": "Sem pessoa"})
        self.assertEqual(monitor.process_video_analysis("P", "video.mp4"), [])
        self.assertEqual(monitor.get_patient_history("P")[0]["data"]["status"], "INCONCLUSIVA")

    def test_invalid_result_is_failure(self):
        for result in ({}, {"status": "CONCLUIDA", "findings": [{"type": "A", "description": "B", "severity": "INVALIDA"}]},
                       {"status": "INCONCLUSIVA", "findings": []},
                       {"status": "CONCLUIDA", "findings": [], "frames_analyzed": True}):
            monitor = self.monitor(result)
            self.assertEqual(monitor.process_video_analysis("P", "video.mp4"), [])
            self.assertEqual(monitor.get_patient_history("P")[0]["data"]["status"], "FALHA")

    def test_exception(self):
        def fail(path):
            raise FileNotFoundError(path)
        monitor = PatientMonitor(video_analyzer=VideoFunctionAdapter(fail))
        self.assertEqual(monitor.process_video_analysis("P", "missing"), [])
        self.assertEqual(monitor.get_patient_history("P")[0]["data"]["status"], "FALHA")

    def test_stub_and_unconfigured(self):
        monitor = PatientMonitor(video_analyzer=VideoAnalyzerStub())
        self.assertTrue(monitor.process_video_analysis("P", "stub")[0].simulated)
        monitor = PatientMonitor()
        self.assertEqual(monitor.process_video_analysis("P", "none"), [])
        self.assertEqual(monitor.get_patient_history("P")[0]["data"]["status"], "NAO_INTEGRADO")
