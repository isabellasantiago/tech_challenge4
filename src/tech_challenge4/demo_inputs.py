"""Entradas sintéticas fixas: não representam prescrição clínica."""
from datetime import datetime
from anomaly_detection.prescription_analyzer import Medication, Prescription


def demo_prescriptions(patient_id):
    return [
        Prescription("RX-DEMO-1", patient_id, datetime(2026, 11, 13, 8), [
            Medication("varfarina", 5, "mg", "1x/dia"),
        ], notes="Exemplo sintético"),
        Prescription("RX-DEMO-2", patient_id, datetime(2026, 11, 13, 9), [
            Medication("varfarina", 10, "mg", "1x/dia"),
            Medication("aspirina", 100, "mg", "1x/dia"),
        ], notes="Exemplo sintético de evolução e interação"),
    ]
