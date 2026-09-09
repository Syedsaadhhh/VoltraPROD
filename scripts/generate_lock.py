import subprocess
import pathlib
import sys

def main():
    out = subprocess.check_output(
        ["uv", "pip", "freeze", "--python", ".venv/Scripts/python.exe"],
        text=True,
    )
    clean_lines = []
    for line in out.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pkg = line.split("==")[0].lower().strip()
        if pkg in ["pywin32", "pywin32-ctypes"]:
            clean_lines.append(f'{line}; sys_platform == "win32"')
        else:
            clean_lines.append(line)

    target = pathlib.Path("backend/requirements.lock")
    target.write_text("\n".join(clean_lines) + "\n", encoding="utf-8")
    print(f"Generated UTF-8 backend/requirements.lock with {len(clean_lines)} packages.")

if __name__ == "__main__":
    main()
