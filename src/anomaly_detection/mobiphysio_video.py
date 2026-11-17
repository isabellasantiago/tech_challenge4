"""Non-clinical pose heuristic for MobiPhysio E07, E08 and E09 videos."""
from __future__ import annotations

import hashlib
import math
import os
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .mobiphysio_dataset import (
    EXERCISE_NAMES,
    TARGET_EXERCISES,
    exercise_code_from_path,
)

MIN_ANGULAR_EXCURSION_DEGREES = 15.0
MIN_LANDMARK_VISIBILITY = 0.5
SAMPLE_RATE_FPS = 3.0
MIN_VALID_FRAMES = 3
MIN_VALID_FRACTION = 0.6
FRAME_COUNT_TOLERANCE = 1
POSE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
)
POSE_MODEL_ENV = "MEDIAPIPE_POSE_MODEL_PATH"
POSE_MODEL_SHA256 = "59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a"
_MODEL_USER_AGENT = "tech-challenge4-mobiphysio/0.1"
_JOINT_LANDMARKS = {
    "left": (11, 23, 25),
    "right": (12, 24, 26),
}


def angle_degrees(first, vertex, last) -> float | None:
    if not all(math.isfinite(coordinate) for point in (first, vertex, last) for coordinate in point):
        return None
    first_vector = (first[0] - vertex[0], first[1] - vertex[1])
    last_vector = (last[0] - vertex[0], last[1] - vertex[1])
    first_length = math.hypot(*first_vector)
    last_length = math.hypot(*last_vector)
    if first_length == 0 or last_length == 0:
        return None
    cosine = (
        first_vector[0] * last_vector[0] + first_vector[1] * last_vector[1]
    ) / (first_length * last_length)
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def _excursion_degrees(angles: list[float]) -> float:
    ordered = sorted(angles)
    low = ordered[int((len(ordered) - 1) * 0.1)]
    high = ordered[int((len(ordered) - 1) * 0.9)]
    return high - low


def _validate_decoded_frame_count(
    path: Path, decoded_frames: int, expected_frames: int
) -> None:
    missing_frames = expected_frames - decoded_frames
    if missing_frames > FRAME_COUNT_TOLERANCE:
        raise ValueError(
            f"decodificação incompleta do vídeo {path}: "
            f"{decoded_frames} de {expected_frames} quadros "
            f"({missing_frames} ausentes)"
        )


def _pose_model_path() -> Path:
    configured = os.environ.get(POSE_MODEL_ENV)
    if configured:
        model_path = Path(configured)
        if not model_path.is_file():
            raise FileNotFoundError(
                f"modelo MediaPipe configurado não encontrado: {model_path}"
            )
        if _sha256(model_path) != POSE_MODEL_SHA256:
            raise ValueError(f"SHA-256 inválido para o modelo MediaPipe: {model_path}")
        return model_path

    model_path = Path.home() / ".cache" / "tech-challenge4" / "pose_landmarker_lite.task"
    if model_path.is_file():
        if _sha256(model_path) != POSE_MODEL_SHA256:
            raise ValueError(f"SHA-256 inválido para o modelo MediaPipe: {model_path}")
        return model_path

    model_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=model_path.parent, prefix=".pose_landmarker.", suffix=".part", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            request = Request(POSE_MODEL_URL, headers={"User-Agent": _MODEL_USER_AGENT})
            try:
                with urlopen(request, timeout=120) as response:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        temporary.write(chunk)
            except HTTPError as exc:
                raise RuntimeError(
                    f"download do modelo MediaPipe respondeu HTTP {exc.code}"
                ) from exc
            except URLError as exc:
                raise RuntimeError(
                    f"não foi possível baixar o modelo MediaPipe: {exc.reason}"
                ) from exc
        if temporary_path.stat().st_size == 0:
            raise RuntimeError("o download do modelo MediaPipe retornou arquivo vazio")
        if _sha256(temporary_path) != POSE_MODEL_SHA256:
            raise ValueError("SHA-256 inválido no modelo MediaPipe baixado")
        os.replace(temporary_path, model_path)
        return model_path
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _visible(landmark) -> bool:
    visibility = getattr(landmark, "visibility", None)
    return (visibility is not None and math.isfinite(visibility)
            and visibility >= MIN_LANDMARK_VISIBILITY)


