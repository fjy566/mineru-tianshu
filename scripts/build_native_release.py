# Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
"""从 Git 提交与已构建前端制作 Windows 联网初始化开发包。"""

import argparse
import hashlib
import io
import json
import re
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ENV_FILES = {"frontend/.env.development", ".env.example", ".env.cpu.example", "backend/.env.example"}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def safe_name(name):
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in name


def allowed(name):
    if not safe_name(name):
        return False
    path = PurePosixPath(name)
    if path.name == ".gitkeep":
        return True
    if any(part in {".git", ".venv", "node_modules", "__pycache__"} for part in path.parts):
        return False
    if path.parts[0] in {"input", "output", "data", "models", "logs", "work"}:
        return False
    if path.name.startswith(".env") and name not in PUBLIC_ENV_FILES and not path.name.endswith(".example"):
        return False
    return path.suffix.lower() not in {".db", ".sqlite", ".pyc", ".lnk"}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def verify_archive(path):
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None, "ZIP CRC verification failed"
        names = archive.namelist()
        assert len(names) == len(set(names)), "Duplicate ZIP entries"
        assert all(safe_name(name) for name in names)
        prefixes = {name.split("/", 1)[0] for name in names}
        assert len(prefixes) == 1
        prefix = prefixes.pop() + "/"
        manifest = json.loads(archive.read(prefix + "PACKAGE_MANIFEST.json"))
        contents = {name[len(prefix) :] for name in names if not name.endswith("/")}
        assert contents == set(manifest["files"]) | {"PACKAGE_MANIFEST.json"}
        for name, expected in manifest["files"].items():
            assert allowed(name), "Forbidden package entry: " + name
            assert sha256(archive.read(prefix + name)) == expected, "Hash mismatch: " + name
        for required in [
            "LICENSE",
            "NOTICE",
            "README.md",
            "安装天枢开发环境.ps1",
            "启动天枢开发版.ps1",
            "停止天枢开发版.ps1",
            "frontend/dist/index.html",
            "backend/requirements.txt",
        ]:
            assert required in contents, "Required package entry missing: " + required
        return {"file_count": len(contents), "version": manifest["version"], "commit": manifest["commit"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"v[0-9][A-Za-z0-9_.-]*", args.version):
        raise ValueError("Invalid release version")
    if git("status", "--porcelain", "--untracked-files=no").strip():
        raise RuntimeError("Commit tracked source changes before packaging")
    commit = git("rev-parse", "--verify", args.ref + "^{commit}").decode().strip()
    if commit != git("rev-parse", "HEAD").decode().strip():
        raise RuntimeError("Build the checked-out HEAD so frontend sources match the release")
    frontend_dist = ROOT / "frontend/dist"
    if not (frontend_dist / "index.html").is_file():
        raise RuntimeError("Run npm ci and npm run build inside frontend first")
    out = args.output_dir or ROOT / "dist/releases" / args.version
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    with zipfile.ZipFile(io.BytesIO(git("archive", "--format=zip", commit))) as source:
        for entry in source.infolist():
            if not entry.is_dir() and allowed(entry.filename):
                files[entry.filename] = source.read(entry)
    for path in sorted(frontend_dist.rglob("*")):
        if path.is_file():
            name = path.relative_to(ROOT).as_posix()
            assert allowed(name)
            files[name] = path.read_bytes()
    notes = git("show", commit + ":docs/RELEASE_" + args.version + ".md")
    files["RELEASE_NOTES.md"] = notes
    info = {
        "version": args.version,
        "commit": commit,
        "frontend_tree": git("rev-parse", commit + ":frontend").decode().strip(),
        "package_kind": "windows-native-development-online-initialization",
        "runtimes_bundled": False,
        "models_bundled": False,
        "dependencies_bundled": False,
        "prebuilt_frontend": True,
        "upstream": "https://github.com/magicyuan876/mineru-tianshu",
        "fork": "https://github.com/fjy566/mineru-tianshu",
    }
    files["RELEASE_INFO.json"] = (json.dumps(info, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    manifest = {
        "version": args.version,
        "commit": commit,
        "files": {name: sha256(value) for name, value in sorted(files.items())},
    }
    files["PACKAGE_MANIFEST.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    prefix = "tianshu-" + args.version + "/"
    package = out / ("tianshu-" + args.version + "-windows-native-dev.zip")
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, value in sorted(files.items()):
            archive.writestr(prefix + name, value)
    verification = verify_archive(package)
    (out / "RELEASE_NOTES.md").write_bytes(notes)
    release_manifest = {
        **info,
        "verification": verification,
        "assets": [
            {"name": path.name, "bytes": path.stat().st_size, "sha256": sha256(path.read_bytes())}
            for path in [package, out / "RELEASE_NOTES.md"]
        ],
    }
    (out / "release-manifest.json").write_text(
        json.dumps(release_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    assets = [package, out / "RELEASE_NOTES.md", out / "release-manifest.json"]
    (out / "SHA256SUMS").write_text(
        "".join(sha256(path.read_bytes()) + "  " + path.name + "\n" for path in assets), encoding="utf-8"
    )
    print(json.dumps({"package": str(package), "bytes": package.stat().st_size, **verification}, ensure_ascii=False))


if __name__ == "__main__":
    main()
