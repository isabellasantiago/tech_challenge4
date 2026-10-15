"""
Sistema de Alertas Automáticos para Equipe Médica.

Centraliza e gerencia alertas de múltiplas fontes:
- Sinais vitais
- Prescrições
- Análise de áudio
- Análise de vídeo (preparado para integração futura)

Funcionalidades:
- Priorização de alertas por severidade
- Consolidação de alertas por paciente
- Histórico de alertas
- Notificações configuráveis
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Callable
import threading
import queue


class AlertSource(Enum):
    """Fonte do alerta."""
    VITAL_SIGNS = "SINAIS_VITAIS"
    PRESCRIPTION = "PRESCRICAO"
    AUDIO_ANALYSIS = "ANALISE_AUDIO"
    VIDEO_ANALYSIS = "ANALISE_VIDEO"
    MOVEMENT_PATTERN = "PADRAO_MOVIMENTACAO"
    MANUAL = "MANUAL"


class AlertPriority(Enum):
    """Prioridade do alerta para triagem."""
    P1_CRITICAL = 1  # Atenção imediata
    P2_HIGH = 2  # Atenção urgente (< 15 min)
    P3_MEDIUM = 3  # Atenção em até 1 hora
    P4_LOW = 4  # Atenção em até 4 horas
    P5_INFO = 5  # Informativo


class AlertStatus(Enum):
    """Status do alerta."""
    NEW = "NOVO"
    ACKNOWLEDGED = "RECONHECIDO"
    IN_PROGRESS = "EM_ANDAMENTO"
    RESOLVED = "RESOLVIDO"
    ESCALATED = "ESCALADO"
    DISMISSED = "DISPENSADO"


@dataclass
class MedicalAlert:
    """Representa um alerta médico."""
    alert_id: str
    patient_id: str
    source: AlertSource
    priority: AlertPriority
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    status: AlertStatus = AlertStatus.NEW
    details: dict = field(default_factory=dict)
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None


@dataclass
class PatientAlertSummary:
    """Resumo de alertas de um paciente."""
    patient_id: str
    total_alerts: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    unresolved_count: int
    latest_alert: Optional[MedicalAlert]
    all_alerts: list[MedicalAlert]


class AlertSystem:
    """
    Sistema centralizado de alertas médicos.

    Gerencia alertas de múltiplas fontes com:
    - Fila de prioridade
    - Callbacks para notificações
    - Histórico persistente
    - Consolidação por paciente
    """

    def __init__(self):
        self._alerts: dict[str, MedicalAlert] = {}
        self._patient_alerts: dict[str, list[str]] = {}  # patient_id -> [alert_ids]
        self._alert_counter = 0
        self._lock = threading.Lock()
        self._alert_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._callbacks: list[Callable[[MedicalAlert], None]] = []

    def _generate_alert_id(self) -> str:
        """Gera ID único para o alerta."""
        with self._lock:
            self._alert_counter += 1
            return f"ALT-{datetime.now().strftime('%Y%m%d')}-{self._alert_counter:05d}"

    def _map_severity_to_priority(self, severity: str) -> AlertPriority:
        """Mapeia severidade de outras fontes para prioridade de alerta."""
        mapping = {
            "CRITICO": AlertPriority.P1_CRITICAL,
            "CRITICAL": AlertPriority.P1_CRITICAL,
            "ALTO": AlertPriority.P2_HIGH,
            "HIGH": AlertPriority.P2_HIGH,
            "GRAVE": AlertPriority.P2_HIGH,
            "MAJOR": AlertPriority.P2_HIGH,
            "MEDIO": AlertPriority.P3_MEDIUM,
            "MEDIUM": AlertPriority.P3_MEDIUM,
            "MODERADA": AlertPriority.P3_MEDIUM,
            "MODERATE": AlertPriority.P3_MEDIUM,
            "BAIXO": AlertPriority.P4_LOW,
            "LOW": AlertPriority.P4_LOW,
            "LEVE": AlertPriority.P4_LOW,
            "MINOR": AlertPriority.P4_LOW,
            "NORMAL": AlertPriority.P5_INFO,
            "INFO": AlertPriority.P5_INFO,
        }
        return mapping.get(severity.upper(), AlertPriority.P3_MEDIUM)

    def register_callback(self, callback: Callable[[MedicalAlert], None]):
        """Registra callback para ser chamado quando novo alerta é criado."""
        self._callbacks.append(callback)

    def create_alert(
        self,
        patient_id: str,
        source: AlertSource,
        title: str,
        message: str,
        priority: Optional[AlertPriority] = None,
        severity: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> MedicalAlert:
        """
        Cria um novo alerta médico.

        Args:
            patient_id: ID do paciente
            source: Fonte do alerta
            title: Título curto do alerta
            message: Mensagem detalhada
            priority: Prioridade (se não fornecida, usa severity)
            severity: Severidade para mapear para prioridade
            details: Detalhes adicionais

        Returns:
            Alerta criado
        """
        alert_id = self._generate_alert_id()

        if priority is None:
            priority = self._map_severity_to_priority(severity or "MEDIUM")

        alert = MedicalAlert(
            alert_id=alert_id,
            patient_id=patient_id,
            source=source,
            priority=priority,
            title=title,
            message=message,
            details=details or {},
        )

        with self._lock:
            self._alerts[alert_id] = alert

            if patient_id not in self._patient_alerts:
                self._patient_alerts[patient_id] = []
            self._patient_alerts[patient_id].append(alert_id)

            # Adiciona à fila de prioridade
            self._alert_queue.put((priority.value, alert.timestamp, alert_id))

        # Notifica callbacks
        for callback in self._callbacks:
            try:
                callback(alert)
            except Exception:
                pass  # Não interrompe por erro em callback

        return alert

    def create_alert_from_vital_signs(
        self, patient_id: str, anomaly_result: dict
    ) -> Optional[MedicalAlert]:
        """Cria alerta a partir de resultado de análise de sinais vitais."""
        if not anomaly_result.get("is_anomaly", False):
            return None

        return self.create_alert(
            patient_id=patient_id,
            source=AlertSource.VITAL_SIGNS,
            title=f"Anomalia em {anomaly_result.get('metric_name', 'sinal vital')}",
            message=anomaly_result.get("message", ""),
            severity=anomaly_result.get("severity", "MEDIUM"),
            details={
                "metric": anomaly_result.get("metric_name"),
                "value": anomaly_result.get("current_value"),
                "expected_range": anomaly_result.get("expected_range"),
                "z_score": anomaly_result.get("z_score"),
            },
        )

    def create_alert_from_prescription(
        self, patient_id: str, prescription_alert: dict
    ) -> MedicalAlert:
        """Cria alerta a partir de resultado de análise de prescrição."""
        return self.create_alert(
            patient_id=patient_id,
            source=AlertSource.PRESCRIPTION,
            title=f"{prescription_alert.get('alert_type', 'Alerta de prescrição')}",
            message=prescription_alert.get("message", ""),
            severity=prescription_alert.get("severity", "MEDIUM"),
            details={
                "medication": prescription_alert.get("medication_name"),
                "recommendation": prescription_alert.get("recommendation"),
                **prescription_alert.get("details", {}),
            },
        )

    def create_alert_from_audio_analysis(
        self, patient_id: str, audio_result: dict
    ) -> Optional[MedicalAlert]:
        """Cria alerta a partir de resultado de análise de áudio."""
        risk_level = audio_result.get("multimodal_risk_assessment", {}).get(
            "overall_risk", "BAIXO"
        )

        if risk_level in ["BAIXO", "LOW"]:
            return None

        return self.create_alert(
            patient_id=patient_id,
            source=AlertSource.AUDIO_ANALYSIS,
            title="Alerta de análise vocal",
            message=audio_result.get("multimodal_risk_assessment", {}).get(
                "justification", ""
            ),
            severity=risk_level,
            details={
                "text_risk_level": audio_result.get("text_risk_level"),
                "identified_symptoms": audio_result.get("identified_symptoms", []),
                "clinical_recommendation": audio_result.get("clinical_recommendation"),
            },
        )

    def acknowledge_alert(self, alert_id: str, user_id: str) -> bool:
        """Marca alerta como reconhecido."""
        with self._lock:
            if alert_id not in self._alerts:
                return False

            alert = self._alerts[alert_id]
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_by = user_id
            alert.acknowledged_at = datetime.now()
            return True

    def resolve_alert(
        self, alert_id: str, user_id: str, resolution_notes: str = ""
    ) -> bool:
        """Marca alerta como resolvido."""
        with self._lock:
            if alert_id not in self._alerts:
                return False

            alert = self._alerts[alert_id]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_by = user_id
            alert.resolved_at = datetime.now()
            alert.resolution_notes = resolution_notes
            return True

    def escalate_alert(self, alert_id: str) -> bool:
        """Escala alerta para prioridade mais alta."""
        with self._lock:
            if alert_id not in self._alerts:
                return False

            alert = self._alerts[alert_id]
            alert.status = AlertStatus.ESCALATED

            # Aumenta prioridade
            if alert.priority.value > 1:
                new_priority = AlertPriority(alert.priority.value - 1)
                alert.priority = new_priority

            return True

    def get_alert(self, alert_id: str) -> Optional[MedicalAlert]:
        """Retorna alerta pelo ID."""
        return self._alerts.get(alert_id)

    def get_patient_alerts(
        self,
        patient_id: str,
        status_filter: Optional[list[AlertStatus]] = None,
        source_filter: Optional[list[AlertSource]] = None,
    ) -> list[MedicalAlert]:
        """Retorna alertas de um paciente com filtros opcionais."""
        alert_ids = self._patient_alerts.get(patient_id, [])
        alerts = [self._alerts[aid] for aid in alert_ids if aid in self._alerts]

        if status_filter:
            alerts = [a for a in alerts if a.status in status_filter]

        if source_filter:
            alerts = [a for a in alerts if a.source in source_filter]

        # Ordena por prioridade e timestamp
        alerts.sort(key=lambda a: (a.priority.value, a.timestamp))

        return alerts

    def get_patient_summary(self, patient_id: str) -> PatientAlertSummary:
        """Retorna resumo de alertas do paciente."""
        alerts = self.get_patient_alerts(patient_id)

        unresolved = [
            a for a in alerts if a.status not in [AlertStatus.RESOLVED, AlertStatus.DISMISSED]
        ]

        return PatientAlertSummary(
            patient_id=patient_id,
            total_alerts=len(alerts),
            critical_count=sum(1 for a in alerts if a.priority == AlertPriority.P1_CRITICAL),
            high_count=sum(1 for a in alerts if a.priority == AlertPriority.P2_HIGH),
            medium_count=sum(1 for a in alerts if a.priority == AlertPriority.P3_MEDIUM),
            low_count=sum(1 for a in alerts if a.priority == AlertPriority.P4_LOW),
            unresolved_count=len(unresolved),
            latest_alert=alerts[-1] if alerts else None,
            all_alerts=alerts,
        )

    def get_pending_alerts(self, max_count: int = 10) -> list[MedicalAlert]:
        """Retorna alertas pendentes em ordem de prioridade."""
        pending = [
            a for a in self._alerts.values()
            if a.status in [AlertStatus.NEW, AlertStatus.ACKNOWLEDGED, AlertStatus.IN_PROGRESS]
        ]

        # Ordena por prioridade e timestamp
        pending.sort(key=lambda a: (a.priority.value, a.timestamp))

        return pending[:max_count]

    def get_critical_alerts(self) -> list[MedicalAlert]:
        """Retorna todos os alertas críticos não resolvidos."""
        return [
            a for a in self._alerts.values()
            if a.priority == AlertPriority.P1_CRITICAL
            and a.status not in [AlertStatus.RESOLVED, AlertStatus.DISMISSED]
        ]

    def generate_shift_report(self) -> dict:
        """Gera relatório para passagem de plantão."""
        all_alerts = list(self._alerts.values())

        # Alertas das últimas 12 horas (aproximado)
        recent_alerts = [a for a in all_alerts]  # Em produção, filtrar por timestamp

        return {
            "report_timestamp": datetime.now().isoformat(),
            "total_alerts": len(all_alerts),
            "critical_pending": len([
                a for a in all_alerts
                if a.priority == AlertPriority.P1_CRITICAL
                and a.status not in [AlertStatus.RESOLVED, AlertStatus.DISMISSED]
            ]),
            "high_pending": len([
                a for a in all_alerts
                if a.priority == AlertPriority.P2_HIGH
                and a.status not in [AlertStatus.RESOLVED, AlertStatus.DISMISSED]
            ]),
            "patients_with_alerts": list(self._patient_alerts.keys()),
            "alerts_by_source": {
                source.value: len([a for a in all_alerts if a.source == source])
                for source in AlertSource
            },
            "recent_critical": [
                {
                    "alert_id": a.alert_id,
                    "patient_id": a.patient_id,
                    "title": a.title,
                    "status": a.status.value,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in sorted(
                    [a for a in all_alerts if a.priority == AlertPriority.P1_CRITICAL],
                    key=lambda x: x.timestamp,
                    reverse=True,
                )[:5]
            ],
        }

    def export_alerts_json(self, patient_id: Optional[str] = None) -> str:
        """Exporta alertas em formato JSON."""
        if patient_id:
            alerts = self.get_patient_alerts(patient_id)
        else:
            alerts = list(self._alerts.values())

        return json.dumps(
            [
                {
                    "alert_id": a.alert_id,
                    "patient_id": a.patient_id,
                    "source": a.source.value,
                    "priority": a.priority.name,
                    "title": a.title,
                    "message": a.message,
                    "status": a.status.value,
                    "timestamp": a.timestamp.isoformat(),
                    "details": a.details,
                }
                for a in alerts
            ],
            indent=2,
            ensure_ascii=False,
        )
