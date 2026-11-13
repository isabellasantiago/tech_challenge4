import unittest
from datetime import datetime
from unittest.mock import patch
from anomaly_detection.patient_monitor import PatientMonitor
from anomaly_detection.vital_signs_detector import VitalSignsReading, VitalSignsAnomalyDetector
from tech_challenge4.demo_inputs import demo_prescriptions


class ModalitiesTests(unittest.TestCase):
    def test_spo2_100_is_normal(self):
        result = VitalSignsAnomalyDetector().analyze_reading(VitalSignsReading(datetime.now(), spo2=100))
        self.assertFalse(result[0].is_anomaly)

    def test_invalid_cells_do_not_pollute_history_or_hide_valid_cells(self):
        detector = VitalSignsAnomalyDetector()
        for value in (None, "", "abc", "NaN", "inf", 101, -1):
            results = detector.analyze_reading(VitalSignsReading(datetime.now(), heart_rate="72", spo2=value))
            self.assertEqual([r.metric_name for r in results], ["heart_rate"])
        self.assertEqual(detector.history["spo2"], [])
        self.assertEqual(detector.analyze_reading(VitalSignsReading(datetime.now(), spo2=98))[0].current_value, 98)

    def test_constant_history_has_no_statistical_alert(self):
        detector = VitalSignsAnomalyDetector()
        for _ in range(3):
            detector.analyze_reading(VitalSignsReading(datetime.now(), heart_rate=72))
        result = detector.analyze_reading(VitalSignsReading(datetime.now(), heart_rate=80))[0]
        self.assertIsNone(result.z_score)
        self.assertEqual(result.history_change, 8)
        self.assertFalse(result.is_anomaly)
        result = detector.analyze_reading(VitalSignsReading(datetime.now(), heart_rate=160))[0]
        self.assertTrue(result.is_anomaly)

    def test_prescription_evolution(self):
        monitor = PatientMonitor()
        for prescription in demo_prescriptions("P"):
            monitor.process_prescription(prescription)
        report = monitor.prescription_analyzer.generate_report("P")
        self.assertIsNotNone(report)
        alerts = monitor.alert_system.get_patient_alerts("P")
        self.assertTrue(any("DOSAGEM" in a.title for a in alerts))
        self.assertTrue(any("INTERACAO" in a.title for a in alerts))

    def test_audio_passes_acoustics_to_service_and_preserves_them(self):
        from audio_analisys.main import run_pipeline, ClinicalNLPStub, AudioPipelineError
        evidence = {"participant_id": "303", "acoustic_metrics": {"mean_energy": 0.01}}
        with patch("audio_analisys.main.AudioAnalyzer.analyze_participant_folder", return_value=evidence):
            result = run_pipeline("303_P", ClinicalNLPStub())
            self.assertEqual(result["audio_metrics"], evidence["acoustic_metrics"])
            self.assertTrue(result["clinical_assessment"]["simulated"])
            class Broken:
                def analyze_clinical_risk(self, data):
                    raise RuntimeError("API indisponível")
            with self.assertRaises(AudioPipelineError) as caught:
                run_pipeline("303_P", Broken())
            self.assertEqual(caught.exception.acoustic_result, evidence)
