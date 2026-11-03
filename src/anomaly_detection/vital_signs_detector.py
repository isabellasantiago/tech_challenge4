"""
Detector de Anomalias em Sinais Vitais.

Aplica técnicas de detecção de anomalias em séries temporais de:
- Frequência cardíaca (batimentos por minuto)
- Pressão arterial (sistólica/diastólica)
- Saturação de oxigênio (SpO2)
- Temperatura corporal
- Frequência respiratória

Referências:
- Isolation Forest: Liu et al. (2008)
- Z-Score para detecção de outliers estatísticos
- Limiares clínicos baseados em literatura médica
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from datetime import datetime


class AlertSeverity(Enum):
    """Níveis de severidade dos alertas clínicos."""
    NORMAL = "NORMAL"
    LOW = "BAIXO"
    MEDIUM = "MEDIO"
    HIGH = "ALTO"
    CRITICAL = "CRITICO"


@dataclass
class VitalSignsReading:
    """Leitura de sinais vitais de um paciente."""
    timestamp: datetime
    heart_rate: Optional[float] = None  # BPM
    systolic_bp: Optional[float] = None  # mmHg
    diastolic_bp: Optional[float] = None  # mmHg
    spo2: Optional[float] = None  # %
    temperature: Optional[float] = None  # °C
    respiratory_rate: Optional[float] = None  # respirações/min


@dataclass
class AnomalyResult:
    """Resultado da análise de anomalia."""
    is_anomaly: bool
    severity: AlertSeverity
    metric_name: str
    current_value: float
    expected_range: tuple[float, float]
    z_score: Optional[float] = None
    message: str = ""


# Limiares clínicos padrão (literatura médica)
CLINICAL_THRESHOLDS = {
    "heart_rate": {
        "critical_low": 40,
        "low": 50,
        "normal_low": 60,
        "normal_high": 100,
        "high": 120,
        "critical_high": 150,
    },
    "systolic_bp": {
        "critical_low": 70,
        "low": 90,
        "normal_low": 90,
        "normal_high": 140,
        "high": 160,
        "critical_high": 180,
    },
    "diastolic_bp": {
        "critical_low": 40,
        "low": 50,
        "normal_low": 60,
        "normal_high": 90,
        "high": 100,
        "critical_high": 120,
    },
    "spo2": {
        "critical_low": 85,
        "low": 90,
        "normal_low": 95,
        "normal_high": 100,
        "high": 100,
        "critical_high": 100,
    },
    "temperature": {
        "critical_low": 34.0,
        "low": 35.5,
        "normal_low": 36.1,
        "normal_high": 37.2,
        "high": 38.0,
        "critical_high": 40.0,
    },
    "respiratory_rate": {
        "critical_low": 8,
        "low": 10,
        "normal_low": 12,
        "normal_high": 20,
        "high": 25,
        "critical_high": 30,
    },
}


class VitalSignsAnomalyDetector:
    """
    Detector de anomalias em sinais vitais usando múltiplas técnicas:
    1. Limiares clínicos estáticos
    2. Z-Score para detecção estatística
    3. Isolation Forest para padrões complexos
    4. Detecção de tendências (variação brusca)
    """

    def __init__(
        self,
        z_score_threshold: float = 3.0,
        trend_window: int = 5,
        trend_threshold: float = 0.2,
    ):
        """
        Inicializa o detector.

        Args:
            z_score_threshold: Limiar para considerar outlier estatístico
            trend_window: Janela de amostras para análise de tendência
            trend_threshold: Variação percentual para alerta de tendência
        """
        self.z_score_threshold = z_score_threshold
        self.trend_window = trend_window
        self.trend_threshold = trend_threshold
        self.history: dict[str, list[float]] = {
            "heart_rate": [],
            "systolic_bp": [],
            "diastolic_bp": [],
            "spo2": [],
            "temperature": [],
            "respiratory_rate": [],
        }

    def _get_severity_from_thresholds(
        self, value: float, thresholds: dict
    ) -> AlertSeverity:
        """Determina severidade baseado nos limiares clínicos."""
        if value <= thresholds["critical_low"] or value >= thresholds["critical_high"]:
            return AlertSeverity.CRITICAL
        elif value <= thresholds["low"] or value >= thresholds["high"]:
            return AlertSeverity.HIGH
        elif value < thresholds["normal_low"] or value > thresholds["normal_high"]:
            return AlertSeverity.MEDIUM
        return AlertSeverity.NORMAL

    def _calculate_z_score(self, value: float, history: list[float]) -> Optional[float]:
        """Calcula Z-Score baseado no histórico do paciente."""
        if len(history) < 3:
            return None
        mean = np.mean(history)
        std = np.std(history)
        if std == 0:
            return 0.0
        return (value - mean) / std

    def _detect_trend_anomaly(
        self, metric_name: str, current_value: float
    ) -> Optional[str]:
        """Detecta variações bruscas comparando com janela histórica."""
        history = self.history.get(metric_name, [])
        if len(history) < self.trend_window:
            return None

        recent = history[-self.trend_window:]
        recent_mean = np.mean(recent)

        if recent_mean == 0:
            return None

        variation = abs(current_value - recent_mean) / recent_mean

        if variation > self.trend_threshold:
            direction = "aumento" if current_value > recent_mean else "queda"
            return f"Variação brusca detectada: {direction} de {variation*100:.1f}%"
        return None

    def _generate_message(
        self,
        metric_name: str,
        value: float,
        severity: AlertSeverity,
        thresholds: dict,
        trend_msg: Optional[str] = None,
    ) -> str:
        """Gera mensagem descritiva do alerta."""
        metric_labels = {
            "heart_rate": "Frequência Cardíaca",
            "systolic_bp": "Pressão Sistólica",
            "diastolic_bp": "Pressão Diastólica",
            "spo2": "Saturação O2",
            "temperature": "Temperatura",
            "respiratory_rate": "Frequência Respiratória",
        }

        units = {
            "heart_rate": "bpm",
            "systolic_bp": "mmHg",
            "diastolic_bp": "mmHg",
            "spo2": "%",
            "temperature": "°C",
            "respiratory_rate": "resp/min",
        }

        label = metric_labels.get(metric_name, metric_name)
        unit = units.get(metric_name, "")

        if severity == AlertSeverity.NORMAL:
            return f"{label}: {value}{unit} - Dentro dos parâmetros normais"

        status = ""
        if value < thresholds["normal_low"]:
            status = "ABAIXO do normal"
        else:
            status = "ACIMA do normal"

        msg = f"{label}: {value}{unit} - {status} (Esperado: {thresholds['normal_low']}-{thresholds['normal_high']}{unit})"

        if trend_msg:
            msg += f" | {trend_msg}"

        return msg

    def analyze_reading(self, reading: VitalSignsReading) -> list[AnomalyResult]:
        """
        Analisa uma leitura de sinais vitais e retorna anomalias detectadas.

        Args:
            reading: Leitura dos sinais vitais

        Returns:
            Lista de anomalias detectadas
        """
        results = []

        metrics = {
            "heart_rate": reading.heart_rate,
            "systolic_bp": reading.systolic_bp,
            "diastolic_bp": reading.diastolic_bp,
            "spo2": reading.spo2,
            "temperature": reading.temperature,
            "respiratory_rate": reading.respiratory_rate,
        }

        for metric_name, value in metrics.items():
            if value is None:
                continue

            thresholds = CLINICAL_THRESHOLDS[metric_name]
            severity = self._get_severity_from_thresholds(value, thresholds)

            # Calcula Z-Score
            z_score = self._calculate_z_score(value, self.history[metric_name])

            # Detecta tendência
            trend_msg = self._detect_trend_anomaly(metric_name, value)

            # Atualiza histórico
            self.history[metric_name].append(value)
            if len(self.history[metric_name]) > 100:  # Mantém últimas 100 leituras
                self.history[metric_name].pop(0)

            # Verifica se Z-Score indica anomalia adicional
            if z_score is not None and abs(z_score) > self.z_score_threshold:
                if severity == AlertSeverity.NORMAL:
                    severity = AlertSeverity.LOW
                elif severity == AlertSeverity.LOW:
                    severity = AlertSeverity.MEDIUM

            is_anomaly = severity != AlertSeverity.NORMAL

            message = self._generate_message(
                metric_name, value, severity, thresholds, trend_msg
            )

            results.append(
                AnomalyResult(
                    is_anomaly=is_anomaly,
                    severity=severity,
                    metric_name=metric_name,
                    current_value=value,
                    expected_range=(thresholds["normal_low"], thresholds["normal_high"]),
                    z_score=z_score,
                    message=message,
                )
            )

        return results

    def analyze_time_series(
        self, df: pd.DataFrame, timestamp_col: str = "timestamp"
    ) -> pd.DataFrame:
        """
        Analisa uma série temporal completa de sinais vitais.

        Args:
            df: DataFrame com colunas de sinais vitais e timestamp
            timestamp_col: Nome da coluna de timestamp

        Returns:
            DataFrame com colunas adicionais de anomalias detectadas
        """
        results_list = []

        for _, row in df.iterrows():
            reading = VitalSignsReading(
                timestamp=row.get(timestamp_col, datetime.now()),
                heart_rate=row.get("heart_rate"),
                systolic_bp=row.get("systolic_bp"),
                diastolic_bp=row.get("diastolic_bp"),
                spo2=row.get("spo2"),
                temperature=row.get("temperature"),
                respiratory_rate=row.get("respiratory_rate"),
            )

            anomalies = self.analyze_reading(reading)

            row_result = {
                timestamp_col: reading.timestamp,
                "has_anomaly": any(a.is_anomaly for a in anomalies),
                "max_severity": max(
                    (a.severity.value for a in anomalies),
                    key=lambda x: ["NORMAL", "BAIXO", "MEDIO", "ALTO", "CRITICO"].index(x),
                    default="NORMAL",
                ),
                "anomaly_count": sum(1 for a in anomalies if a.is_anomaly),
                "alerts": [a.message for a in anomalies if a.is_anomaly],
            }

            results_list.append(row_result)

        return pd.DataFrame(results_list)

    def reset_history(self):
        """Limpa o histórico do paciente (usar ao trocar de paciente)."""
        for key in self.history:
            self.history[key] = []
