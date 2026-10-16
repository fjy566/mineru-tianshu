# Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
"""Build a self-contained, relocatable Windows x64 release from tested local inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parent.parent
VERSION = "v2.2.1-fjy566.2"
MODEL_NAMES = (
    "iic--punc_ct-transformer_cn-en-common-vocab471067-large",
    "iic--SenseVoiceSmall",
    "iic--speech_campplus_sv_zh-cn_16k-common",
    "iic--speech_fsmn_vad_zh-cn-16k-common-pytorch",
    "iic--speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
)
STORED_SUFFIXES = {
    ".7z", ".bin", ".bz2", ".dll", ".exe", ".gguf", ".gz", ".jpeg", ".jpg", ".mp3", ".mp4",
    ".onnx", ".pdf", ".png", ".pt", ".pth", ".pyd", ".safetensors", ".tar", ".whl", ".zip",
}
TEXT_SUFFIXES = {
    ".cjs", ".conf", ".css", ".csv", ".html", ".ini", ".js", ".json", ".jsx", ".md", ".mjs",
    ".py", ".ps1", ".rst", ".sh", ".sql", ".svg", ".toml", ".ts", ".tsx", ".txt", ".vue", ".xml", ".yaml", ".yml",
}
CHUNK_BYTES = 1_800_000_000
COPY_BUFFER = 4 * 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(COPY_BUFFER):
            digest.update(chunk)
    return digest.hexdigest()


def fixed_timestamp(commit_epoch: int) -> tuple[int, int, int, int, int, int]:
    stamp = datetime.fromtimestamp(max(commit_epoch, 315532800), timezone.utc)
    return stamp.year, stamp.month, stamp.day, stamp.hour, stamp.minute, stamp.second // 2 * 2


def tracked_source_files() -> list[Path]:
    output = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "-z"])
    paths = [Path(os.fsdecode(item)) for item in output.split(b"\0") if item]
    excluded_roots = {".git", ".venv", "data", "input", "logs", "models", "node_modules", "work", "dist"}
    excluded_exact = {
        "backend/.env",
        "docs/RELEASE_v2.2.1-fjy566.1.md",
    }
    kept = []
    for path in paths:
        posix = path.as_posix()
        if path.parts and path.parts[0] in excluded_roots:
            continue
        if posix in excluded_exact or posix.startswith("docs/plans/") or posix.startswith("docs/REVIEW_"):
            continue
        if posix.startswith("frontend/node_modules/") or posix.startswith("frontend/dist/"):
            continue
        if "__pycache__" in path.parts or path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        if path.name in {".env", ".env.cpu"} or path.name.endswith(".db"):
            continue
        if posix.startswith("docker-images/") or posix.startswith("docker-images-cpu/"):
            continue
        kept.append(path)
    return sorted(kept, key=lambda item: item.as_posix().casefold())


def iter_files(base: Path):
    """Walk files without following links so the package cannot escape its input roots."""
    for current, dirnames, filenames in os.walk(base, topdown=True, followlinks=False):
        current_path = Path(current)
        dirnames[:] = sorted(
            (name for name in dirnames if not (current_path / name).is_symlink()), key=str.casefold
        )
        for name in sorted(filenames, key=str.casefold):
            path = current_path / name
            if path.is_symlink() or not path.is_file():
                continue
            yield path


def ensure_safe_archive_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"Unsafe ZIP path: {value}")
    if ":" in path.parts[0]:
        raise ValueError(f"Drive path is not allowed in ZIP: {value}")
    return path.as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-runtime", type=Path, default=ROOT / "work/offline-build-20261016/runtime/python")
    parser.add_argument("--site-packages", type=Path, default=ROOT / ".venv/Lib/site-packages")
    parser.add_argument("--powershell-runtime", type=Path, default=ROOT / "work/offline-build-20261016/runtime/powershell")
    parser.add_argument("--node-runtime", type=Path, default=ROOT / "work/offline-build-20261016/runtime/node")
    parser.add_argument("--node-license", type=Path, default=ROOT / "work/offline-build-20261016/downloads/node-LICENSE-v25.2.1")
    parser.add_argument("--ffmpeg-runtime", type=Path, default=ROOT / "work/offline-build-20261016/runtime/ffmpeg/ffmpeg-n9.0.2-28-g669f5ab083-win64-lgpl-9.0")
    parser.add_argument("--ffmpeg-source", type=Path, default=ROOT / "work/offline-build-20261016/downloads/ffmpeg-669f5ab083-source.tar.gz")
    parser.add_argument("--modelscope-cache", type=Path, default=Path.home() / ".cache/modelscope/models")
    parser.add_argument("--output", type=Path, default=ROOT / "dist/releases" / VERSION)
    parser.add_argument("--chunk-bytes", type=int, default=CHUNK_BYTES)
    args = parser.parse_args()

    python_runtime = args.python_runtime.resolve()
    site_packages = args.site_packages.resolve()
    powershell_runtime = args.powershell_runtime.resolve()
    node_runtime = args.node_runtime.resolve()
    ffmpeg_runtime = args.ffmpeg_runtime.resolve()
    modelscope_cache = args.modelscope_cache.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    required = {
        "Python embeddable runtime": python_runtime / "python.exe",
        "Python package directory": site_packages / "torch" / "__init__.py",
        "PowerShell runtime": powershell_runtime / "pwsh.exe",
        "Node runtime": node_runtime / "node.exe",
        "Node license": args.node_license.resolve(),
        "FFmpeg": ffmpeg_runtime / "bin" / "ffmpeg.exe",
        "FFprobe": ffmpeg_runtime / "bin" / "ffprobe.exe",
        "FFmpeg license": ffmpeg_runtime / "LICENSE.txt",
        "FFmpeg source archive": args.ffmpeg_source.resolve(),
        "Built frontend": ROOT / "frontend/dist/index.html",
        "MinerU 4 ONNX models": ROOT / "models/MinerU-4_models_onnx",
        "MinerU 2.5 VLM models": ROOT / "models/MinerU2.5-Pro-2605-1.2B-GGUF",
    }
    missing = [f"{name}: {path}" for name, path in required.items() if not path.exists()]
    missing.extend(f"Audio model cache: {name}" for name in MODEL_NAMES if not (modelscope_cache / name).is_dir())
    if missing:
        raise SystemExit("Missing offline inputs:\n  " + "\n  ".join(missing))

    pth_files = list(site_packages.glob("*.pth"))
    for pth in pth_files:
        text = pth.read_text(encoding="utf-8", errors="replace")
        if "E:\\ProgramData\\anaconda3" in text or str(ROOT).replace("\\", "\\\\") in text:
            raise SystemExit(f"Non-portable absolute path in {pth.name}")

    commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    epoch = int(subprocess.check_output(["git", "-C", str(ROOT), "show", "-s", "--format=%ct", "HEAD"], text=True).strip())
    timestamp = fixed_timestamp(epoch)
    archive_name = f"tianshu-{VERSION}-windows-offline.zip"
    archive_path = output / archive_name
    if archive_path.exists():
        archive_path.unlink()
    seen: set[str] = set()
    seen_casefold: set[str] = set()
    stored_bytes = 0
    file_count = 0

    def add_file(zf: zipfile.ZipFile, source: Path, target: str, compress_type: int | None = None):
        nonlocal stored_bytes, file_count
        target = ensure_safe_archive_path(target)
        if target.casefold() in seen_casefold:
            raise ValueError(f"Duplicate package path: {target}")
        seen.add(target)
        seen_casefold.add(target.casefold())
        size = source.stat().st_size
        suffix = source.suffix.lower()
        if compress_type is None:
            compress_type = zipfile.ZIP_DEFLATED if suffix in TEXT_SUFFIXES else zipfile.ZIP_STORED
        info = zipfile.ZipInfo(target, date_time=timestamp)
        info.compress_type = compress_type
        info._compresslevel = 1 if compress_type == zipfile.ZIP_DEFLATED else None
        info.create_system = 0
        info.external_attr = 0o600 << 16
        with source.open("rb") as incoming, zf.open(info, "w", force_zip64=True) as outgoing:
            shutil.copyfileobj(incoming, outgoing, COPY_BUFFER)
        stored_bytes += size
        file_count += 1
        if file_count % 10000 == 0:
            print(f"Added {file_count:,} files ({stored_bytes / 1024**3:.2f} GiB source)", flush=True)

    def add_tree(zf: zipfile.ZipFile, base: Path, prefix: str, skip_paths: set[str] | None = None):
        skip_paths = skip_paths or set()
        for source in iter_files(base):
            relative = source.relative_to(base).as_posix()
            if relative in skip_paths or "__pycache__" in PurePosixPath(relative).parts:
                continue
            if source.suffix.lower() in {".pyc", ".pyo"} or source.name in {".DS_Store", "Thumbs.db"}:
                continue
            add_file(zf, source, f"{prefix}/{relative}")

    print(f"Packaging {VERSION} from commit {commit}", flush=True)
    with zipfile.ZipFile(archive_path, "w", allowZip64=True, compresslevel=1) as zf:
        zf.comment = f"{VERSION} | source commit {commit}".encode("ascii")
        for source_rel in tracked_source_files():
            source = ROOT / source_rel
            if not source.is_file():
                continue
            add_file(zf, source, source_rel.as_posix())

        add_tree(zf, ROOT / "frontend/node_modules", "frontend/node_modules")
        add_tree(zf, ROOT / "frontend/dist", "frontend/dist")
        # python312._pth is deliberately rewritten so the embeddable runtime uses only this package.
        pth_source = python_runtime / "python312._pth"
        for source in iter_files(python_runtime):
            relative = source.relative_to(python_runtime).as_posix()
            if relative == "python312._pth" or relative.startswith("Lib/site-packages/"):
                continue
            add_file(zf, source, f"runtime/python/{relative}")
        pth_info = zipfile.ZipInfo("runtime/python/python312._pth", date_time=timestamp)
        pth_info.compress_type = zipfile.ZIP_STORED
        pth_info.create_system = 0
        # Embeddable Python ignores cwd and PYTHONPATH, so expose this package's backend by relative path.
        zf.writestr(pth_info, b"python312.zip\n.\nLib\\site-packages\n..\\..\\backend\nimport site\n")
        seen.add("runtime/python/python312._pth")
        seen_casefold.add("runtime/python/python312._pth".casefold())
        file_count += 1
        import importlib.metadata

        package_rows = []
        for distribution in sorted(
            importlib.metadata.distributions(path=[str(site_packages)]),
            key=lambda item: (item.metadata.get("Name", "").casefold(), item.version),
        ):
            metadata = distribution.metadata
            name = metadata.get("Name", "unknown")
            version = distribution.version
            license_value = metadata.get("License-Expression") or metadata.get("License") or "See package .dist-info license files"
            home = metadata.get("Home-page") or (metadata.get_all("Project-URL") or [""])[0]
            package_rows.append(f"{name}=={version} | {license_value} | {home}".rstrip())
        package_info = "Bundled Python distributions (license files are retained in their .dist-info directories):\n\n" + "\n".join(package_rows) + "\n"
        zf.writestr("runtime/python/THIRD_PARTY_PACKAGES.txt", package_info.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED, compresslevel=1)
        seen.add("runtime/python/THIRD_PARTY_PACKAGES.txt")
        seen_casefold.add("runtime/python/THIRD_PARTY_PACKAGES.txt".casefold())
        file_count += 1
        add_tree(zf, site_packages, "runtime/python/Lib/site-packages")

        add_tree(zf, powershell_runtime, "runtime/powershell")
        add_file(zf, node_runtime / "node.exe", "runtime/node/node.exe")
        add_file(zf, args.node_license.resolve(), "runtime/node/LICENSE")
        add_file(zf, ffmpeg_runtime / "bin/ffmpeg.exe", "runtime/ffmpeg/ffmpeg.exe")
        add_file(zf, ffmpeg_runtime / "bin/ffprobe.exe", "runtime/ffmpeg/ffprobe.exe")
        add_file(zf, ffmpeg_runtime / "LICENSE.txt", "runtime/ffmpeg/LICENSE.txt")
        add_file(zf, args.ffmpeg_source.resolve(), "runtime/ffmpeg/source/ffmpeg-669f5ab083-source.tar.gz")
        ffmpeg_build_info = (
            "FFmpeg source commit: 669f5ab083\n"
            "BtbN build release: autobuild-2026-10-15-13-03\n"
            "Target: win64 LGPL 3+\n"
            "The build configuration has no --enable-gpl or --enable-nonfree; GPL-only x264/x265 encoders are disabled.\n"
            "Corresponding source is in source/ffmpeg-669f5ab083-source.tar.gz.\n"
        )
        zf.writestr("runtime/ffmpeg/BUILD_INFO.txt", ffmpeg_build_info.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED, compresslevel=1)
        seen.add("runtime/ffmpeg/BUILD_INFO.txt")
        seen_casefold.add("runtime/ffmpeg/BUILD_INFO.txt".casefold())
        file_count += 1

        add_tree(zf, ROOT / "models/MinerU-4_models_onnx", "models/MinerU-4_models_onnx")
        add_tree(zf, ROOT / "models/MinerU2.5-Pro-2605-1.2B-GGUF", "models/MinerU2.5-Pro-2605-1.2B-GGUF")
        for model_name in MODEL_NAMES:
            add_tree(zf, modelscope_cache / model_name, f"models/modelscope_cache/models/{model_name}")

    print(f"ZIP created: {archive_path} ({archive_path.stat().st_size / 1024**3:.2f} GiB)", flush=True)
    print("Verifying ZIP CRC and forbidden paths...", flush=True)
    with zipfile.ZipFile(archive_path, "r") as zf:
        broken = zf.testzip()
        if broken:
            raise SystemExit(f"ZIP CRC failure: {broken}")
        names = zf.namelist()
        if len(names) != len(set(names)):
            raise SystemExit("ZIP contains duplicate members")
        forbidden_prefixes = ("data/", "input/", "logs/", "work/", ".git/", "models/PDF-Extract-Kit-1.0/")
        bad = [name for name in names if name.startswith(forbidden_prefixes) or PurePosixPath(name).name in {".env", ".env.cpu"}]
        if bad:
            raise SystemExit("Forbidden package paths: " + ", ".join(bad[:20]))
        for required_member in (
            "启动天枢离线版.ps1", "停止天枢离线版.ps1", "backend/start_all.py", "frontend/src/main.ts",
            "runtime/python/python.exe", "runtime/python/Lib/site-packages/torch/__init__.py",
            "runtime/powershell/pwsh.exe", "runtime/node/node.exe", "runtime/ffmpeg/ffmpeg.exe",
            "models/MinerU-4_models_onnx", "models/MinerU2.5-Pro-2605-1.2B-GGUF",
        ):
            if not any(name == required_member or name.startswith(required_member + "/") for name in names):
                raise SystemExit(f"Required package member missing: {required_member}")
        print(f"ZIP CRC OK; {len(names):,} members", flush=True)

    archive_hash = sha256_file(archive_path)
    part_records = []
    with archive_path.open("rb") as stream:
        index = 1
        while True:
            chunk_path = output / f"{archive_name}.part{index:03d}"
            digest = hashlib.sha256()
            size = 0
            with chunk_path.open("wb") as chunk_out:
                while size < args.chunk_bytes:
                    data = stream.read(min(COPY_BUFFER, args.chunk_bytes - size))
                    if not data:
                        break
                    chunk_out.write(data)
                    digest.update(data)
                    size += len(data)
            if size == 0:
                chunk_path.unlink(missing_ok=True)
                break
            part_records.append({"name": chunk_path.name, "bytes": size, "sha256": digest.hexdigest()})
            print(f"Split {chunk_path.name}: {size / 1024**3:.2f} GiB", flush=True)
            index += 1

    manifest = {
        "schema_version": 1,
        "tag": VERSION,
        "commit": commit,
        "platform": "Windows x64",
        "archive": {
            "name": archive_name,
            "bytes": archive_path.stat().st_size,
            "sha256": archive_hash,
            "parts": part_records,
        },
        "contents": {
            "python": "3.12.10 embeddable + tested site-packages",
            "node": "v25.2.1",
            "powershell": "7.6.5",
            "mineru": "4.0.12",
            "models": ["MinerU-4 ONNX", "MinerU 2.5 Pro 1.2B GGUF", "five ModelScope audio models"],
            "excluded": ["unused PDF-Extract-Kit-1.0", "watermark detector with research-only use restrictions", "user data and credentials"],
        },
    }
    (output / "release-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    helper_path = output / "JOIN_OFFLINE_PACKAGE.ps1"
    notes_path = output / "RELEASE_NOTES.md"
    licenses_path = output / "THIRD_PARTY_LICENSES_OFFLINE.md"
    shutil.copy2(ROOT / "JOIN_OFFLINE_PACKAGE.ps1", helper_path)
    shutil.copy2(ROOT / "docs/RELEASE_v2.2.1-fjy566.2.md", notes_path)
    shutil.copy2(ROOT / "docs/THIRD_PARTY_LICENSES_OFFLINE.md", licenses_path)
    sums = [f"{record['sha256']}  {record['name']}" for record in part_records]
    sums.extend(
        [
            f"{archive_hash}  {archive_name} (reassembled ZIP)",
            f"{sha256_file(helper_path)}  {helper_path.name}",
            f"{sha256_file(notes_path)}  {notes_path.name}",
            f"{sha256_file(licenses_path)}  {licenses_path.name}",
        ]
    )
    (output / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(json.dumps({"archive": str(archive_path), "bytes": archive_path.stat().st_size, "sha256": archive_hash, "parts": part_records, "members": file_count, "commit": commit}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
