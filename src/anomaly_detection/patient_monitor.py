"""
Monitor de Pacientes - Orquestrador Principal.

Integra todas as fontes de dados para monitoramento contínuo:
- Sinais vitais em tempo real
- Prescrições médicas
- Análise de áudio (integrado com módulo existente)
- Análise de vídeo (interface preparada para integração futura)

Fornece visão unificada do estado do paciente e gera alertas consolidados.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Protocol, Any
from enum import Enum

from .vital_signs_detector import (
    VitalSignsAnomalyDetector,
    VitalSignsReading,
    AnomalyResult,
)
from .prescription_analyzer import (
    PrescriptionAnalyzer,
    Prescription,
    PrescriptionAlert,
)
from .alert_system import AlertSystem, AlertSource, MedicalAlert


class PatientRiskLevel(Enum):
    """Nível de risco geral do paciente."""
    STABLE = "ESTAVEL"
    ATTENTION = "ATENCAO"
    WARNING = "ALERTA"
    CRITICAL = "CRITICO"


@dataclass
class PatientStatus:
    """Status consolidado do paciente."""
    patient_id: str
    risk_level: PatientRiskLevel
    last_update: datetime
    vital_signs_status: str
    prescription_status: str
    audio_analysis_status: Optional[str] = None
    video_analysis_status: Optional[str] = None
    active_alerts_count: int = 0
    critical_alerts_count: int = 0
    summary: str = ""


class VideoAnalyzerProtocol(Protocol):
    """
    Protocolo/Interface para integração com módulo de análise de vídeo.

    Quem implementar análise de vídeo deve seguir esta interface:
    - analyze_video(video_path) -> dict com resultados
    - detect_movement_anomalies(frames) -> list de anomalias
    """

    def analyze_video(self, video_path: str) -> dict:
        """Analisa vídeo e retorna resultados."""
        ...

    def detect_movement_anomalies(self, patient_id: str, frames: Any) -> list[dict]:
        """Detecta anomalias de movimentação."""
        ...


class PatientMonitor:
    """
    Monitor central de pacientes.

    Orquestra a análise de múltiplas fontes de dados e consolida
    o estado de saúde do paciente em tempo real.
    """

    def __init__(
        self,
        alert_system: Optional[AlertSystem] = None,
        video_analyzer: Optional[VideoAnalyzerProtocol] = None,
    ):
        """
        Inicializa o monitor.

        Args:
            alert_system: Sistema de alertas (cria novo se não fornecido)
            video_analyzer: Analisador de vídeo opcional (para integração futura)
        """
        self.alert_system = alert_system or AlertSystem()
        self.vital_signs_detector = VitalSignsAnomalyDetector()
        self.prescription_analyzer = PrescriptionAnalyzer()
        self.video_analyzer = video_analyzer

        # Cache de status dos pacientes
        self._patient_status: dict[str, PatientStatus] = {}

        # Histórico de análises
        self._analysis_history: dict[str, list[dict]] = {}

    def _determine_risk_level(self, patient_id: str) -> PatientRiskLevel:
        """Determina nível de risco baseado nos alertas ativos."""
        summary = self.alert_system.get_patient_summary(patient_id)

        if summary.critical_count > 0:
            return PatientRiskLevel.CRITICAL
        elif summary.high_count > 0:
            return PatientRiskLevel.WARNING
        elif summary.medium_count > 0:
            return PatientRiskLevel.ATTENTION
        return PatientRiskLevel.STABLE

    def process_vital_signs(
        self, patient_id: str, reading: VitalSignsReading
    ) -> list[MedicalAlert]:
        """
        Processa leitura de sinais vitais e gera alertas se necessário.

        Args:
            patient_id: ID do paciente
            reading: Leitura dos sinais vitais

        Returns:
            Lista de alertas gerados
        """
        anomalies = self.vital_signs_detector.analyze_reading(reading)
        alerts = []

        for anomaly in anomalies:
            if anomaly.is_anomaly:
                alert = self.alert_system.create_alert_from_vital_signs(
                    patient_id=patient_id,
                    anomaly_result={
                        "is_anomaly": anomaly.is_anomaly,
                        "metric_name": anomaly.metric_name,
                        "message": anomaly.message,
                        "severity": anomaly.severity.value,
                        "current_value": anomaly.current_value,
                        "expected_range": anomaly.expected_range,
                        "z_score": anomaly.z_score,
                    },
                )
                if alert:
                    alerts.append(alert)

        # Registra no histórico
        self._add_to_history(
            patient_id,
            "vital_signs",
            {
                "timestamp": reading.timestamp.isoformat(),
                "anomalies_detected": len([a for a in anomalies if a.is_anomaly]),
                "readings": {
                    "heart_rate": reading.heart_rate,
                    "systolic_bp": reading.systolic_bp,
                    "diastolic_bp": reading.diastolic_bp,
                    "spo2": reading.spo2,
                    "temperature": reading.temperature,
                    "respiratory_rate": reading.respiratory_rate,
                },
            },
        )

        return alerts

    def process_prescription(
        self, prescription: Prescription
    ) -> list[MedicalAlert]:
        """
        Processa prescrição médica e gera alertas se necessário.

        Args:
            prescription: Prescrição a ser analisada

        Returns:
            Lista de alertas gerados
        """
        prescription_alerts = self.prescription_analyzer.analyze_prescription(
            prescription
        )
        alerts = []

        for p_alert in prescription_alerts:
            alert = self.alert_system.create_alert_from_prescription(
                patient_id=prescription.patient_id,
                prescription_alert={
                    "alert_type": p_alert.alert_type.value,
                    "message": p_alert.message,
                    "severity": p_alert.severity.value,
                    "medication_name": p_alert.medication_name,
                    "recommendation": p_alert.recommendation,
                    "details": p_alert.details,
                },
            )
            alerts.append(alert)

        # Registra no histórico
        self._add_to_history(
            prescription.patient_id,
            "prescription",
            {
                "timestamp": prescription.timestamp.isoformat(),
                "prescription_id": prescription.prescription_id,
                "medications_count": len(prescription.medications),
                "alerts_generated": len(prescription_alerts),
            },
        )

        return alerts

    def process_audio_analysis(
        self, patient_id: str, audio_result: dict
    ) -> Optional[MedicalAlert]:
        """
        Processa resultado de análise de áudio do módulo existente.

        Args:
            patient_id: ID do paciente
            audio_result: Resultado do ClinicalNLPService

        Returns:
            Alerta gerado (se houver)
        """
        alert = self.alert_system.create_alert_from_audio_analysis(
            patient_id=patient_id,
            audio_result=audio_result,
        )

        # Registra no histórico
        self._add_to_history(
            patient_id,
            "audio_analysis",
            {
                "timestamp": datetime.now().isoformat(),
                "text_risk_level": audio_result.get("text_risk_level"),
                "overall_risk": audio_result.get("multimodal_risk_assessment", {}).get(
                    "overall_risk"
                ),
                "alert_generated": alert is not None,
            },
        )

        return alert

    def process_video_analysis(
        self, patient_id: str, video_path: str
    ) -> list[MedicalAlert]:
        """
        Processa análise de vídeo (quando integrado).

        Esta função está preparada para receber um VideoAnalyzer que
        implemente VideoAnalyzerProtocol.

        Args:
            patient_id: ID do paciente
            video_path: Caminho do vídeo a analisar

        Returns:
            Lista de alertas gerados
        """
        if self.video_analyzer is None:
            # Registra que vídeo não foi processado por falta de integração
            self._add_to_history(
                patient_id,
                "video_analysis",
                {
                    "timestamp": datetime.now().isoformat(),
                    "status": "NOT_INTEGRATED",
                    "message": "Módulo de análise de vídeo não integrado",
                },
            )
            return []

        # Quando o módulo de vídeo for integrado, usar:
        # results = self.video_analyzer.analyze_video(video_path)
        # anomalies = self.video_analyzer.detect_movement_anomalies(patient_id, results)

        # Por enquanto, retorna lista vazia
        return []

    def _add_to_history(self, patient_id: str, source: str, data: dict):
        """Adiciona entrada ao histórico de análises."""
        if patient_id not in self._analysis_history:
            self._analysis_history[patient_id] = []

        self._analysis_history[patient_id].append({
            "source": source,
            "data": data,
        })

        # Limita histórico a 1000 entradas por paciente
        if len(self._analysis_history[patient_id]) > 1000:
            self._analysis_history[patient_id] = self._analysis_history[patient_id][-1000:]

    def get_patient_status(self, patient_id: str) -> PatientStatus:
        """
        Retorna status consolidado do paciente.

        Args:
            patient_id: ID do paciente

        Returns:
            Status atual do paciente
        """
        risk_level = self._determine_risk_level(patient_id)
        alert_summary = self.alert_system.get_patient_summary(patient_id)

        # Determina status de cada componente
        vital_signs_alerts = self.alert_system.get_patient_alerts(
            patient_id, source_filter=[AlertSource.VITAL_SIGNS]
        )
        prescription_alerts = self.alert_system.get_patient_alerts(
            patient_id, source_filter=[AlertSource.PRESCRIPTION]
        )
        audio_alerts = self.alert_system.get_patient_alerts(
            patient_id, source_filter=[AlertSource.AUDIO_ANALYSIS]
        )

        vs_status = "OK" if not vital_signs_alerts else f"{len(vital_signs_alerts)} alertas"
        rx_status = "OK" if not prescription_alerts else f"{len(prescription_alerts)} alertas"
        audio_status = "OK" if not audio_alerts else f"{len(audio_alerts)} alertas"

        # Gera resumo
        summary_parts = []
        if alert_summary.critical_count > 0:
            summary_parts.append(f"{alert_summary.critical_count} alerta(s) CRÍTICO(S)")
        if alert_summary.high_count > 0:
            summary_parts.append(f"{alert_summary.high_count} alerta(s) de alta prioridade")
        if not summary_parts:
            summary_parts.append("Paciente estável, sem alertas críticos")

        status = PatientStatus(
            patient_id=patient_id,
            risk_level=risk_level,
            last_update=datetime.now(),
            vital_signs_status=vs_status,
            prescription_status=rx_status,
            audio_analysis_status=audio_status,
            video_analysis_status="Não integrado" if self.video_analyzer is None else "OK",
            active_alerts_count=alert_summary.unresolved_count,
            critical_alerts_count=alert_summary.critical_count,
            summary="; ".join(summary_parts),
        )

        self._patient_status[patient_id] = status
        return status

    def get_all_monitored_patients(self) -> list[str]:
        """Retorna lista de pacientes monitorados."""
        return list(self._analysis_history.keys())

    def get_patient_history(
        self, patient_id: str, source_filter: Optional[str] = None
    ) -> list[dict]:
        """
        Retorna histórico de análises do paciente.

        Args:
            patient_id: ID do paciente
            source_filter: Filtrar por fonte (vital_signs, prescription, audio, video)

        Returns:
            Lista de entradas do histórico
        """
        history = self._analysis_history.get(patient_id, [])

        if source_filter:
            history = [h for h in history if h["source"] == source_filter]

        return history

    def generate_patient_report(self, patient_id: str) -> dict:
        """
        Gera relatório completo do paciente.

        Args:
            patient_id: ID do paciente

        Returns:
            Relatório consolidado
        """
        status = self.get_patient_status(patient_id)
        alert_summary = self.alert_system.get_patient_summary(patient_id)
        prescription_report = self.prescription_analyzer.generate_report(patient_id)
        history = self.get_patient_history(patient_id)

        return {
            "patient_id": patient_id,
            "report_timestamp": datetime.now().isoformat(),
            "current_status": {
                "risk_level": status.risk_level.value,
                "vital_signs": status.vital_signs_status,
                "prescriptions": status.prescription_status,
                "audio_analysis": status.audio_analysis_status,
                "video_analysis": status.video_analysis_status,
                "summary": status.summary,
            },
            "alerts": {
                "total": alert_summary.total_alerts,
                "critical": alert_summary.critical_count,
                "high": alert_summary.high_count,
                "medium": alert_summary.medium_count,
                "low": alert_summary.low_count,
                "unresolved": alert_summary.unresolved_count,
            },
            "prescription_evolution": prescription_report,
            "analysis_count": {
                "vital_signs": len([h for h in history if h["source"] == "vital_signs"]),
                "prescriptions": len([h for h in history if h["source"] == "prescription"]),
                "audio": len([h for h in history if h["source"] == "audio_analysis"]),
                "video": len([h for h in history if h["source"] == "video_analysis"]),
            },
        }

    def export_monitoring_data(self, patient_id: Optional[str] = None) -> str:
        """
        Exporta dados de monitoramento em JSON.

        Args:
            patient_id: ID do paciente (None para todos)

        Returns:
            JSON com dados de monitoramento
        """
        if patient_id:
            data = {
                "patient": self.generate_patient_report(patient_id),
                "alerts": json.loads(self.alert_system.export_alerts_json(patient_id)),
            }
        else:
            data = {
                "patients": [
                    self.generate_patient_report(pid)
                    for pid in self.get_all_monitored_patients()
                ],
                "shift_report": self.alert_system.generate_shift_report(),
            }

        return json.dumps(data, indent=2, ensure_ascii=False)
