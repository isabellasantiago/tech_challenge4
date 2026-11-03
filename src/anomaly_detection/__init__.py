"""
Módulo de Detecção de Anomalias para Monitoramento de Pacientes.

Este módulo implementa técnicas de detecção de anomalias em:
- Séries temporais de sinais vitais (batimentos, pressão arterial, oxigenação)
- Evolução de prescrições médicas
- Padrões de movimentação do paciente

Gera alertas automáticos para a equipe médica.
"""

from .vital_signs_detector import VitalSignsAnomalyDetector
from .prescription_analyzer import PrescriptionAnalyzer
from .alert_system import AlertSystem
from .patient_monitor import PatientMonitor
from .video_integration import VideoAnalyzerInterface, VideoAnalyzerStub

__all__ = [
    "VitalSignsAnomalyDetector",
    "PrescriptionAnalyzer",
    "AlertSystem",
    "PatientMonitor",
    "VideoAnalyzerInterface",
    "VideoAnalyzerStub",
]