def _measure_side(landmarks, side: str, width: int, height: int) -> float | None:
    shoulder_index, hip_index, knee_index = _JOINT_LANDMARKS[side]
    shoulder = landmarks[shoulder_index]
    hip = landmarks[hip_index]
    knee = landmarks[knee_index]
    if not (_visible(shoulder) and _visible(hip) and _visible(knee)):
        return None
    return angle_degrees(
        (shoulder.x * width, shoulder.y * height),
        (hip.x * width, hip.y * height),
        (knee.x * width, knee.y * height),
    )


def _eligible_measurements(observations: list[dict[str, float | None]], exercise: str):
    """Require coverage across the clip; E08 uses only simultaneous observations."""
    count = len(observations)
    sides = ("left", "right")
    if exercise == "E08":
        valid = [i for i, frame in enumerate(observations)
                 if all(frame[side] is not None for side in sides)]
        candidates = {side: valid for side in sides}
    else:
        candidates = {side: [i for i, frame in enumerate(observations)
                             if frame[side] is not None] for side in sides}

    def sufficient(indices):
        return (len(indices) >= MIN_VALID_FRAMES
                and len(indices) >= count * MIN_VALID_FRACTION
                and len({min(2, i * 3 // count) for i in indices}) == 3)

    if exercise == "E08":
        if not sufficient(candidates["left"]):
            return None
        selected = sides
    else:
        available = [side for side in sides if sufficient(candidates[side])]
        if not available:
            return None
        selected = (max(available, key=lambda side: len(candidates[side])),)
    return {side: [observations[i][side] for i in candidates[side]] for side in selected}


def _percentile_evidence(observations, sides, exercise: str, step: int, fps: float) -> dict:
    """Identify the measured frames used for the two excursion percentiles."""
    evidence = {}
    for side in sides:
        samples = [
            (frame[side], index * step)
            for index, frame in enumerate(observations)
            if frame[side] is not None
            and (exercise != "E08" or all(frame[item] is not None for item in ("left", "right")))
        ]
        samples.sort(key=lambda sample: sample[0])
        percentiles = {}
        for name, fraction in (("p10", 0.1), ("p90", 0.9)):
            angle, frame_number = samples[int((len(samples) - 1) * fraction)]
            measured = {"angle_degrees": round(angle, 2), "frame_number": frame_number}
            if math.isfinite(fps) and fps > 0:
                measured["offset_seconds"] = frame_number / fps
            percentiles[name] = measured
        evidence[side] = percentiles
    return evidence


def _inconclusive(summary: str, duration: float | None, frames: int) -> dict:
    result = {
        "status": "INCONCLUSIVA",
        "findings": [],
        "summary": summary,
        "frames_analyzed": frames,
    }
    if duration is not None:
        result["duration_seconds"] = duration
    return result


def analyze_video(video_path: str) -> dict:
    """Estimate 2D hip-angle excursion; findings are heuristic, not clinical."""
    path = Path(video_path)
    if not path.is_file():
        raise FileNotFoundError(f"vídeo não encontrado: {path}")

    try:
        import cv2
        import mediapipe as mp
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "dependências de vídeo ausentes; instale com `uv sync --extra video`"
        ) from exc

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise ValueError(f"não foi possível abrir o vídeo: {path}")

    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        reported_frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        total_frames = int(reported_frames) if math.isfinite(reported_frames) and reported_frames > 0 else 0
        valid_fps = math.isfinite(fps) and fps > 0
        duration = total_frames / fps if valid_fps and total_frames > 0 else None
        ok, first_frame = capture.read()
        if not ok or first_frame is None:
            raise ValueError(f"vídeo sem quadros decodificáveis: {path}")

        if not valid_fps:
            return _inconclusive(
                "Não foi possível avaliar: taxa de quadros ausente ou inválida.",
                None,
                0,
            )

        exercise = exercise_code_from_path(path)
        if exercise not in TARGET_EXERCISES:
            label = exercise or "não identificado"
            return _inconclusive(
                f"Exercício {label} fora do filtro MobiPhysio E07/E08/E09.",
                duration,
                0,
            )

        model_path = _pose_model_path()
        try:
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
        except ImportError as exc:
            raise RuntimeError(
                "MediaPipe não disponibiliza a API PoseLandmarker esperada; "
                "confira a dependência opcional de vídeo"
            ) from exc

        options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(
                model_asset_buffer=model_path.read_bytes()
            ),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=MIN_LANDMARK_VISIBILITY,
            min_pose_presence_confidence=MIN_LANDMARK_VISIBILITY,
            min_tracking_confidence=MIN_LANDMARK_VISIBILITY,
        )
        step = max(1, round(fps / SAMPLE_RATE_FPS))
        observations = []
        analyzed_frames = 0
        frame_number = 0
        last_timestamp_ms = -1

        with vision.PoseLandmarker.create_from_options(options) as landmarker:
            ok = True
            frame = first_frame
            while ok:
                if frame_number % step == 0:
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                    timestamp_ms = int(frame_number * 1000 / fps)
                    timestamp_ms = max(last_timestamp_ms + 1, timestamp_ms)
                    last_timestamp_ms = timestamp_ms
                    result = landmarker.detect_for_video(image, timestamp_ms)
                    analyzed_frames += 1
                    measured_frame = {"left": None, "right": None}
                    if result.pose_landmarks:
                        landmarks = result.pose_landmarks[0]
                        height, width = frame.shape[:2]
                        for side in measured_frame:
                            measured_frame[side] = _measure_side(landmarks, side, width, height)
                    observations.append(measured_frame)
                frame_number += 1
                ok, frame = capture.read()

        _validate_decoded_frame_count(path, frame_number, total_frames)

        angles = _eligible_measurements(observations, exercise)
        if angles is None:
            return _inconclusive(
                "Marcos insuficientes: são necessários ao menos três quadros, "
                "60% das amostras e cobertura dos três terços do vídeo; para E08, "
                "ambos os lados devem estar visíveis nos mesmos quadros.",
                duration,
                analyzed_frames,
            )
        excursions = {side: _excursion_degrees(values) for side, values in angles.items()}

        low_excursion_sides = {
            side: value for side, value in excursions.items()
            if value < MIN_ANGULAR_EXCURSION_DEGREES
        }
        joint = "quadril" if exercise in {"E07", "E08"} else "ângulo tronco-quadril"
        rule = (
            "Heurística demonstrativa: comparar percentis 10–90 do ângulo 2D "
            "ombro-quadril-joelho; excursão abaixo de 15 graus é sinalizada. "
            "Regra não validada clinicamente."
        )
        findings = []
        if low_excursion_sides:
            measured = ", ".join(
                f"{side}: {value:.1f}°" for side, value in low_excursion_sides.items()
            )
            findings.append({
                "type": "BAIXA_EXCURSAO_ANGULAR_HEURISTICA",
                "description": (
                    f"Excursão angular abaixo do limiar demonstrativo ({measured}; "
                    f"limiar {MIN_ANGULAR_EXCURSION_DEGREES:.0f}°)."
                ),
                "severity": "BAIXO",
                "exercise_code": exercise,
                "exercise_name": EXERCISE_NAMES[exercise],
                "joint": joint,
                "angular_excursion_degrees": {
                    side: round(value, 2) for side, value in excursions.items()
                },
                "rule": rule,
                "heuristic": True,
                "valid_frames": {side: len(values) for side, values in angles.items()},
                "sampled_frames": analyzed_frames,
                "percentile_evidence": _percentile_evidence(
                    observations, angles, exercise, step, fps
                ),
                "sampled_frame_interval": {
                    "start": 0,
                    "end": ((frame_number - 1) // step) * step,
                },
            })
            if fps > 0 and math.isfinite(fps):
                findings[-1]["sampled_interval_seconds"] = {
                    "start": 0.0,
                    "end": (((frame_number - 1) // step) * step) / fps,
                }

        if findings:
            summary = (
                f"Análise heurística concluída para {exercise} "
                f"({EXERCISE_NAMES[exercise]}): baixa excursão angular "
                "demonstrativa observada."
            )
        else:
            summary = (
                f"Análise heurística concluída para {exercise} "
                f"({EXERCISE_NAMES[exercise]}): o limiar demonstrativo de "
                "excursão angular foi atingido."
            )
        result = {
            "status": "CONCLUIDA",
            "findings": findings,
            "summary": summary,
            "frames_analyzed": analyzed_frames,
        }
        if duration is not None:
            result["duration_seconds"] = duration
        return result
    finally:
        capture.release()
