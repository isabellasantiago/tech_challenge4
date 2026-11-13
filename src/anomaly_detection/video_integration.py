"""Contrato interno e adaptador do dicionário independente fornecido pelo Cae."""
from dataclasses import dataclass
from importlib import import_module
import math
from typing import Callable, Protocol

SEVERITIES = {"CRITICO", "ALTO", "MEDIO", "BAIXO"}


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def number(value, name, minimum=0, maximum=None, integer=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < minimum
            or (maximum is not None and value > maximum)
            or (integer and not isinstance(value, int))):
        raise ValueError(f"{name} inválido")


@dataclass(frozen=True)
class VideoAnalysisResult:
    status: str
    findings: list[dict]
    summary: str = ""
    duration_seconds: float | None = None
    frames_analyzed: int | None = None

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or data.get("status") not in {
            "CONCLUIDA", "INCONCLUSIVA", "SIMULADA"
        }:
            raise ValueError("status de vídeo inválido")
        findings = data.get("findings")
        if not isinstance(findings, list):
            raise ValueError("findings deve ser uma lista")
        summary = data.get("summary", "")
        if not isinstance(summary, str):
            raise ValueError("summary deve ser texto")
        if data["status"] == "INCONCLUSIVA" and (not nonempty(summary) or findings):
            raise ValueError("vídeo inconclusivo exige motivo e findings vazio")
        for finding in findings:
            if (not isinstance(finding, dict)
                    or not nonempty(finding.get("type"))
                    or not nonempty(finding.get("description"))
                    or finding.get("severity") not in SEVERITIES):
                raise ValueError("achado de vídeo inválido: tipo, descrição ou severidade")
            for name in ("offset_seconds", "frame_number", "confidence"):
                if name in finding:
                    number(finding[name], name, maximum=1 if name == "confidence" else None,
                           integer=name == "frame_number")
        for name in ("duration_seconds", "frames_analyzed"):
            if name in data:
                number(data[name], name, integer=name == "frames_analyzed")
        # Todas as evidências adicionais devem poder ser preservadas no JSON.
        import json
        json.dumps(data, allow_nan=False)
        return cls(data["status"], findings, summary, data.get("duration_seconds"),
                   data.get("frames_analyzed"))


class VideoAnalyzerProtocol(Protocol):
    def analyze_video(self, video_path: str) -> VideoAnalysisResult: ...


class VideoFunctionAdapter:
    def __init__(self, function: Callable):
        self.function = function

    @classmethod
    def load(cls, reference: str):
        module, separator, name = reference.partition(":")
        if not separator or not module or not name:
            raise ValueError("analisador deve ser modulo:funcao")
        function = getattr(import_module(module), name)
        if not callable(function):
            raise ValueError("analisador de vídeo não é uma função")
        return cls(function)

    def analyze_video(self, video_path: str) -> VideoAnalysisResult:
        return VideoAnalysisResult.from_dict(self.function(video_path))


class VideoAnalyzerStub:
    def analyze_video(self, video_path: str) -> VideoAnalysisResult:
        return VideoAnalysisResult.from_dict({
            "status": "SIMULADA",
            "summary": "Exemplo simulado; nenhum vídeo foi analisado.",
            "findings": [{"type": "DESVIO_POSTURAL", "severity": "MEDIO",
                          "description": "Exemplo simulado de inclinação do tronco.",
                          "offset_seconds": 12.5, "rule": "stub demonstrativo"}],
        })


# Nome legado aponta para o mesmo protocolo, sem contrato paralelo.
VideoAnalyzerInterface = VideoAnalyzerProtocol
