# -*- coding: utf-8 -*-
"""
=============================================================================
SCRIPT DE DEMONSTRACAO - TECH CHALLENGE 4
Modulo de Deteccao de Anomalias para Monitoramento de Pacientes
=============================================================================

Este script demonstra o funcionamento completo do sistema para gravacao de tela.

Execute com: python demo_gravacao.py
"""

import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Configura encoding para Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Adiciona o diretorio src ao path para imports
src_dir = Path(__file__).parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Imports do modulo - tenta import relativo primeiro, depois absoluto
try:
    from anomaly_detection.vital_signs_detector import VitalSignsAnomalyDetector, VitalSignsReading
    from anomaly_detection.prescription_analyzer import PrescriptionAnalyzer, Prescription, Medication
    from anomaly_detection.alert_system import AlertSystem, AlertSource
    from anomaly_detection.patient_monitor import PatientMonitor
except ImportError:
    from vital_signs_detector import VitalSignsAnomalyDetector, VitalSignsReading
    from prescription_analyzer import PrescriptionAnalyzer, Prescription, Medication
    from alert_system import AlertSystem, AlertSource
    from patient_monitor import PatientMonitor


def print_header(title: str):
    """Imprime cabecalho formatado."""
    print("\n")
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)
    time.sleep(1)


def print_section(title: str):
    """Imprime secao formatada."""
    print(f"\n>>> {title}")
    print("-" * 50)
    time.sleep(0.5)


def demo_sinais_vitais():
    """Demonstracao 1: Deteccao de anomalias em sinais vitais."""
    print_header("DEMONSTRACAO 1: ANALISE DE SINAIS VITAIS")

    print("\nCriando detector de anomalias...")
    detector = VitalSignsAnomalyDetector()
    time.sleep(0.5)

    # Cenario 1: Paciente estavel
    print_section("Cenario 1: Paciente Estavel")

    leitura_normal = VitalSignsReading(
        timestamp=datetime.now(),
        heart_rate=72,
        systolic_bp=120,
        diastolic_bp=80,
        spo2=98,
        temperature=36.5,
        respiratory_rate=16,
    )

    print(f"  Frequencia Cardiaca: {leitura_normal.heart_rate} bpm")
    print(f"  Pressao Arterial: {leitura_normal.systolic_bp}/{leitura_normal.diastolic_bp} mmHg")
    print(f"  Saturacao O2: {leitura_normal.spo2}%")
    print(f"  Temperatura: {leitura_normal.temperature} C")
    print(f"  Frequencia Respiratoria: {leitura_normal.respiratory_rate} rpm")

    time.sleep(1)
    print("\n  Analisando...")
    time.sleep(0.5)

    resultados = detector.analyze_reading(leitura_normal)
    anomalias = [r for r in resultados if r.is_anomaly]

    if not anomalias:
        print("\n  [OK] RESULTADO: Todos os sinais vitais dentro dos parametros normais")

    time.sleep(1.5)

    # Cenario 2: Paciente critico
    print_section("Cenario 2: Paciente em Estado Critico")

    leitura_critica = VitalSignsReading(
        timestamp=datetime.now(),
        heart_rate=150,      # Taquicardia severa
        systolic_bp=180,     # Crise hipertensiva
        diastolic_bp=110,    # Hipertensao
        spo2=85,             # Hipoxemia severa
        temperature=39.5,    # Febre alta
        respiratory_rate=32, # Taquipneia
    )

    print(f"  Frequencia Cardiaca: {leitura_critica.heart_rate} bpm  [!]")
    print(f"  Pressao Arterial: {leitura_critica.systolic_bp}/{leitura_critica.diastolic_bp} mmHg  [!]")
    print(f"  Saturacao O2: {leitura_critica.spo2}%  [!]")
    print(f"  Temperatura: {leitura_critica.temperature} C  [!]")
    print(f"  Frequencia Respiratoria: {leitura_critica.respiratory_rate} rpm  [!]")

    time.sleep(1)
    print("\n  Analisando...")
    time.sleep(0.5)

    resultados = detector.analyze_reading(leitura_critica)
    anomalias = [r for r in resultados if r.is_anomaly]

    print(f"\n  [ALERTA] RESULTADO: {len(anomalias)} ANOMALIAS DETECTADAS!")
    print()

    for r in anomalias:
        severidade_simbolo = {
            "CRITICO": "[!!!]",
            "ALTO": "[!!]",
            "MEDIO": "[!]",
            "BAIXO": "[i]",
        }
        simbolo = severidade_simbolo.get(r.severity.value, "[?]")
        print(f"  {simbolo} [{r.severity.value}] {r.message}")
        time.sleep(0.3)

    time.sleep(2)


