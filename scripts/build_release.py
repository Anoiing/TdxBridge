from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


REQUIRED_FILES = [
    "00-右键管理员打开安装-TdxBridge.cmd",
    "01-启动-TdxBridge.cmd",
    "02-停止-TdxBridge.cmd",
    "03-右键管理员打开卸载-TdxBridge.cmd",
    "README.md",
    "requirements.txt",
]

REQUIRED_DIRS = [
    "app",
    "scripts",
    "config",
    "docs",
    "tdxbridge-agent",
]

RELEASE_SCRIPT_ALLOWLIST = {
    "Install-TdxBridge.ps1",
    "Start-TdxBridge.ps1",
    "Stop-TdxBridge.ps1",
    "Uninstall-TdxBridge.ps1",
}

def echo(title: str) -> None:
    print()
    print(f"========== {title} ==========")


def project_root_from(value: str | None) -> Path:
    if value and value.strip():
        return Path(value).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def normalize_powershell_files(base_dir: Path) -> None:
    for path in base_dir.glob("*.ps1"):
        text = path.read_bytes().decode("utf-8-sig")
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
        path.write_bytes(b"\xef\xbb\xbf" + normalized.encode("utf-8"))


def assert_inputs(project_root: Path) -> None:
    for file_name in REQUIRED_FILES:
        path = project_root / file_name
        if not path.exists():
            raise FileNotFoundError(f"缺少文件：{path}")
    for dir_name in REQUIRED_DIRS:
        path = project_root / dir_name
        if not path.exists() or not path.is_dir():
            raise FileNotFoundError(f"缺少目录：{path}")
    if not (project_root / "config" / "bridge.example.json").exists():
        raise FileNotFoundError(f"缺少文件：{project_root / 'config' / 'bridge.example.json'}")


def remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def copy_release_tree(project_root: Path, package_root: Path) -> None:
    for dir_name in REQUIRED_DIRS:
        src_dir = project_root / dir_name
        dst_dir = package_root / dir_name
        ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
        if dir_name == "config":
            ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "bridge.json", "bridge.local.json")
        shutil.copytree(src_dir, dst_dir, ignore=ignore)
        print(f"已复制目录：{dir_name}")
    for file_name in REQUIRED_FILES:
        shutil.copy2(project_root / file_name, package_root / file_name)
        print(f"已复制文件：{file_name}")


def cleanup_release_tree(package_root: Path) -> None:
    excluded_paths = [
        package_root / "10-打包发布-TdxBridge.cmd",
        package_root / "10-打包发布-TdxBridge.command",
        package_root / "app" / "__pycache__",
        package_root / "scripts" / "__pycache__",
        package_root / "config" / "__pycache__",
        package_root / "config" / "bridge.json",
        package_root / "config" / "bridge.local.json",
    ]
    for path in excluded_paths:
        remove_path(path)

    for path in package_root.glob("scripts/*.ps1"):
        if path.name not in RELEASE_SCRIPT_ALLOWLIST:
            remove_path(path)

    for path in package_root.glob("scripts/*.py"):
        if path.suffix == ".py":
            remove_path(path)

    for pyc in package_root.rglob("*.pyc"):
        pyc.unlink()


def normalize_release_tree(package_root: Path) -> None:
    for path in package_root.glob("*.cmd"):
        text = path.read_bytes().decode("utf-8-sig")
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
        path.write_bytes(normalized.encode("utf-8"))
    normalize_powershell_files(package_root / "scripts")


def create_zip(dist_root: Path, package_root: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        for path in sorted(package_root.rglob("*")):
            arcname = Path("TdxBridge") / path.relative_to(package_root)
            arcname_text = str(arcname).replace("\\", "/")
            if path.is_dir():
                zf.writestr(f"{arcname_text}/", "")
            else:
                zf.write(path, arcname_text)


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 TdxBridge 发布包")
    parser.add_argument("--project-root", default="", help="项目根目录，默认自动推断")
    args = parser.parse_args()

    project_root = project_root_from(args.project_root)
    dist_root = project_root / "dist"
    package_root = dist_root / "TdxBridge"
    zip_path = dist_root / "TdxBridge-release.zip"

    echo("检查打包输入")
    assert_inputs(project_root)
    print(f"项目根目录：{project_root}")

    echo("清理旧的发布目录")
    remove_path(package_root)
    remove_path(zip_path)
    dist_root.mkdir(parents=True, exist_ok=True)
    package_root.mkdir(parents=True, exist_ok=True)

    echo("复制发布文件")
    copy_release_tree(project_root, package_root)

    echo("清理不应进入发布包的内容")
    cleanup_release_tree(package_root)
    normalize_release_tree(package_root)
    print("已完成发布目录清理")

    echo("生成压缩包")
    create_zip(dist_root, package_root, zip_path)
    print(f"发布目录：{package_root}")
    print(f"发布压缩包：{zip_path}")

    echo("打包完成")
    print("TdxBridge 发布包已生成，可直接分发给 Windows 用户。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
