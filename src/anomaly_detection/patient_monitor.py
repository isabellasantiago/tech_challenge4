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
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from dataclasses import asdict
from .video_integration import VideoAnalyzerProtocol, VideoAnalysisResult
from enum import Enum

from .vital_signs_detector import VitalSignsAnomalyDetector, VitalSignsReading
from .prescription_analyzer import PrescriptionAnalyzer, Prescription
from .alert_system import AlertSystem, AlertSource, MedicalAlert, AlertStatus


class PatientRiskLevel(Enum):
    """Nível de risco geral do paciente."""
    INDETERMINATE = "INDETERMINADO"
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


class PatientMonitor:
    """
    Monitor central de pacientes.

    Orquestra a análise de múltiplas fontes de dados e consolida
    o estado de saúde do paciente por execução.
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
        alerts = [a for a in self.alert_system.get_patient_alerts(patient_id)
                  if not a.simulated and a.status not in {AlertStatus.RESOLVED, AlertStatus.DISMISSED}]
        priority = min((a.priority.value for a in alerts), default=None)
        if priority == 1:
            return PatientRiskLevel.CRITICAL
        if priority == 2:
            return PatientRiskLevel.WARNING
        if priority in {3, 4}:
            return PatientRiskLevel.ATTENTION
        if not alerts and not self.evaluation_complete(patient_id):
            return PatientRiskLevel.INDETERMINATE
        return PatientRiskLevel.STABLE

    def modality_states(self, patient_id: str) -> dict:
        states = {}
        for source in ("audio_analysis", "video_analysis", "vital_signs", "prescription"):
            entries = [item["data"] for item in self.get_patient_history(patient_id, source)]
            statuses = [item.get("status", "CONCLUIDA") for item in entries]
            if not statuses:
                states[source] = "NAO_INTEGRADO" if source == "video_analysis" else "AUSENTE"
            elif "FALHA" in statuses:
                states[source] = "FALHA"
            elif "PARCIAL" in statuses:
                states[source] = "PARCIAL"
            elif source == "prescription" and len(entries) < 2:
                states[source] = "PARCIAL"
            else:
                states[source] = statuses[-1]
        return states

    def evaluation_complete(self, patient_id: str) -> bool:
        return all(value == "CONCLUIDA" for value in self.modality_states(patient_id).values())

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
                        "timestamp": reading.timestamp.isoformat(),
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
                "status": "PARCIAL" if self.vital_signs_detector.last_data_errors else "CONCLUIDA",
                "data_errors": list(self.vital_signs_detector.last_data_errors),
                "results": [{**asdict(a), "severity": a.severity.value} for a in anomalies],
                "anomalies_detected": len([a for a in anomalies if a.is_anomaly]),
                "readings": {a.metric_name: a.current_value for a in anomalies},
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
                    "details": {**p_alert.details, "prescription_id": prescription.prescription_id,
                                "timestamp": prescription.timestamp.isoformat(),
                                "rule": "regras locais demonstrativas"},
                },
            )
            alerts.append(alert)

        # Registra no histórico
        self._add_to_history(
            prescription.patient_id,
            "prescription",
            {
                "timestamp": prescription.timestamp.isoformat(),
                "status": "CONCLUIDA",
                "prescription": json.loads(json.dumps(asdict(prescription), default=str)),
                "prescription_id": prescription.prescription_id,
                "medications_count": len(prescription.medications),
                "alerts_generated": len(prescription_alerts),
            },
        )

        return alerts

    def process_audio_analysis(
        self, patient_id: str, audio_result: dict, evidence: Optional[dict] = None
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

        self._add_to_history(patient_id, "audio_analysis", {
            "timestamp": datetime.now().isoformat(),
            "status": "SIMULADA" if audio_result.get("simulated") else "CONCLUIDA",
            "clinical_assessment": audio_result,
            **(evidence or {}),
        })

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
        if not patient_id.strip() or not video_path.strip():
            raise ValueError("patient_id e video_path devem ser não vazios")
        if self.video_analyzer is None:
            self._add_to_history(patient_id, "video_analysis", {
                "status": "NAO_INTEGRADO", "summary": "Módulo de vídeo não integrado",
            })
            return []
        try:
            result = self.video_analyzer.analyze_video(video_path)
            if not isinstance(result, VideoAnalysisResult):
                raise ValueError("analisador interno deve retornar VideoAnalysisResult")
            result = VideoAnalysisResult.from_dict({
                key: value for key, value in asdict(result).items() if value is not None
            })
        except Exception as exc:
            self._add_to_history(patient_id, "video_analysis", {
                "status": "FALHA", "error": str(exc), "video_path": video_path,
            })
            return []
        data = asdict(result)
        data.update(video_path=video_path, timestamp=datetime.now().isoformat())
        self._add_to_history(patient_id, "video_analysis", data)
        alerts = []
        if result.status in {"CONCLUIDA", "SIMULADA"}:
            for finding in result.findings:
                alerts.append(self.alert_system.create_alert(
                    patient_id, AlertSource.VIDEO_ANALYSIS,
                    title=finding["type"], message=finding["description"],
                    severity=finding["severity"],
                    details={**finding, "video_path": video_path},
                    simulated=result.status == "SIMULADA",
                ))
        return alerts

    def record_modality_result(self, patient_id: str, source: str, data: dict):
        """Registra resultados, falhas e evidências de uma modalidade."""
        self._add_to_history(patient_id, source, data)

    def _add_to_history(self, patient_id: str, source: str, data: dict):
        """Adiciona entrada ao histórico de análises."""
        if patient_id not in self._analysis_history:
            self._analysis_history[patient_id] = []

        self._analysis_history[patient_id].append({
            "source": source,
            "data": data,
        })

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

        states = self.modality_states(patient_id)

        # Gera resumo
        summary_parts = [f"Risco real: {risk_level.value}"]
        if not self.evaluation_complete(patient_id):
            summary_parts.append("Avaliação incompleta")

        status = PatientStatus(
            patient_id=patient_id,
            risk_level=risk_level,
            last_update=datetime.now(),
            vital_signs_status=states["vital_signs"],
            prescription_status=states["prescription"],
            audio_analysis_status=states["audio_analysis"],
            video_analysis_status=states["video_analysis"],
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

        complete = self.evaluation_complete(patient_id)
        output_errors = [h["data"] for h in history if h["source"] == "output"]
        findings = {
            name: [h["data"] for h in history if h["source"] == source]
            for name, source in {"audio": "audio_analysis", "video": "video_analysis",
                                 "vital_signs": "vital_signs", "prescriptions": "prescription"}.items()
        }
        limitations = [
            "Protótipo acadêmico: resultados de apoio, sem diagnóstico autônomo.",
            "Console e JSONL locais; nenhuma notificação entregue à equipe médica.",
            "Dados de modalidades diferentes associados a um paciente fictício.",
            "Sinais vitais e prescrições sintéticos; regras farmacológicas limitadas.",
            "Transcrição fornecida pelo DAIC-WOZ; sem transcrição automática ou streaming.",
        ]
        for name, state in self.modality_states(patient_id).items():
            if state != "CONCLUIDA":
                limitations.append(f"{name}: {state}")
        if output_errors:
            limitations.append("Falha operacional ao gravar saídas locais.")
        return {
            "patient_id": patient_id,
            "report_timestamp": datetime.now().isoformat(),
            "execution_status": "COMPLETA" if complete and not output_errors else "PARCIAL",
            "evaluation_complete": complete,
            "findings": findings,
            "limitations": limitations,
            "output_errors": output_errors,
            "alerts": [a.to_dict() for a in self.alert_system.get_patient_alerts(patient_id)],
            "current_status": {
                "risk_level": status.risk_level.value,
                "vital_signs": status.vital_signs_status,
                "prescriptions": status.prescription_status,
                "audio_analysis": status.audio_analysis_status,
                "video_analysis": status.video_analysis_status,
                "summary": status.summary,
            },
            "alert_summary": {
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