def demo_prescricoes():
    """Demonstracao 2: Analise de prescricoes medicas."""
    print_header("DEMONSTRACAO 2: ANALISE DE PRESCRICOES")

    print("\nCriando analisador de prescricoes...")
    analyzer = PrescriptionAnalyzer()
    time.sleep(0.5)

    # Prescricao inicial
    print_section("Prescricao Inicial do Paciente")

    prescricao1 = Prescription(
        prescription_id="RX-2024-001",
        patient_id="PAC-12345",
        timestamp=datetime.now() - timedelta(days=7),
        medications=[
            Medication(name="Enalapril", dosage=10, unit="mg", frequency="1x/dia"),
            Medication(name="Metformina", dosage=500, unit="mg", frequency="2x/dia"),
        ],
    )

    print("  Medicamentos prescritos:")
    for med in prescricao1.medications:
        print(f"    - {med.name} {med.dosage}{med.unit} - {med.frequency}")

    time.sleep(1)
    alertas1 = analyzer.analyze_prescription(prescricao1)

    if not alertas1:
        print("\n  [OK] Prescricao sem alertas")

    time.sleep(1.5)

    # Nova prescricao com problemas
    print_section("Nova Prescricao - 7 dias depois")

    prescricao2 = Prescription(
        prescription_id="RX-2024-002",
        patient_id="PAC-12345",
        timestamp=datetime.now(),
        medications=[
            Medication(name="Enalapril", dosage=40, unit="mg", frequency="1x/dia"),  # 4x aumento
            Medication(name="Metformina", dosage=500, unit="mg", frequency="2x/dia"),
            Medication(name="Varfarina", dosage=5, unit="mg", frequency="1x/dia"),   # Novo
            Medication(name="Aspirina", dosage=100, unit="mg", frequency="1x/dia"),  # Interacao!
        ],
    )

    print("  Medicamentos prescritos:")
    for med in prescricao2.medications:
        print(f"    - {med.name} {med.dosage}{med.unit} - {med.frequency}")

    time.sleep(1)
    print("\n  Analisando alteracoes e interacoes...")
    time.sleep(0.5)

    alertas2 = analyzer.analyze_prescription(prescricao2)

    print(f"\n  [ALERTA] {len(alertas2)} ALERTAS DETECTADOS!")
    print()

    for alerta in alertas2:
        severidade_simbolo = {
            "GRAVE": "[!!!]",
            "MODERADA": "[!!]",
            "LEVE": "[!]",
        }
        simbolo = severidade_simbolo.get(alerta.severity.value, "[?]")
        print(f"  {simbolo} [{alerta.alert_type.value}]")
        print(f"     {alerta.message}")
        print(f"     -> {alerta.recommendation}")
        print()
        time.sleep(0.5)

    time.sleep(2)


def demo_sistema_alertas():
    """Demonstracao 3: Sistema de alertas automaticos."""
    print_header("DEMONSTRACAO 3: SISTEMA DE ALERTAS AUTOMATICOS")

    print("\nInicializando sistema de alertas...")
    alert_system = AlertSystem()
    time.sleep(0.5)

    # Callback para simular notificacao
    def notificar_alerta(alert):
        if alert.priority.value <= 2:
            print(f"\n  [NOTIFICACAO] {alert.title}")

    alert_system.register_callback(notificar_alerta)

    print_section("Gerando Alertas de Multiplas Fontes")

    # Alerta de sinais vitais
    print("\n  [VITAL] Criando alerta de sinais vitais...")
    time.sleep(0.5)
    alert_system.create_alert(
        patient_id="PAC-001",
        source=AlertSource.VITAL_SIGNS,
        title="SpO2 Critico",
        message="Saturacao de oxigenio em 82% - Risco de hipoxia",
        severity="CRITICO",
    )

    time.sleep(1)

    # Alerta de prescricao
    print("\n  [RX] Criando alerta de prescricao...")
    time.sleep(0.5)
    alert_system.create_alert(
        patient_id="PAC-001",
        source=AlertSource.PRESCRIPTION,
        title="Interacao Medicamentosa Grave",
        message="Varfarina + Aspirina: risco aumentado de sangramento",
        severity="GRAVE",
    )

    time.sleep(1)

    # Alerta de audio
    print("\n  [AUDIO] Criando alerta de analise de audio...")
    time.sleep(0.5)
    alert_system.create_alert(
        patient_id="PAC-002",
        source=AlertSource.AUDIO_ANALYSIS,
        title="Indicadores Vocais de Risco",
        message="Analise vocal indica possiveis sinais de depressao",
        severity="ALTO",
    )

    time.sleep(1.5)

    print_section("Relatorio de Passagem de Plantao")

    relatorio = alert_system.generate_shift_report()

    print(f"\n  [RELATORIO] Resumo do Plantao:")
    print(f"     Total de alertas: {relatorio['total_alerts']}")
    print(f"     Alertas criticos pendentes: {relatorio['critical_pending']}")
    print(f"     Alertas de alta prioridade: {relatorio['high_pending']}")
    print(f"     Pacientes com alertas: {len(relatorio['patients_with_alerts'])}")

    print("\n  [STATS] Alertas por Fonte:")
    for fonte, qtd in relatorio['alerts_by_source'].items():
        if qtd > 0:
            print(f"     - {fonte}: {qtd}")

    time.sleep(2)


