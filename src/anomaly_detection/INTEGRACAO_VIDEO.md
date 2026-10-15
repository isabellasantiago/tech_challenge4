# Guia de Integração com Módulo de Vídeo

Este guia explica como integrar o módulo de análise de vídeo (Requisito 1) com o sistema de detecção de anomalias.

## Pré-requisitos

Instalar dependências para análise de vídeo:

```bash
pip install opencv-python ultralytics  # YOLOv8
# OpenPose requer instalação separada - ver documentação oficial
```

## Passo a Passo

### 1. Criar sua classe de análise de vídeo

Crie um arquivo `video_analyzer.py` no seu módulo:

```python
from anomaly_detection.video_integration import (
    VideoAnalyzerInterface,
    VideoAnalysisResult,
    MovementAnomaly,
    PostureAnalysis,
    ObjectDetection,
    MovementType,
    PostureQuality,
)
from datetime import datetime
from ultralytics import YOLO
import cv2


class VideoAnalyzer(VideoAnalyzerInterface):
    """Implementação real do analisador de vídeo."""

    def __init__(self):
        # Carrega modelo YOLOv8
        self.yolo = YOLO('yolov8n.pt')
        # OpenPose - carregar conforme sua instalação
        # self.openpose = ...

    def analyze_video(self, video_path: str) -> VideoAnalysisResult:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        movement_anomalies = []
        posture_analyses = []
        object_detections = []

        frame_count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # Processa a cada 30 frames (1 segundo em 30fps)
            if frame_count % 30 == 0:
                # Detecção de objetos com YOLOv8
                results = self.yolo(frame)
                detections = self._process_yolo_results(results)
                if detections:
                    object_detections.append(detections)

                # Análise de postura (implementar com OpenPose)
                # posture = self._analyze_posture_frame(frame)
                # posture_analyses.append(posture)

            frame_count += 1

        cap.release()

        return VideoAnalysisResult(
            video_path=video_path,
            duration_seconds=duration,
            frames_analyzed=frame_count,
            movement_anomalies=movement_anomalies,
            posture_analyses=posture_analyses,
            object_detections=object_detections,
            overall_assessment="Análise concluída",
            recommendations=[],
            requires_attention=len(movement_anomalies) > 0,
        )

    def detect_movement_anomalies(self, patient_id, video_path, movement_type=None):
        # Implementar detecção de quedas, movimentos restritos, etc.
        anomalies = []
        # ... sua lógica aqui
        return anomalies

    def analyze_posture(self, video_path, sample_rate=30):
        # Implementar com OpenPose
        analyses = []
        # ... sua lógica aqui
        return analyses

    def detect_objects(self, video_path, target_classes=None):
        # Usar YOLOv8 para detectar equipamentos, EPIs, etc.
        detections = []
        # ... sua lógica aqui
        return detections

    def _process_yolo_results(self, results):
        # Processar resultados do YOLO
        # ...
        pass
```

### 2. Integrar com o PatientMonitor

```python
from anomaly_detection import PatientMonitor
from seu_modulo.video_analyzer import VideoAnalyzer

# Cria o analisador de vídeo
video_analyzer = VideoAnalyzer()

# Cria o monitor com o analisador integrado
monitor = PatientMonitor(video_analyzer=video_analyzer)

# Agora você pode processar vídeos
alerts = monitor.process_video_analysis(
    patient_id="PAC123",
    video_path="sessao_fisioterapia.mp4"
)

# Os alertas são automaticamente adicionados ao sistema
for alert in alerts:
    print(f"[{alert.priority.name}] {alert.title}: {alert.message}")
```

### 3. Exemplo completo de uso

```python
from anomaly_detection import PatientMonitor, AlertSystem
from seu_modulo.video_analyzer import VideoAnalyzer

# Setup
alert_system = AlertSystem()
video_analyzer = VideoAnalyzer()
monitor = PatientMonitor(
    alert_system=alert_system,
    video_analyzer=video_analyzer
)

# Processa vídeo de sessão de fisioterapia
video_alerts = monitor.process_video_analysis(
    patient_id="PAC123",
    video_path="videos/sessao_001.mp4"
)

# Gera relatório completo (inclui dados de vídeo)
report = monitor.generate_patient_report("PAC123")
print(report)
```

## Estrutura esperada dos resultados

O `VideoAnalyzer` deve retornar objetos definidos em `video_integration.py`:

- `MovementAnomaly`: Anomalias de movimento (quedas, tremores, etc.)
- `PostureAnalysis`: Análise postural com ângulos e desvios
- `ObjectDetection`: Objetos detectados (equipamentos, EPIs)
- `VideoAnalysisResult`: Resultado consolidado da análise

## Alertas gerados

Quando anomalias são detectadas, o sistema gera alertas automáticos:

| Tipo de Anomalia | Prioridade |
|------------------|------------|
| Queda detectada | P1 (Crítico) |
| Postura crítica | P2 (Alto) |
| Movimento restrito | P3 (Médio) |
| Equipamento ausente | P3 (Médio) |

## Dúvidas

Consulte o arquivo `video_integration.py` para ver a interface completa e os tipos de dados esperados.
