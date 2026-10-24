"""Postavlja noćni raspored za nightly_update.py (Windows Task Scheduler / crontab)."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

from config import NIGHTLY_SCHEDULE_TIME, NIGHTLY_TASK_NAME, PROJECT_ROOT


def python_executable() -> Path:
    candidate = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
    if candidate.exists():
        return candidate
    candidate = PROJECT_ROOT / "venv" / "bin" / "python"
    if candidate.exists():
        return candidate
    return Path(sys.executable).resolve()


def nightly_script() -> Path:
    return PROJECT_ROOT / "nightly_update.py"


def windows_launcher() -> Path:
    """.bat izbjegava probleme s navodnicima u schtasks /TR."""
    return PROJECT_ROOT / "run_nightly.bat"


def write_windows_launcher(python_path: Path, script_path: Path) -> Path:
    bat = windows_launcher()
    bat.write_text(
        "\r\n".join(
            [
                "@echo off",
                f'cd /d "{PROJECT_ROOT}"',
                f'"{python_path}" "{script_path}"',
                "exit /b %ERRORLEVEL%",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return bat


def install_windows_task() -> int:
    python_path = python_executable()
    script_path = nightly_script()
    if not script_path.exists():
        print(f"Nedostaje {script_path}", file=sys.stderr)
        return 1

    bat = write_windows_launcher(python_path, script_path)
    cmd = [
        "schtasks",
        "/Create",
        "/TN",
        NIGHTLY_TASK_NAME,
        "/TR",
        str(bat),
        "/SC",
        "DAILY",
        "/ST",
        NIGHTLY_SCHEDULE_TIME,
        "/F",
    ]
    print("Kreiram Windows Task Scheduler zadatak...")
    print(f"  ime:     {NIGHTLY_TASK_NAME}")
    print(f"  vrijeme: svaki dan u {NIGHTLY_SCHEDULE_TIME}")
    print(f"  launcher: {bat}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(result.stdout.strip() or result.stderr.strip(), file=sys.stderr)
        print(
            "Ako nemaš prava, pokreni PowerShell kao Administrator "
            "ili ručno dodaj zadatak u Task Scheduler.",
            file=sys.stderr,
        )
        return result.returncode

    print((result.stdout or "Zadatak je kreiran.").strip())
    print(f"Provjera: schtasks /Query /TN \"{NIGHTLY_TASK_NAME}\" /V /FO LIST")
    print(f"Ručni test: schtasks /Run /TN \"{NIGHTLY_TASK_NAME}\"")
    return 0


def print_crontab_line() -> int:
    python_path = python_executable()
    script_path = nightly_script()
    hour, minute = NIGHTLY_SCHEDULE_TIME.split(":")
    line = (
        f"{int(minute)} {int(hour)} * * * "
        f'cd "{PROJECT_ROOT}" && "{python_path}" "{script_path}" '
        f'>> "{PROJECT_ROOT / "automation.log"}" 2>&1'
    )
    print("Na macOS / Linuxu dodaj ovu liniju u crontab (`crontab -e`):")
    print()
    print(line)
    print()
    print("Pokreće nightly_update.py svaki dan u 03:00 lokalnog vremena.")
    return 0


def main() -> int:
    system = platform.system()
    print(f"OS: {system}")
    print(f"Projekt: {PROJECT_ROOT}")
    print(f"Python: {python_executable()}")
    print(f"Skripta: {nightly_script()}")
    print()

    if system == "Windows":
        return install_windows_task()
    if system in {"Linux", "Darwin"}:
        return print_crontab_line()

    print(f"Nepoznat OS '{system}'. Ispiši crontab ručno ili koristi Task Scheduler.", file=sys.stderr)
    return print_crontab_line()


if __name__ == "__main__":
    raise SystemExit(main())