def demo_monitor_paciente():
    """Demonstracao 4: Monitor integrado de paciente."""
    print_header("DEMONSTRACAO 4: MONITOR INTEGRADO DE PACIENTE")

    print("\nInicializando monitor de pacientes...")
    monitor = PatientMonitor()
    patient_id = "PAC-789"
    time.sleep(0.5)

    print_section(f"Monitoramento do Paciente {patient_id}")

    # Processa sinais vitais
    print("\n  [1] Processando sinais vitais...")
    time.sleep(0.5)

    leitura = VitalSignsReading(
        timestamp=datetime.now(),
        heart_rate=145,
        systolic_bp=95,
        diastolic_bp=65,
        spo2=89,
        temperature=38.8,
        respiratory_rate=26,
    )

    alertas_vitais = monitor.process_vital_signs(patient_id, leitura)
    print(f"     -> {len(alertas_vitais)} alertas gerados")

    time.sleep(1)

    # Processa prescricao
    print("\n  [2] Processando prescricao...")
    time.sleep(0.5)

    prescricao = Prescription(
        prescription_id="RX-003",
        patient_id=patient_id,
        timestamp=datetime.now(),
        medications=[
            Medication(name="Fluoxetina", dosage=20, unit="mg", frequency="1x/dia"),
            Medication(name="Tramadol", dosage=50, unit="mg", frequency="6/6h"),
        ],
    )

    alertas_rx = monitor.process_prescription(prescricao)
    print(f"     -> {len(alertas_rx)} alertas gerados")

    time.sleep(1)

    # Processa analise de audio (simulada)
    print("\n  [3] Processando analise de audio...")
    time.sleep(0.5)

    resultado_audio = {
        "text_risk_level": "ALTO",
        "identified_symptoms": ["fadiga vocal", "pausas longas", "tom monotono"],
        "multimodal_risk_assessment": {
            "overall_risk": "ALTO",
            "justification": "Paciente apresenta marcadores vocais de exaustao e possivel estado depressivo",
        },
        "clinical_recommendation": "Avaliacao psicologica recomendada",
    }

    alerta_audio = monitor.process_audio_analysis(patient_id, resultado_audio)
    print(f"     -> Alerta de audio: {'Sim' if alerta_audio else 'Nao'}")

    time.sleep(1.5)

    # Status consolidado
    print_section("Status Consolidado do Paciente")

    status = monitor.get_patient_status(patient_id)

    risco_simbolo = {
        "ESTAVEL": "[OK]",
        "ATENCAO": "[!]",
        "ALERTA": "[!!]",
        "CRITICO": "[!!!]",
    }

    print(f"\n  {risco_simbolo.get(status.risk_level.value, '[?]')} Nivel de Risco: {status.risk_level.value}")
    print(f"  [VITAL] Sinais Vitais: {status.vital_signs_status}")
    print(f"  [RX] Prescricoes: {status.prescription_status}")
    print(f"  [AUDIO] Analise de Audio: {status.audio_analysis_status}")
    print(f"  [VIDEO] Analise de Video: {status.video_analysis_status}")
    print(f"\n  [RESUMO] {status.summary}")
    print(f"  [!] Total de alertas ativos: {status.active_alerts_count}")
    print(f"  [!!!] Alertas criticos: {status.critical_alerts_count}")

    time.sleep(2)

    # Relatorio completo
    print_section("Relatorio Completo (JSON)")
    time.sleep(0.5)

    relatorio = monitor.generate_patient_report(patient_id)
    print(json.dumps(relatorio, indent=2, ensure_ascii=False, default=str))

    time.sleep(2)


def main():
    """Executa demonstracao completa."""
    print("\n" * 2)
    print("+====================================================================+")
    print("|                                                                    |")
    print("|              TECH CHALLENGE 4 - FASE 5                             |")
    print("|     Sistema Multimodal de Monitoramento de Pacientes              |")
    print("|                                                                    |")
    print("|     Modulo: Deteccao de Anomalias                                 |")
    print("|                                                                    |")
    print("+====================================================================+")
    print("\n  Este modulo implementa:")
    print("  * Deteccao de anomalias em sinais vitais")
    print("  * Analise de evolucao de prescricoes")
    print("  * Sistema de alertas automaticos")
    print("  * Integracao com analise de audio")
    print("  * Interface para futura integracao com video")

    time.sleep(3)

    # Executa demonstracoes
    demo_sinais_vitais()
    demo_prescricoes()
    demo_sistema_alertas()
    demo_monitor_paciente()

    # Finalizacao
    print("\n" * 2)
    print("+====================================================================+")
    print("|                                                                    |")
    print("|                   DEMONSTRACAO CONCLUIDA                           |")
    print("|                                                                    |")
    print("|  O sistema esta pronto para:                                       |")
    print("|  [x] Monitorar sinais vitais em tempo real                        |")
    print("|  [x] Analisar prescricoes e detectar interacoes                   |")
    print("|  [x] Gerar alertas automaticos para equipe medica                 |")
    print("|  [x] Integrar com modulo de analise de audio                      |")
    print("|  [x] Receber futura integracao com analise de video               |")
    print("|                                                                    |")
    print("+====================================================================+")
    print()


if __name__ == "__main__":
    main()
