import os
import platform
import subprocess
from pathlib import Path


BANNER = "-------------------------CONTENT OF FILES-------------------------"

DEFAULT_IGNORED_EXTS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".heic",
    ".webp",
    ".gif",
    ".bmp",
    ".tiff",
    ".tif",
    ".ico",
    ".svg",
    ".avif",
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".mp3",
    ".wav",
    ".flac",
    ".m4a",
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
    ".dmg",
    ".iso",
    ".exe",
    ".msi",
    ".apk",
    ".bin",
    ".o",
    ".a",
    ".so",
    ".dylib",
    ".dll",
    ".class",
    ".jar",
}


def welcome_message() -> str:
    return (
        "File Content → Clipboard\n"
        "Enter one or more folder paths separated by commas.\n"
        "Then enter unwanted filenames (also comma-separated) to ignore everywhere.\n"
        "Binary/media files are auto-ignored by extension.\n"
    )


def parse_csv_input(raw: str) -> list[str]:
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


def normalize_ignore_set(raw: str) -> set[str]:
    items = parse_csv_input(raw)
    return {Path(x).name for x in items if x}


def validate_folders(paths: list[str]) -> tuple[list[Path], list[str]]:
    ok: list[Path] = []
    bad: list[str] = []
    for p in paths:
        pp = Path(p).expanduser()
        if pp.exists() and pp.is_dir():
            ok.append(pp.resolve())
        else:
            bad.append(p)
    return ok, bad


def is_auto_ignored_by_ext(p: Path) -> bool:
    return p.suffix.lower() in DEFAULT_IGNORED_EXTS


def iter_files(folder: Path, ignore_names: set[str]) -> list[Path]:
    files: list[Path] = []
    for p in folder.rglob("*"):
        if not p.is_file():
            continue
        if p.name in ignore_names:
            continue
        if is_auto_ignored_by_ext(p):
            continue
        files.append(p)
    files.sort(key=lambda x: str(x).lower())
    return files


def read_text_best_effort(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            try:
                data = p.read_bytes()
                return data.decode("utf-8", errors="replace")
            except Exception:
                return ""
    except Exception:
        return ""


def format_output(folders: list[Path], ignore_names: set[str]) -> str:
    lines: list[str] = [BANNER]
    for folder in folders:
        lines.append(f"/{folder.name}")
        for f in iter_files(folder, ignore_names):
            rel = f.relative_to(folder)
            file_label = "/" + str(rel).replace(os.sep, "/")
            lines.append(f"{file_label}:")
            content = read_text_best_effort(f)
            lines.append(content.rstrip("\n"))
            lines.append("---end-of-file")
        lines.append(f"----end-of-/{folder.name}----files")
    return "\n".join(lines) + "\n"


def which(cmd: str) -> str | None:
    try:
        from shutil import which as _which
        return _which(cmd)
    except Exception:
        return None


def copy_to_clipboard(text: str) -> None:
    system = platform.system().lower()

    if system == "darwin":
        subprocess.run(["pbcopy"], input=text, text=True, check=True)
        return

    if system == "windows":
        subprocess.run(["clip"], input=text, text=True, check=True)
        return

    if which("wl-copy"):
        subprocess.run(["wl-copy"], input=text, text=True, check=True)
        return

    if which("xclip"):
        subprocess.run(["xclip", "-selection", "clipboard"], input=text, text=True, check=True)
        return

    if which("xsel"):
        subprocess.run(["xsel", "--clipboard", "--input"], input=text, text=True, check=True)
        return

    raise RuntimeError("No clipboard tool found. Install wl-copy, xclip, or xsel.")


def prompt_folders() -> list[str]:
    raw = input("Folders (comma-separated): ").strip()
    return parse_csv_input(raw)


def prompt_ignore_files() -> set[str]:
    raw = input("Unwanted filenames to ignore (comma-separated, optional): ").strip()
    return normalize_ignore_set(raw)


def main() -> int:
    print(welcome_message())

    folder_inputs = prompt_folders()
    if not folder_inputs:
        print("No folders provided.")
        return 1

    ignore_names = prompt_ignore_files()

    folders, bad = validate_folders(folder_inputs)
    if bad:
        print("These paths are not valid folders:")
        for b in bad:
            print(f"  - {b}")
    if not folders:
        print("No valid folders to process.")
        return 1

    text = format_output(folders, ignore_names)

    try:
        copy_to_clipboard(text)
    except Exception as e:
        print(f"Clipboard copy failed: {e}")
        print("\nOutput (copy manually):\n")
        print(text)
        return 2

    print(f"Copied to clipboard. Processed {len(folders)} folder(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())