"""
Analisador de Evolução de Prescrições Médicas.

Detecta anomalias em:
- Alterações inesperadas de dosagem
- Interações medicamentosas perigosas
- Mudanças bruscas no tratamento
- Padrões atípicos de prescrição

Referências:
- Regras de interação medicamentosa baseadas em literatura farmacológica
- Detecção de outliers em séries temporais de dosagem
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class PrescriptionAlertType(Enum):
    """Tipos de alertas de prescrição."""
    DOSAGE_INCREASE = "AUMENTO_DOSAGEM"
    DOSAGE_DECREASE = "REDUCAO_DOSAGEM"
    NEW_MEDICATION = "NOVO_MEDICAMENTO"
    MEDICATION_STOPPED = "MEDICAMENTO_SUSPENSO"
    DRUG_INTERACTION = "INTERACAO_MEDICAMENTOSA"
    DUPLICATE_THERAPY = "TERAPIA_DUPLICADA"
    FREQUENCY_CHANGE = "ALTERACAO_FREQUENCIA"


class InteractionSeverity(Enum):
    """Severidade de interações medicamentosas."""
    NONE = "NENHUMA"
    MINOR = "LEVE"
    MODERATE = "MODERADA"
    MAJOR = "GRAVE"
    CONTRAINDICATED = "CONTRAINDICADA"


@dataclass
class Medication:
    """Representa um medicamento prescrito."""
    name: str
    dosage: float
    unit: str  # mg, ml, UI, etc.
    frequency: str  # 1x/dia, 2x/dia, 8/8h, etc.
    route: str = "oral"  # oral, IV, IM, SC, etc.
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    prescriber: Optional[str] = None


@dataclass
class Prescription:
    """Representa uma prescrição médica completa."""
    prescription_id: str
    patient_id: str
    timestamp: datetime
    medications: list[Medication]
    notes: Optional[str] = None


@dataclass
class PrescriptionAlert:
    """Alerta gerado pela análise de prescrição."""
    alert_type: PrescriptionAlertType
    severity: InteractionSeverity
    medication_name: str
    message: str
    details: dict = field(default_factory=dict)
    recommendation: str = ""


# Base de conhecimento simplificada de interações medicamentosas
# Em produção, usar banco de dados completo (ex: DrugBank, Micromedex)
DRUG_INTERACTIONS = {
    ("varfarina", "aspirina"): {
        "severity": InteractionSeverity.MAJOR,
        "effect": "Aumento do risco de sangramento",
        "recommendation": "Monitorar INR frequentemente. Considerar alternativas.",
    },
    ("metformina", "contraste_iodado"): {
        "severity": InteractionSeverity.MAJOR,
        "effect": "Risco de acidose láctica",
        "recommendation": "Suspender metformina 48h antes do exame.",
    },
    ("inibidor_eca", "espironolactona"): {
        "severity": InteractionSeverity.MODERATE,
        "effect": "Risco de hipercalemia",
        "recommendation": "Monitorar potássio sérico.",
    },
    ("omeprazol", "clopidogrel"): {
        "severity": InteractionSeverity.MODERATE,
        "effect": "Redução da eficácia do clopidogrel",
        "recommendation": "Considerar pantoprazol como alternativa.",
    },
    ("ciprofloxacino", "teofilina"): {
        "severity": InteractionSeverity.MAJOR,
        "effect": "Aumento dos níveis de teofilina - risco de toxicidade",
        "recommendation": "Reduzir dose de teofilina ou usar outro antibiótico.",
    },
    ("fluoxetina", "tramadol"): {
        "severity": InteractionSeverity.MAJOR,
        "effect": "Risco de síndrome serotoninérgica",
        "recommendation": "Evitar combinação. Usar analgésico alternativo.",
    },
    ("metoclopramida", "levodopa"): {
        "severity": InteractionSeverity.MODERATE,
        "effect": "Antagonismo dos efeitos da levodopa",
        "recommendation": "Usar domperidona como alternativa antiemética.",
    },
    ("digoxina", "amiodarona"): {
        "severity": InteractionSeverity.MAJOR,
        "effect": "Aumento dos níveis de digoxina",
        "recommendation": "Reduzir dose de digoxina em 50%. Monitorar níveis.",
    },
}

# Classes terapêuticas para detecção de terapia duplicada
THERAPEUTIC_CLASSES = {
    "anti-hipertensivos": ["enalapril", "losartana", "anlodipino", "atenolol", "captopril"],
    "estatinas": ["atorvastatina", "sinvastatina", "rosuvastatina", "pravastatina"],
    "anticoagulantes": ["varfarina", "rivaroxabana", "apixabana", "enoxaparina"],
    "antidepressivos_isrs": ["fluoxetina", "sertralina", "paroxetina", "escitalopram"],
    "benzodiazepinicos": ["diazepam", "clonazepam", "alprazolam", "lorazepam"],
    "inibidores_bomba_protons": ["omeprazol", "pantoprazol", "esomeprazol", "lansoprazol"],
}

# Limites de dosagem (simplificado - em produção usar base completa)
DOSAGE_LIMITS = {
    "metformina": {"min": 500, "max": 2550, "unit": "mg"},
    "atorvastatina": {"min": 10, "max": 80, "unit": "mg"},
    "omeprazol": {"min": 20, "max": 40, "unit": "mg"},
    "losartana": {"min": 25, "max": 100, "unit": "mg"},
    "enalapril": {"min": 5, "max": 40, "unit": "mg"},
    "furosemida": {"min": 20, "max": 600, "unit": "mg"},
    "digoxina": {"min": 0.0625, "max": 0.25, "unit": "mg"},
}


class PrescriptionAnalyzer:
    """
    Analisador de prescrições médicas para detecção de anomalias.

    Funcionalidades:
    1. Detecta mudanças bruscas de dosagem
    2. Identifica interações medicamentosas
    3. Alerta sobre terapias duplicadas
    4. Verifica limites de dosagem
    5. Rastreia evolução do tratamento
    """

    def __init__(self, dosage_change_threshold: float = 0.5):
        """
        Inicializa o analisador.

        Args:
            dosage_change_threshold: Variação percentual para alertar (default 50%)
        """
        self.dosage_change_threshold = dosage_change_threshold
        self.prescription_history: dict[str, list[Prescription]] = {}

    def _normalize_drug_name(self, name: str) -> str:
        """Normaliza nome do medicamento para comparação."""
        return name.lower().strip().replace("-", "_").replace(" ", "_")

    def _check_drug_interactions(
        self, medications: list[Medication]
    ) -> list[PrescriptionAlert]:
        """Verifica interações medicamentosas entre os medicamentos da prescrição."""
        alerts = []
        drug_names = [self._normalize_drug_name(m.name) for m in medications]

        for i, drug1 in enumerate(drug_names):
            for drug2 in drug_names[i + 1:]:
                # Verifica ambas as direções
                key1 = (drug1, drug2)
                key2 = (drug2, drug1)

                interaction = DRUG_INTERACTIONS.get(key1) or DRUG_INTERACTIONS.get(key2)

                if interaction:
                    alerts.append(
                        PrescriptionAlert(
                            alert_type=PrescriptionAlertType.DRUG_INTERACTION,
                            severity=interaction["severity"],
                            medication_name=f"{drug1} + {drug2}",
                            message=f"Interação detectada: {interaction['effect']}",
                            details={"drugs": [drug1, drug2]},
                            recommendation=interaction["recommendation"],
                        )
                    )

        return alerts

    def _check_duplicate_therapy(
        self, medications: list[Medication]
    ) -> list[PrescriptionAlert]:
        """Detecta prescrição de múltiplos medicamentos da mesma classe."""
        alerts = []
        drug_names = [self._normalize_drug_name(m.name) for m in medications]

        for class_name, drugs in THERAPEUTIC_CLASSES.items():
            matches = [d for d in drug_names if d in drugs]
            if len(matches) > 1:
                alerts.append(
                    PrescriptionAlert(
                        alert_type=PrescriptionAlertType.DUPLICATE_THERAPY,
                        severity=InteractionSeverity.MODERATE,
                        medication_name=", ".join(matches),
                        message=f"Terapia duplicada: múltiplos {class_name}",
                        details={"class": class_name, "drugs": matches},
                        recommendation=f"Avaliar necessidade de múltiplos {class_name}.",
                    )
                )

        return alerts

    def _check_dosage_limits(
        self, medications: list[Medication]
    ) -> list[PrescriptionAlert]:
        """Verifica se dosagens estão dentro dos limites seguros."""
        alerts = []

        for med in medications:
            drug_name = self._normalize_drug_name(med.name)
            limits = DOSAGE_LIMITS.get(drug_name)

            if limits and med.unit.lower() == limits["unit"].lower():
                if med.dosage < limits["min"]:
                    alerts.append(
                        PrescriptionAlert(
                            alert_type=PrescriptionAlertType.DOSAGE_DECREASE,
                            severity=InteractionSeverity.MINOR,
                            medication_name=med.name,
                            message=f"Dosagem abaixo do mínimo usual ({limits['min']}{limits['unit']})",
                            details={
                                "current": med.dosage,
                                "min": limits["min"],
                                "max": limits["max"],
                            },
                            recommendation="Verificar se dose subterapêutica é intencional.",
                        )
                    )
                elif med.dosage > limits["max"]:
                    alerts.append(
                        PrescriptionAlert(
                            alert_type=PrescriptionAlertType.DOSAGE_INCREASE,
                            severity=InteractionSeverity.MAJOR,
                            medication_name=med.name,
                            message=f"Dosagem acima do máximo recomendado ({limits['max']}{limits['unit']})",
                            details={
                                "current": med.dosage,
                                "min": limits["min"],
                                "max": limits["max"],
                            },
                            recommendation="Risco de toxicidade. Revisar dosagem.",
                        )
                    )

        return alerts

    def _compare_with_previous(
        self, current: Prescription, previous: Prescription
    ) -> list[PrescriptionAlert]:
        """Compara prescrição atual com a anterior para detectar mudanças."""
        alerts = []

        current_meds = {self._normalize_drug_name(m.name): m for m in current.medications}
        previous_meds = {self._normalize_drug_name(m.name): m for m in previous.medications}

        # Novos medicamentos
        for name, med in current_meds.items():
            if name not in previous_meds:
                alerts.append(
                    PrescriptionAlert(
                        alert_type=PrescriptionAlertType.NEW_MEDICATION,
                        severity=InteractionSeverity.MINOR,
                        medication_name=med.name,
                        message=f"Novo medicamento adicionado: {med.name} {med.dosage}{med.unit}",
                        details={"dosage": med.dosage, "frequency": med.frequency},
                        recommendation="Verificar indicação e monitorar resposta.",
                    )
                )

        # Medicamentos suspensos
        for name, med in previous_meds.items():
            if name not in current_meds:
                alerts.append(
                    PrescriptionAlert(
                        alert_type=PrescriptionAlertType.MEDICATION_STOPPED,
                        severity=InteractionSeverity.MINOR,
                        medication_name=med.name,
                        message=f"Medicamento suspenso: {med.name}",
                        details={"previous_dosage": med.dosage},
                        recommendation="Confirmar se suspensão é intencional.",
                    )
                )

        # Mudanças de dosagem
        for name, current_med in current_meds.items():
            if name in previous_meds:
                prev_med = previous_meds[name]
                if prev_med.dosage > 0:
                    change_ratio = abs(current_med.dosage - prev_med.dosage) / prev_med.dosage

                    if change_ratio > self.dosage_change_threshold:
                        direction = (
                            "aumento" if current_med.dosage > prev_med.dosage else "redução"
                        )
                        alerts.append(
                            PrescriptionAlert(
                                alert_type=(
                                    PrescriptionAlertType.DOSAGE_INCREASE
                                    if direction == "aumento"
                                    else PrescriptionAlertType.DOSAGE_DECREASE
                                ),
                                severity=InteractionSeverity.MODERATE,
                                medication_name=current_med.name,
                                message=f"Mudança brusca de dosagem ({direction} de {change_ratio*100:.0f}%)",
                                details={
                                    "previous": prev_med.dosage,
                                    "current": current_med.dosage,
                                    "change_percent": change_ratio * 100,
                                },
                                recommendation=f"Confirmar {direction} intencional de {prev_med.dosage} para {current_med.dosage}{current_med.unit}.",
                            )
                        )

        return alerts

    def analyze_prescription(
        self, prescription: Prescription
    ) -> list[PrescriptionAlert]:
        """
        Analisa uma prescrição e retorna todos os alertas detectados.

        Args:
            prescription: Prescrição a ser analisada

        Returns:
            Lista de alertas de prescrição
        """
        alerts = []

        # 1. Verifica interações medicamentosas
        alerts.extend(self._check_drug_interactions(prescription.medications))

        # 2. Verifica terapia duplicada
        alerts.extend(self._check_duplicate_therapy(prescription.medications))

        # 3. Verifica limites de dosagem
        alerts.extend(self._check_dosage_limits(prescription.medications))

        # 4. Compara com prescrição anterior (se houver)
        patient_history = self.prescription_history.get(prescription.patient_id, [])
        if patient_history:
            previous = patient_history[-1]
            alerts.extend(self._compare_with_previous(prescription, previous))

        # Adiciona ao histórico
        if prescription.patient_id not in self.prescription_history:
            self.prescription_history[prescription.patient_id] = []
        self.prescription_history[prescription.patient_id].append(prescription)

        return alerts

    def get_patient_medication_timeline(self, patient_id: str) -> list[dict]:
        """Retorna timeline de medicamentos de um paciente."""
        history = self.prescription_history.get(patient_id, [])
        timeline = []

        for prescription in history:
            timeline.append({
                "prescription_id": prescription.prescription_id,
                "timestamp": prescription.timestamp.isoformat(),
                "medications": [
                    {
                        "name": m.name,
                        "dosage": f"{m.dosage}{m.unit}",
                        "frequency": m.frequency,
                    }
                    for m in prescription.medications
                ],
            })

        return timeline

    def generate_report(self, patient_id: str) -> dict:
        """Gera relatório completo da evolução de prescrições do paciente."""
        history = self.prescription_history.get(patient_id, [])

        if not history:
            return {"patient_id": patient_id, "status": "Sem histórico de prescrições"}

        all_medications = set()
        all_alerts = []

        for i, prescription in enumerate(history):
            for med in prescription.medications:
                all_medications.add(med.name)

            if i > 0:
                alerts = self._compare_with_previous(prescription, history[i - 1])
                for alert in alerts:
                    all_alerts.append({
                        "timestamp": prescription.timestamp.isoformat(),
                        "type": alert.alert_type.value,
                        "medication": alert.medication_name,
                        "message": alert.message,
                    })

        return {
            "patient_id": patient_id,
            "total_prescriptions": len(history),
            "first_prescription": history[0].timestamp.isoformat(),
            "last_prescription": history[-1].timestamp.isoformat(),
            "all_medications_used": list(all_medications),
            "change_alerts": all_alerts,
            "current_medications": [
                {"name": m.name, "dosage": f"{m.dosage}{m.unit}", "frequency": m.frequency}
                for m in history[-1].medications
            ],
        }
