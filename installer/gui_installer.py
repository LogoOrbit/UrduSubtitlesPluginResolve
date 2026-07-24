#!/usr/bin/env python3
"""Graphical one-click installer for Urdu Auto Subtitles (DaVinci Resolve 20+).

This is what gets compiled into ``UrduAutoSubtitles-Setup.exe`` by the GitHub
Actions workflow. It has NO dependency on the plugin package or on the user
having Python — the compiled .exe is fully self-contained (PyInstaller bundles
a Python runtime and tkinter).

What it does, with a window + progress log:
  1. Locate DaVinci Resolve's per-user Fusion scripts folder.
  2. Download the plugin from GitHub and install it + the menu launcher.
  3. Find a *system* Python 3 that Resolve can use (Resolve on Windows drives
     scripting with an externally installed Python). If none is found, offer to
     download and silently install Python 3.11.
  4. Install the ASR dependencies (faster-whisper + bundled ffmpeg) into it.

Because the compiled installer's own interpreter (sys.executable) is the frozen
.exe — not a Python usable by Resolve — we deliberately search for an external
Python instead of using sys.executable.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import urllib.request

# ---- source of the plugin -------------------------------------------------
GITHUB_OWNER = "LogoOrbit"
GITHUB_REPO = "UrduSubtitlesPluginResolve"
GITHUB_REF = "claude/urdu-auto-transcription-davinci-kwmp6a"
TARBALL_URL = (
    f"https://codeload.github.com/{GITHUB_OWNER}/{GITHUB_REPO}/tar.gz/{GITHUB_REF}"
)
PACKAGE_NAME = "urdu_subtitles"
SUPPORT_FOLDER = "UrduSubtitles"
MENU_SCRIPT_NAME = "Urdu Auto Subtitles.py"

# A Resolve-compatible Python to install if the machine has none.
PYTHON_WIN_URL = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"

CREATE_NO_WINDOW = 0x08000000 if sys.platform.startswith("win") else 0


# --------------------------------------------------------------------------- #
# Resolve folder discovery                                                    #
# --------------------------------------------------------------------------- #
def fusion_base_dir() -> str:
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        return os.path.join(
            home, "Library", "Application Support", "Blackmagic Design",
            "DaVinci Resolve", "Fusion",
        )
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA", os.path.join(home, "AppData", "Roaming"))
        return os.path.join(
            appdata, "Blackmagic Design", "DaVinci Resolve", "Support", "Fusion",
        )
    return os.path.join(home, ".local", "share", "DaVinciResolve", "Fusion")


# --------------------------------------------------------------------------- #
# Finding / installing a usable system Python                                  #
# --------------------------------------------------------------------------- #
def _py_ok(path: str) -> bool:
    try:
        out = subprocess.run(
            [path, "-c", "import sys;print(sys.version_info[:2])"],
            capture_output=True, text=True, creationflags=CREATE_NO_WINDOW,
        )
        return out.returncode == 0
    except Exception:
        return False


def find_system_python() -> str | None:
    candidates: list[str] = []
    for name in ("python3", "python"):
        p = shutil.which(name)
        if p:
            candidates.append(p)

    if sys.platform.startswith("win"):
        # The 'py' launcher.
        py = shutil.which("py")
        if py:
            try:
                out = subprocess.run(
                    [py, "-3", "-c", "import sys;print(sys.executable)"],
                    capture_output=True, text=True, creationflags=CREATE_NO_WINDOW,
                )
                if out.returncode == 0 and out.stdout.strip():
                    candidates.append(out.stdout.strip())
            except Exception:
                pass
        # Registry.
        try:
            import winreg  # type: ignore

            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    base = winreg.OpenKey(root, r"SOFTWARE\Python\PythonCore")
                except OSError:
                    continue
                i = 0
                while True:
                    try:
                        ver = winreg.EnumKey(base, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        k = winreg.OpenKey(base, ver + r"\InstallPath")
                        install = winreg.QueryValue(k, None)
                        candidates.append(os.path.join(install, "python.exe"))
                    except OSError:
                        pass
        except Exception:
            pass
        # Common install dirs.
        localapp = os.environ.get("LOCALAPPDATA", "")
        import glob
        candidates += glob.glob(
            os.path.join(localapp, "Programs", "Python", "Python3*", "python.exe"))
        candidates += glob.glob(r"C:\Python3*\python.exe")

    seen = set()
    for c in candidates:
        if c and c not in seen and os.path.isfile(c) and _py_ok(c):
            return c
        seen.add(c)
    return None


def install_python_windows(log) -> str | None:
    log("No Python found. Downloading Python 3.11 (one-time)…")
    tmp = tempfile.mkdtemp(prefix="urdu_py_")
    exe = os.path.join(tmp, "python-setup.exe")
    with urllib.request.urlopen(PYTHON_WIN_URL) as r, open(exe, "wb") as f:
        shutil.copyfileobj(r, f)
    log("Installing Python (a Windows prompt may ask for permission)…")
    subprocess.run(
        [exe, "/quiet", "InstallAllUsers=0", "PrependPath=1",
         "Include_pip=1", "Include_test=0"],
        check=False,
    )
    shutil.rmtree(tmp, ignore_errors=True)
    return find_system_python()


# --------------------------------------------------------------------------- #
# Core install steps                                                          #
# --------------------------------------------------------------------------- #
def download_and_extract(log) -> str:
    log("Downloading the plugin from GitHub…")
    with urllib.request.urlopen(TARBALL_URL) as resp:
        data = resp.read()
    dest = tempfile.mkdtemp(prefix="urdu_src_")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        tar.extractall(dest)
    for name in os.listdir(dest):
        root = os.path.join(dest, name)
        if os.path.isdir(os.path.join(root, PACKAGE_NAME)):
            return root
    raise RuntimeError("Downloaded archive did not contain the plugin package.")


def copy_plugin(repo_root: str, log) -> str:
    fusion = fusion_base_dir()
    support = os.path.join(fusion, SUPPORT_FOLDER)
    util = os.path.join(fusion, "Scripts", "Utility")
    os.makedirs(support, exist_ok=True)
    os.makedirs(util, exist_ok=True)

    pkg_dst = os.path.join(support, PACKAGE_NAME)
    if os.path.isdir(pkg_dst):
        shutil.rmtree(pkg_dst)
    shutil.copytree(
        os.path.join(repo_root, PACKAGE_NAME), pkg_dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    launcher = os.path.join(util, MENU_SCRIPT_NAME)
    with open(launcher, "w", encoding="utf-8") as fh:
        fh.write(
            "# Auto-generated by the Urdu Auto Subtitles installer.\n"
            "import os, sys\n"
            f"_support = {support!r}\n"
            "if _support not in sys.path:\n"
            "    sys.path.insert(0, _support)\n"
            "from urdu_subtitles.resolve.panel import main\n"
            "main()\n"
        )
    log(f"Installed plugin to: {support}")
    log(f"Added menu item: {launcher}")
    return launcher


def install_deps(py: str, log) -> bool:
    log(f"Installing AI engine into: {py}")
    log("(faster-whisper + ffmpeg — this can take a few minutes)")
    subprocess.run([py, "-m", "pip", "install", "--upgrade", "pip"],
                   check=False, creationflags=CREATE_NO_WINDOW)
    proc = subprocess.run(
        [py, "-m", "pip", "install", "faster-whisper>=1.0.0",
         "imageio-ffmpeg>=0.4.9"],
        capture_output=True, text=True, creationflags=CREATE_NO_WINDOW,
    )
    if proc.returncode != 0:
        log("Dependency install reported a problem:")
        log(proc.stderr[-1200:])
        return False
    return True


def run_install(log, done) -> None:
    try:
        repo = download_and_extract(log)
        copy_plugin(repo, log)

        py = find_system_python()
        if not py and sys.platform.startswith("win"):
            py = install_python_windows(log)
        if not py:
            log("\nCould not find or install Python.")
            log("Please install Python 3 from https://www.python.org/downloads/")
            log("(tick 'Add Python to PATH'), then run this installer again.")
            done(False)
            return

        ok = install_deps(py, log)
        log("")
        if ok:
            log("=" * 48)
            log(" SUCCESS — installation complete!")
            log("=" * 48)
            log("Now open DaVinci Resolve and go to:")
            log("   Workspace > Scripts > Utility > 'Urdu Auto Subtitles'")
            log("(Restart Resolve first if it's already open.)")
        else:
            log("Plugin files are installed, but the AI engine did not.")
            log(f"Open a terminal and run:\n   \"{py}\" -m pip install "
                "faster-whisper imageio-ffmpeg")
        done(ok)
    except Exception as exc:  # surface any failure in the window
        log(f"\nERROR: {exc}")
        done(False)


# --------------------------------------------------------------------------- #
# GUI                                                                         #
# --------------------------------------------------------------------------- #
def gui_main() -> None:
    import tkinter as tk
    from tkinter import scrolledtext

    root = tk.Tk()
    root.title("Urdu Auto Subtitles — Installer")
    root.geometry("620x440")

    tk.Label(root, text="Urdu Auto Subtitles for DaVinci Resolve",
             font=("Segoe UI", 14, "bold")).pack(pady=(14, 2))
    tk.Label(root, text="Installs automatic Urdu subtitling into Resolve 20+.",
             font=("Segoe UI", 9)).pack()

    log_box = scrolledtext.ScrolledText(root, height=16, wrap="word",
                                        font=("Consolas", 9))
    log_box.pack(fill="both", expand=True, padx=12, pady=10)
    log_box.configure(state="disabled")

    def log(msg: str) -> None:
        def _append():
            log_box.configure(state="normal")
            log_box.insert("end", msg + "\n")
            log_box.see("end")
            log_box.configure(state="disabled")
        root.after(0, _append)

    btns = tk.Frame(root)
    btns.pack(pady=(0, 12))
    install_btn = tk.Button(btns, text="Install", width=16,
                            font=("Segoe UI", 10, "bold"))
    install_btn.pack(side="left", padx=6)
    close_btn = tk.Button(btns, text="Close", width=10, command=root.destroy)
    close_btn.pack(side="left", padx=6)

    def done(ok: bool) -> None:
        def _fin():
            install_btn.configure(state="normal",
                                  text="Done" if ok else "Retry")
        root.after(0, _fin)

    def start() -> None:
        install_btn.configure(state="disabled", text="Installing…")
        log_box.configure(state="normal")
        log_box.delete("1.0", "end")
        log_box.configure(state="disabled")
        threading.Thread(target=run_install, args=(log, done), daemon=True).start()

    install_btn.configure(command=start)
    log("Click Install to begin.")
    root.mainloop()


def main() -> None:
    # Allow a silent/CLI run with --console (useful for debugging the .exe).
    if "--console" in sys.argv:
        run_install(lambda m: print(m), lambda ok: None)
    else:
        try:
            gui_main()
        except Exception:
            # No display / tkinter missing -> fall back to console.
            run_install(lambda m: print(m), lambda ok: None)


if __name__ == "__main__":
    main()
