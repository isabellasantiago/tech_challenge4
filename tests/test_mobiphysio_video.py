import math
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace, ModuleType
from unittest.mock import patch

from anomaly_detection.video_integration import VideoAnalysisResult

from anomaly_detection.mobiphysio_dataset import (
    TARGET_EXERCISES,
    REFERENCE_VIDEO,
    REGRESSION_VIDEO,
    LOWER_SCORE_VIDEOS,
    main as dataset_main,
    exercise_code_from_path,
    list_target_videos,
    select_sample_files,
)
from anomaly_detection.mobiphysio_video import (
    _validate_decoded_frame_count,
    _eligible_measurements,
    _percentile_evidence,
    _measure_side,
    _excursion_degrees,
    angle_degrees,
    analyze_video,
)


class MobiPhysioDatasetTests(unittest.TestCase):
    def test_extracts_supported_and_other_exercise_codes(self):
        self.assertEqual(
            exercise_code_from_path("E07_P02_AL_VFL_GM.mp4"), "E07"
        )
        self.assertEqual(
            exercise_code_from_path("dataset/E01/E01_P02_AF_VFL_GM.mp4"), "E01"
        )
        self.assertIsNone(exercise_code_from_path("recording.mp4"))
        with self.assertRaises(ValueError):
            exercise_code_from_path("E07/E08_P02_AL_VFL_GM.mp4")

    def test_lists_only_target_exercises(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for code in (*TARGET_EXERCISES, "E01"):
                (root / f"{code}_P02_AL_VFL_GM.mp4").touch()
            self.assertEqual(
                [path.name for path in list_target_videos(root)],
                [
                    "E07_P02_AL_VFL_GM.mp4",
                    "E08_P02_AL_VFL_GM.mp4",
                    "E09_P02_AL_VFL_GM.mp4",
                ],
            )

    def test_sample_selection_uses_two_distinct_side_view_participants(self):
        files = []
        for exercise in TARGET_EXERCISES:
            files.extend([
                {"filename": f"{exercise}_P01_AF_VFL_GM.mp4", "filesize": 1},
                {"filename": f"{exercise}_P01_AL_VFL_GM.mp4", "filesize": 3},
                {"filename": f"{exercise}_P02_AR_VFL_GM.mp4", "filesize": 2},
                {"filename": f"{exercise}_P03_AL_VFL_GM.mp4", "filesize": 4},
                {"filename": f"E01_P04_AL_VFL_GM.mp4", "filesize": 1},
            ])
        selected = select_sample_files(files)
        self.assertEqual(len(selected), 6)
        self.assertTrue(all(
            any(f"_A{side}_" in item["filename"] for side in ("L", "R"))
            for item in selected
        ))
        for exercise in TARGET_EXERCISES:
            names = [
                item["filename"] for item in selected
                if item["filename"].startswith(exercise + "_")
            ]
            self.assertEqual(len(names), 2)
            self.assertNotEqual(names[0].split("_")[1], names[1].split("_")[1])

    def test_reference_download_checks_pinned_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / REGRESSION_VIDEO["filename"]
            with patch("anomaly_detection.mobiphysio_dataset.download_sample_videos",
                       return_value=[existing]), patch(
                "anomaly_detection.mobiphysio_dataset._download_file",
                side_effect=lambda file_id, filename, md5, dest: dest / filename,
            ) as download, patch("builtins.print") as output:
                self.assertEqual(dataset_main(["--output-dir", directory,
                                               "--include-reference"]), 0)
            self.assertEqual(download.call_count, 4)
            download.assert_any_call(REFERENCE_VIDEO["file_id"], REFERENCE_VIDEO["filename"],
                                     REFERENCE_VIDEO["md5"], root)
            download.assert_any_call(REGRESSION_VIDEO["file_id"], REGRESSION_VIDEO["filename"],
                                     REGRESSION_VIDEO["md5"], root)
            self.assertEqual(output.call_count, 4)

    def test_angle_degrees_and_degenerate_points(self):
        self.assertAlmostEqual(angle_degrees((1, 0), (0, 0), (0, 1)), 90)
        self.assertIsNone(angle_degrees((0, 0), (0, 0), (0, 1)))
        self.assertIsNone(angle_degrees((float("nan"), 0), (0, 0), (0, 1)))
        self.assertIsNone(angle_degrees((float("inf"), 0), (0, 0), (0, 1)))

    def test_measurement_corrects_non_square_frame_coordinates(self):
        landmarks = [SimpleNamespace(x=0, y=0, visibility=1) for _ in range(27)]
        landmarks[11] = SimpleNamespace(x=0.5, y=0.5, visibility=1)
        landmarks[23] = SimpleNamespace(x=0, y=0, visibility=1)
        landmarks[25] = SimpleNamespace(x=0, y=1, visibility=1)
        # In a 2:1 image, the first vector is (1, 0.5), not (0.5, 0.5).
        self.assertAlmostEqual(_measure_side(landmarks, "left", 200, 100), 63.4349488)
        landmarks[11].visibility = float("nan")
        self.assertIsNone(_measure_side(landmarks, "left", 200, 100))
        landmarks[11].visibility = None
        self.assertIsNone(_measure_side(landmarks, "left", 200, 100))

    def test_unilateral_requires_coverage_throughout_video(self):
        frames = [{"left": 45.0 if i < 6 else None, "right": None} for i in range(10)]
        self.assertIsNone(_eligible_measurements(frames, "E07"))
        for i in (6, 9):
            frames[i]["left"] = 70.0
        angles = _eligible_measurements(frames, "E07")
        self.assertEqual(len(angles["left"]), 8)
        self.assertGreater(_excursion_degrees(angles["left"]), 15)

    def test_bilateral_requires_simultaneous_coverage(self):
        frames = [{"left": 45.0 if i < 6 else None,
                   "right": 50.0 if i >= 4 else None} for i in range(10)]
        self.assertIsNone(_eligible_measurements(frames, "E08"))
        frames = [{"left": 45.0, "right": 50.0} for _ in range(10)]
        angles = _eligible_measurements(frames, "E08")
        self.assertEqual(set(angles), {"left", "right"})
        self.assertLess(_excursion_degrees(angles["left"]), 15)

    def test_percentile_evidence_uses_original_frame_indices_and_bilateral_pairs(self):
        observations = [
            {"left": 10.0, "right": 70.0},
            {"left": 90.0, "right": None},
            {"left": 20.0, "right": 60.0},
            {"left": 40.0, "right": 80.0},
        ]
        evidence = _percentile_evidence(observations, ("left", "right"), "E08", 4, 20.0)
        self.assertEqual(evidence["left"]["p10"],
                         {"angle_degrees": 10.0, "frame_number": 0, "offset_seconds": 0.0})
        self.assertEqual(evidence["left"]["p90"],
                         {"angle_degrees": 20.0, "frame_number": 8, "offset_seconds": 0.4})
        self.assertNotIn("offset_seconds", _percentile_evidence(
            observations, ("left",), "E07", 4, 0.0)["left"]["p10"])

    def test_insufficient_fraction_and_no_person_are_inconclusive(self):
        frames = [{"left": 45.0 if i in (0, 3, 9) else None, "right": None}
                  for i in range(10)]
        self.assertIsNone(_eligible_measurements(frames, "E09"))
        self.assertIsNone(_eligible_measurements([], "E09"))

    def test_analyzer_decisions_and_contract_with_controlled_pose_sequence(self):
        class Capture:
            def __init__(self, fps):
                self.remaining = 10
                self.fps = fps
            def isOpened(self):
                return True
            def get(self, prop):
                return self.fps if prop == 1 else 10
            def read(self):
                if not self.remaining:
                    return False, None
                self.remaining -= 1
                return True, SimpleNamespace(shape=(100, 200, 3))
            def release(self):
                pass

        def run_sequence(values, fps=3):
            def pose(angle):
                if angle is None:
                    return SimpleNamespace(pose_landmarks=[])
                points = [SimpleNamespace(x=0.0, y=0.0, visibility=1.0) for _ in range(27)]
                points[11] = SimpleNamespace(x=0.5, y=0.0, visibility=1.0)
                radians = math.radians(angle)
                points[25] = SimpleNamespace(x=math.cos(radians) / 2,
                                             y=math.sin(radians), visibility=1.0)
                return SimpleNamespace(pose_landmarks=[points])
            class Landmarker:
                def __init__(self):
                    self.results = iter(map(pose, values))
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    pass
                def detect_for_video(self, image, timestamp):
                    return next(self.results)
            cv2 = SimpleNamespace(VideoCapture=lambda path: Capture(fps), CAP_PROP_FPS=1,
                                  CAP_PROP_FRAME_COUNT=2, COLOR_BGR2RGB=3,
                                  cvtColor=lambda frame, color: frame)
            mp = ModuleType("mediapipe")
            mp.Image = lambda **kwargs: object()
            mp.ImageFormat = SimpleNamespace(SRGB=1)
            tasks = ModuleType("mediapipe.tasks")
            python = ModuleType("mediapipe.tasks.python")
            python.BaseOptions = lambda **kwargs: object()
            vision = ModuleType("mediapipe.tasks.python.vision")
            vision.PoseLandmarkerOptions = lambda **kwargs: object()
            vision.RunningMode = SimpleNamespace(VIDEO=1)
            vision.PoseLandmarker = SimpleNamespace(create_from_options=lambda options: Landmarker())
            python.vision = vision
            tasks.python = python
            mp.tasks = tasks
            modules = {"cv2": cv2, "mediapipe": mp, "mediapipe.tasks": tasks,
                       "mediapipe.tasks.python": python, "mediapipe.tasks.python.vision": vision}
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "E07_test.mp4"
                path.touch()
                model = Path(directory) / "model.task"
                model.write_bytes(b"model")
                with patch.dict(sys.modules, modules), patch(
                    "anomaly_detection.mobiphysio_video._pose_model_path", return_value=model
                ):
                    result = analyze_video(str(path))
                VideoAnalysisResult.from_dict(result)
                return result

        finding = run_sequence([45] * 10)
        self.assertEqual(finding["status"], "CONCLUIDA")
        self.assertEqual(finding["findings"][0]["severity"], "BAIXO")
        self.assertEqual(finding["findings"][0]["sampled_frame_interval"],
                         {"start": 0, "end": 9})
        self.assertEqual(finding["findings"][0]["sampled_interval_seconds"],
                         {"start": 0.0, "end": 3.0})
        self.assertNotIn("offset_seconds", finding["findings"][0])
        clean = run_sequence([30, 60] * 5)
        self.assertEqual(clean["status"], "CONCLUIDA")
        self.assertEqual(clean["findings"], [])
        inconclusive = run_sequence([45, 45, 45] + [None] * 7)
        self.assertEqual(inconclusive["status"], "INCONCLUSIVA")
        self.assertEqual(inconclusive["findings"], [])
        for fps in (0, -1, float("nan"), float("inf")):
            with self.subTest(fps=fps):
                unknown_timing = run_sequence([45] * 10, fps)
                self.assertEqual(unknown_timing["status"], "INCONCLUSIVA")
                self.assertIn("taxa de quadros", unknown_timing["summary"])
                self.assertEqual(unknown_timing["findings"], [])

    def test_missing_video_raises_before_optional_model_import(self):
        with self.assertRaises(FileNotFoundError):
            analyze_video("missing_E07.mp4")

    def test_incomplete_video_decode_raises(self):
        with self.assertRaisesRegex(ValueError, "decodificação incompleta"):
            _validate_decoded_frame_count(Path("truncated.mp4"), 7, 10)

    def test_one_frame_count_difference_is_tolerated(self):
        _validate_decoded_frame_count(Path("video.mp4"), 9, 10)

    def test_unknown_frame_count_does_not_infer_decode_failure(self):
        _validate_decoded_frame_count(Path("video.mp4"), 7, 0)


if __name__ == "__main__":
    unittest.main()
