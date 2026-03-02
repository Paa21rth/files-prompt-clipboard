import os
import platform
import subprocess
from pathlib import Path


BANNER_CONTENT = "-------------------------CONTENT OF FILES-------------------------"
BANNER_TREE = "-------------------------FILE STRUCTURE-------------------------"

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
        "Modes:\n"
        "  - route-to-leaf = no  → flat list per provided folder\n"
        "  - route-to-leaf = yes → tree traversal, printing paths per leaf file\n"
        "You can also toggle whether hidden files/folders (starting with '.') are included.\n"
        "At the end, a tree-like file structure will be appended.\n"
    )


def parse_csv_input(raw: str) -> list[str]:
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


def normalize_ignore_set(raw: str) -> set[str]:
    items = parse_csv_input(raw)
    return {Path(x).name for x in items if x}


def parse_yes_no(raw: str, default: bool = False) -> bool:
    s = (raw or "").strip().lower()
    if not s:
        return default
    yes = {"y", "yes", "ye", "yep", "yeah", "ja", "j", "ok", "okay", "o", "oui", "si"}
    no = {"n", "no", "nein", "nop"}
    if s in yes:
        return True
    if s in no:
        return False
    if s.startswith("y"):
        return True
    if s.startswith("n"):
        return False
    return default


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


def is_hidden_path(p: Path) -> bool:
    return any(part.startswith(".") and part not in (".", "..") for part in p.parts)


def is_auto_ignored_by_ext(p: Path) -> bool:
    return p.suffix.lower() in DEFAULT_IGNORED_EXTS


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


def iter_files_flat(folder: Path, ignore_names: set[str], include_hidden: bool) -> list[Path]:
    files: list[Path] = []
    for p in folder.rglob("*"):
        if not p.is_file():
            continue
        if p.name in ignore_names:
            continue
        if is_auto_ignored_by_ext(p):
            continue
        if not include_hidden and is_hidden_path(p.relative_to(folder)):
            continue
        files.append(p)
    files.sort(key=lambda x: str(x).lower())
    return files


def format_output_flat(folders: list[Path], ignore_names: set[str], include_hidden: bool) -> str:
    lines: list[str] = [BANNER_CONTENT]
    for folder in folders:
        lines.append(f"/{folder.name}")
        for f in iter_files_flat(folder, ignore_names, include_hidden):
            rel = f.relative_to(folder)
            file_label = "/" + str(rel).replace(os.sep, "/")
            lines.append(f"{file_label}:")
            content = read_text_best_effort(f)
            lines.append(content.rstrip("\n"))
            lines.append("---end-of-file")
        lines.append(f"----end-of-/{folder.name}----files")
    return "\n".join(lines) + "\n"


def list_dir_sorted(p: Path) -> list[Path]:
    try:
        items = list(p.iterdir())
    except Exception:
        return []
    items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
    return items


def format_output_route_to_leaf(
    roots: list[Path],
    ignore_names: set[str],
    include_hidden: bool,
) -> str:
    lines: list[str] = [BANNER_CONTENT]

    def walk_dir(root: Path, current: Path) -> None:
        for entry in list_dir_sorted(current):
            rel = entry.relative_to(root)
            if not include_hidden and is_hidden_path(rel):
                continue

            if entry.is_dir():
                walk_dir(root, entry)
                continue

            if entry.name in ignore_names:
                continue
            if is_auto_ignored_by_ext(entry):
                continue

            route_parts = [root.name] + list(rel.parts[:-1])
            route = "/" + "/".join(route_parts) if route_parts else f"/{root.name}"

            lines.append(route)
            lines.append(f"/{rel.name}:")
            content = read_text_best_effort(entry)
            lines.append(content.rstrip("\n"))
            lines.append("---end-of-file")

    for root in roots:
        walk_dir(root, root)
        lines.append(f"----end-of-/{root.name}----files")

    return "\n".join(lines) + "\n"


def build_tree_lines(root: Path, include_hidden: bool) -> list[str]:
    lines: list[str] = []

    def children(dir_path: Path) -> list[Path]:
        items = list_dir_sorted(dir_path)
        if include_hidden:
            return items
        out: list[Path] = []
        for it in items:
            rel = it.relative_to(root)
            if is_hidden_path(rel):
                continue
            out.append(it)
        return out

    def walk(dir_path: Path, prefix: str) -> None:
        items = children(dir_path)
        for idx, item in enumerate(items):
            last = idx == (len(items) - 1)
            connector = "└── " if last else "├── "
            lines.append(prefix + connector + item.name)
            if item.is_dir():
                extension = "    " if last else "│   "
                walk(item, prefix + extension)

    lines.append(root.name)
    walk(root, "")
    return lines


def format_file_structure(folders: list[Path], include_hidden: bool) -> str:
    lines: list[str] = [BANNER_TREE]
    for root in folders:
        lines.extend(build_tree_lines(root, include_hidden))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def prompt_route_to_leaf() -> bool:
    raw = input("Route-to-leaf mode? (yes/no): ").strip()
    return parse_yes_no(raw, default=False)


def prompt_include_hidden() -> bool:
    raw = input("Include hidden files/folders (starting with '.')? (yes/no): ").strip()
    return parse_yes_no(raw, default=True)


def prompt_folders() -> list[str]:
    raw = input("Folders (comma-separated): ").strip()
    return parse_csv_input(raw)


def prompt_ignore_files() -> set[str]:
    raw = input("Unwanted filenames to ignore (comma-separated, optional): ").strip()
    return normalize_ignore_set(raw)


def main() -> int:
    print(welcome_message())

    route_to_leaf = prompt_route_to_leaf()
    include_hidden = prompt_include_hidden()

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

    if route_to_leaf:
        content_part = format_output_route_to_leaf(folders, ignore_names, include_hidden)
    else:
        content_part = format_output_flat(folders, ignore_names, include_hidden)

    tree_part = format_file_structure(folders, include_hidden)

    full_text = content_part.rstrip("\n") + "\n\n" + tree_part

    try:
        copy_to_clipboard(full_text)
    except Exception as e:
        print(f"Clipboard copy failed: {e}")
        print("\nOutput (copy manually):\n")
        print(full_text)
        return 2

    print(f"Copied to clipboard. Processed {len(folders)} folder(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())