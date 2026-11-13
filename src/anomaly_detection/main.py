"""
Exemplo de uso do módulo de Detecção de Anomalias.

Demonstra o fluxo completo de:
1. Monitoramento de sinais vitais
2. Análise de prescrições
3. Integração com análise de áudio existente
4. Sistema de alertas automáticos

Execute com: python -m anomaly_detection.main
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from .vital_signs_detector import VitalSignsAnomalyDetector, VitalSignsReading
from .prescription_analyzer import (
    PrescriptionAnalyzer,
    Prescription,
    Medication,
)
from .alert_system import AlertSystem, AlertSource
from .patient_monitor import PatientMonitor


def load_demo_vital_readings() -> list[VitalSignsReading]:
    """Carrega a série sintética compartilhada pelos exemplos de sinais vitais."""
    csv_path = Path(__file__).parent / "data" / "sinais_vitais_demo.csv"
    readings_df = pd.read_csv(csv_path, parse_dates=["timestamp"])

    return [
        VitalSignsReading(
            timestamp=row.timestamp.to_pydatetime(),
            heart_rate=float(row.heart_rate),
            systolic_bp=float(row.systolic_bp),
            diastolic_bp=float(row.diastolic_bp),
            spo2=float(row.spo2),
            temperature=float(row.temperature),
            respiratory_rate=float(row.respiratory_rate),
        )
        for row in readings_df.itertuples(index=False)
    ]


def demo_vital_signs_analysis():
    """Demonstra análise de sinais vitais."""
    print("=" * 60)
    print("DEMONSTRAÇÃO: Análise de Sinais Vitais")
    print("=" * 60)

    detector = VitalSignsAnomalyDetector()
    readings = load_demo_vital_readings()

    for i, reading in enumerate(readings, 1):
        print(f"\n--- Leitura {i} | {reading.timestamp.isoformat()} ---")
        results = detector.analyze_reading(reading)

        for result in results:
            status = "⚠️ ANOMALIA" if result.is_anomaly else "✅ Normal"
            print(f"{status} | {result.message}")


def demo_prescription_analysis():
    """Demonstra análise de prescrições."""
    print("\n" + "=" * 60)
    print("DEMONSTRAÇÃO: Análise de Prescrições")
    print("=" * 60)

    analyzer = PrescriptionAnalyzer()

    # Prescrição inicial
    prescription1 = Prescription(
        prescription_id="RX001",
        patient_id="PAC123",
        timestamp=datetime.now() - timedelta(days=7),
        medications=[
            Medication(name="Enalapril", dosage=10, unit="mg", frequency="1x/dia"),
            Medication(name="Metformina", dosage=500, unit="mg", frequency="2x/dia"),
            Medication(name="Omeprazol", dosage=20, unit="mg", frequency="1x/dia"),
        ],
    )

    # Prescrição com alterações
    prescription2 = Prescription(
        prescription_id="RX002",
        patient_id="PAC123",
        timestamp=datetime.now(),
        medications=[
            Medication(name="Enalapril", dosage=40, unit="mg", frequency="1x/dia"),  # Aumento
            Medication(name="Metformina", dosage=500, unit="mg", frequency="2x/dia"),
            Medication(name="Omeprazol", dosage=20, unit="mg", frequency="1x/dia"),
            Medication(name="Clopidogrel", dosage=75, unit="mg", frequency="1x/dia"),  # Novo + Interação
            Medication(name="Varfarina", dosage=5, unit="mg", frequency="1x/dia"),  # Anticoagulante
            Medication(name="Aspirina", dosage=100, unit="mg", frequency="1x/dia"),  # Interação perigosa
        ],
    )

    print("\n--- Análise da Prescrição Inicial ---")
    alerts1 = analyzer.analyze_prescription(prescription1)
    if alerts1:
        for alert in alerts1:
            print(f"⚠️ [{alert.severity.value}] {alert.message}")
            print(f"   Recomendação: {alert.recommendation}")
    else:
        print("✅ Nenhum alerta na prescrição inicial")

    print("\n--- Análise da Nova Prescrição ---")
    alerts2 = analyzer.analyze_prescription(prescription2)
    for alert in alerts2:
        print(f"⚠️ [{alert.severity.value}] {alert.alert_type.value}: {alert.message}")
        print(f"   Recomendação: {alert.recommendation}")

    print("\n--- Relatório de Evolução ---")
    report = analyzer.generate_report("PAC123")
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


def demo_patient_monitor():
    """Demonstra o monitor completo de pacientes."""
    print("\n" + "=" * 60)
    print("DEMONSTRAÇÃO: Monitor de Pacientes")
    print("=" * 60)

    # Cria monitor
    alert_system = AlertSystem()
    monitor = PatientMonitor(alert_system=alert_system)

    patient_id = "PAC456"

    # Processa sinais vitais
    print("\n--- Processando Sinais Vitais ---")
    vital_reading = load_demo_vital_readings()[-1]

    vital_alerts = monitor.process_vital_signs(patient_id, vital_reading)
    print(f"Alertas de sinais vitais: {len(vital_alerts)}")
    for alert in vital_alerts:
        print(f"  - [{alert.priority.name}] {alert.title}: {alert.message}")

    # Processa prescrição
    print("\n--- Processando Prescrição ---")
    prescription = Prescription(
        prescription_id="RX003",
        patient_id=patient_id,
        timestamp=datetime.now(),
        medications=[
            Medication(name="Fluoxetina", dosage=20, unit="mg", frequency="1x/dia"),
            Medication(name="Tramadol", dosage=50, unit="mg", frequency="6/6h"),  # Interação grave
        ],
    )

    rx_alerts = monitor.process_prescription(prescription)
    print(f"Alertas de prescrição: {len(rx_alerts)}")
    for alert in rx_alerts:
        print(f"  - [{alert.priority.name}] {alert.title}: {alert.message}")

    # Simula resultado de análise de áudio (do módulo existente)
    print("\n--- Processando Análise de Áudio ---")
    audio_result = {
        "text_risk_level": "ALTO",
        "identified_symptoms": ["fadiga extrema", "dificuldade de concentração"],
        "multimodal_risk_assessment": {
            "overall_risk": "ALTO",
            "justification": "Paciente apresenta sintomas vocais de exaustão "
                           "combinados com relatos de fadiga extrema.",
        },
        "clinical_recommendation": "Encaminhamento para avaliação psiquiátrica",
    }

    audio_alert = monitor.process_audio_analysis(patient_id, audio_result)
    if audio_alert:
        print(f"Alerta de áudio: [{audio_alert.priority.name}] {audio_alert.title}")

    # Gera status do paciente
    print("\n--- Status do Paciente ---")
    status = monitor.get_patient_status(patient_id)
    print(f"Nível de Risco: {status.risk_level.value}")
    print(f"Alertas Ativos: {status.active_alerts_count}")
    print(f"Alertas Críticos: {status.critical_alerts_count}")
    print(f"Resumo: {status.summary}")

    # Gera relatório
    print("\n--- Relatório Completo ---")
    report = monitor.generate_patient_report(patient_id)
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


def demo_alert_system():
    """Demonstra sistema de alertas."""
    print("\n" + "=" * 60)
    print("DEMONSTRAÇÃO: Sistema de Alertas")
    print("=" * 60)

    alert_system = AlertSystem()

    # Registra callback de notificação
    def on_new_alert(alert):
        if alert.priority.value <= 2:  # Crítico ou Alto
            print(f"🚨 NOTIFICAÇÃO: [{alert.priority.name}] {alert.title}")

    alert_system.register_callback(on_new_alert)

    # Cria alguns alertas
    alert_system.create_alert(
        patient_id="PAC001",
        source=AlertSource.VITAL_SIGNS,
        title="SpO2 Crítico",
        message="Saturação de oxigênio em 82%",
        severity="CRITICO",
    )

    alert_system.create_alert(
        patient_id="PAC001",
        source=AlertSource.PRESCRIPTION,
        title="Interação Medicamentosa",
        message="Varfarina + Aspirina detectada",
        severity="GRAVE",
    )

    alert_system.create_alert(
        patient_id="PAC002",
        source=AlertSource.AUDIO_ANALYSIS,
        title="Risco Psiquiátrico",
        message="Análise vocal indica sinais de depressão severa",
        severity="ALTO",
    )

    # Relatório de plantão
    print("\n--- Relatório de Passagem de Plantão ---")
    shift_report = alert_system.generate_shift_report()
    print(json.dumps(shift_report, indent=2, ensure_ascii=False))


def main():
    """Executa todas as demonstrações."""
    print("\n" + "=" * 60)
    print("TECH CHALLENGE - MÓDULO DE DETECÇÃO DE ANOMALIAS")
    print("=" * 60)
    print("\nEste módulo implementa o requisito 3 do Tech Challenge:")
    print("- Detecção de anomalias em sinais vitais")
    print("- Análise de evolução de prescrições")
    print("- Sistema de alertas automáticos")
    print("- Interface para integração com análise de vídeo")

    demo_vital_signs_analysis()
    demo_prescription_analysis()
    demo_alert_system()
    demo_patient_monitor()

    print("\n" + "=" * 60)
    print("DEMONSTRAÇÃO CONCLUÍDA")
    print("=" * 60)


if __name__ == "__main__":
    main()
