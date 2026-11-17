"""Download and filtering helpers for a small MobiPhysio video sample."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DATASET_DOI = "doi:10.7910/DVN/XSI0QN"
DATASET_API = "https://dataverse.harvard.edu/api"
DATASET_PAGE = "https://dataverse.harvard.edu/citation?persistentId=doi:10.7910/DVN/XSI0QN"
TARGET_EXERCISES = ("E07", "E08", "E09")
EXERCISE_NAMES = {
    "E07": "Hip Joint Flexion",
    "E08": "Both Leg Flexion",
    "E09": "Back Extension",
}
SAMPLES_PER_EXERCISE = 2
REFERENCE_VIDEO = {
    "filename": "E09_P02_AR_VFL_GM.mp4",
    "file_id": 11798560,
    "md5": "a45b591d0828f97a96a27bbdf7174130",
}
REGRESSION_VIDEO = {
    "filename": "E09_P32_AL_VFL_GM.mp4",
    "file_id": 11798844,
    "md5": "f374838df339c5a3076a460af1772834",
}
LOWER_SCORE_VIDEOS = (
    {"filename": "E09_P21_AR_VFL_GM.mp4", "file_id": 11799435,
     "md5": "2ef1e7e9107627b1b934f0226f57ec4b"},
    {"filename": "E09_P05_AR_VFL_GM.mp4", "file_id": 11798616,
     "md5": "4db75f056abdb1c37ef67bc27909c189"},
)
_EXERCISE_CODE = re.compile(r"^(E\d{2})(?=[_\s-]|$)")
_DATASET_FILENAME = re.compile(
    r"^(?P<exercise>E\d{2})_(?P<participant>P\d{2})_A(?P<angle>[FLR])_"
    r"V(?P<variation>[A-Z]+)_G[MF]\.mp4$",
    re.IGNORECASE,
)
_USER_AGENT = "tech-challenge4-mobiphysio/0.1 (+https://doi.org/10.7910/DVN/XSI0QN)"


def exercise_code_from_path(path: str | Path) -> str | None:
    codes = set()
    for part in Path(path).parts:
        candidate = Path(part).stem
        match = _EXERCISE_CODE.match(candidate)
        if match:
            codes.add(match.group(1).upper())
    if len(codes) > 1:
        raise ValueError(f"códigos de exercício ambíguos no caminho: {path}")
    return next(iter(codes), None)


def list_target_videos(dataset_dir: str | Path) -> list[Path]:
    root = Path(dataset_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"diretório do dataset não encontrado: {root}")
    return sorted(
        path for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() == ".mp4"
        and exercise_code_from_path(path) in TARGET_EXERCISES
    )


def select_sample_files(files: list[dict]) -> list[dict]:
    candidates = []
    for item in files:
        filename = item.get("filename", "")
        match = _DATASET_FILENAME.fullmatch(filename)
        if not match or match.group("exercise") not in TARGET_EXERCISES:
            continue
        if match.group("angle").upper() not in {"L", "R"}:
            continue
        candidates.append((int(item["filesize"]), filename, match, item))

    selected = []
    for exercise in TARGET_EXERCISES:
        chosen_participants = set()
        for _, _, match, item in sorted(candidates, key=lambda row: (row[0], row[1])):
            if match.group("exercise") != exercise:
                continue
            participant = match.group("participant")
            if participant in chosen_participants:
                continue
            chosen_participants.add(participant)
            selected.append(item)
            if len(chosen_participants) == SAMPLES_PER_EXERCISE:
                break
        if len(chosen_participants) != SAMPLES_PER_EXERCISE:
            raise RuntimeError(
                f"o Dataverse não retornou {SAMPLES_PER_EXERCISE} vídeos de vista "
                f"lateral para {exercise}"
            )
    return selected


def _request(url: str):
    request = Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        return urlopen(request, timeout=120)
    except HTTPError as exc:
        raise RuntimeError(f"Harvard Dataverse respondeu HTTP {exc.code} para {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"não foi possível acessar Harvard Dataverse: {exc.reason}") from exc


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_file(file_id: int, filename: str, expected_md5: str, destination: Path) -> Path:
    target = destination / filename
    if target.exists():
        actual_md5 = _md5(target)
        if actual_md5 != expected_md5:
            raise ValueError(f"checksum MD5 divergente para arquivo existente: {target}")
        return target

    request_url = f"{DATASET_API}/access/datafile/{file_id}"
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination, prefix=f".{filename}.", suffix=".part", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            digest = hashlib.md5()
            with _request(request_url) as response:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    temporary.write(chunk)
                    digest.update(chunk)
        if digest.hexdigest().lower() != expected_md5.lower():
            raise ValueError(f"checksum MD5 divergente após download de {filename}")
        os.replace(temporary_path, target)
        return target
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def download_sample_videos(dataset_dir: str | Path) -> list[Path]:
    destination = Path(dataset_dir)
    destination.mkdir(parents=True, exist_ok=True)
    metadata_url = (
        f"{DATASET_API}/datasets/:persistentId/"
        f"?persistentId={DATASET_DOI}"
    )
    with _request(metadata_url) as response:
        payload = json.load(response)
    if payload.get("status") != "OK":
        raise RuntimeError(f"resposta inválida do Dataverse: {payload.get('status')}")

    version = payload["data"]["latestVersion"]
    inventory = [entry["dataFile"] for entry in version.get("files", [])]
    chosen = select_sample_files(inventory)
    downloaded = []
    manifest_files = []
    for item in chosen:
        checksum = item.get("checksum") or {}
        expected_md5 = checksum.get("value") or item.get("md5")
        if not expected_md5:
            raise ValueError(f"Dataverse não forneceu MD5 para {item['filename']}")
        path = _download_file(
            int(item["id"]), item["filename"], expected_md5, destination
        )
        downloaded.append(path)
        manifest_files.append({
            "filename": item["filename"],
            "file_id": item["id"],
            "size_bytes": item["filesize"],
            "md5": expected_md5,
            "exercise": exercise_code_from_path(item["filename"]),
        })

    manifest = {
        "dataset": "MobiPhysio",
        "doi": DATASET_DOI,
        "dataset_page": DATASET_PAGE,
        "version": (
            f"{version.get('versionNumber')}.{version.get('versionMinorNumber')}"
        ),
        "selection": (
            "Dois menores vídeos de vista lateral, de participantes distintos, "
            "para cada exercício E07, E08 e E09."
        ),
        "license": "CC0 1.0",
        "files": manifest_files,
    }
    (destination / "sample_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return downloaded


def main(argv: list[str] | None = None) -> int:
    default_dir = Path(
        os.environ.get("MOBIPHYSIO_DATASET_DIR", "data/MobiPhysioResearch")
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=default_dir)
    parser.add_argument(
        "--include-reference", action="store_true",
        help="inclui vídeo E09 com avaliação independente de três fisioterapeutas",
    )
    args = parser.parse_args(argv)
    downloaded = download_sample_videos(args.output_dir)
    for path in downloaded:
        print(path)
    if args.include_reference:
        for video in (REFERENCE_VIDEO, REGRESSION_VIDEO, *LOWER_SCORE_VIDEOS):
            path = args.output_dir / video["filename"]
            # Recheck the pinned checksum even if the video is in the sample.
            reference = _download_file(video["file_id"], video["filename"],
                                       video["md5"], args.output_dir)
            if path not in downloaded:
                print(reference)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
