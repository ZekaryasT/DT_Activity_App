import os
import sys
import subprocess
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox
from openpyxl.styles import Font
import requests
from datetime import datetime

# ---------------------- CONFIG ----------------------
APP_VERSION = "2.1.0"  # Bump this AND version.txt together for every release

# --- GitHub repo that hosts your compiled releases ---
GITHUB_OWNER = "ZekaryasT"
GITHUB_REPO = "DT_Activity_App"
EXE_ASSET_NAME = "DumpTruckActivityAdjuster.exe"  # exact filename you upload to each GitHub Release

# version.txt lives as a plain text file in the repo (safe to expose - it's just a number)
VERSION_URL = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/refs/heads/main/version.txt"

# "latest" release download link - GitHub always resolves this to the newest release's asset
EXE_DOWNLOAD_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest/download/{EXE_ASSET_NAME}"

PASSWORD = "ZackT"
MAX_TRIES = 3

# ---------------------- COLOR PALETTE ----------------------
COLOR_BG = "#0f1e2e"
COLOR_PANEL = "#16293d"
COLOR_ACCENT = "#2fb8a3"
COLOR_ACCENT_DARK = "#219684"
COLOR_TEXT = "#eaf2f5"
COLOR_SUBTEXT = "#9db3c2"
COLOR_SUCCESS = "#2fb8a3"
FONT_FAMILY = "Segoe UI"
# ----------------------------------------------------

file_path = ""
login_attempts = 0


# ---------------------- STYLED WIDGET HELPERS ----------------------
def make_button(parent, text, command, bg=COLOR_ACCENT, hover=COLOR_ACCENT_DARK, fg="#0f1e2e", width=20):
    btn = tk.Button(
        parent, text=text, command=command,
        bg=bg, fg=fg, activebackground=hover, activeforeground=fg,
        font=(FONT_FAMILY, 10, "bold"), relief="flat", bd=0,
        padx=14, pady=8, width=width, cursor="hand2"
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=hover))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg))
    return btn


def card(parent, **kwargs):
    return tk.Frame(parent, bg=COLOR_PANEL, highlightthickness=1,
                     highlightbackground="#22384f", **kwargs)


# ---------------------- LOGIN ----------------------
def login():
    global login_attempts
    entered_pass = password_entry.get()
    login_attempts += 1
    if entered_pass == PASSWORD:
        login_window.destroy()
        main_app()
    else:
        remaining = MAX_TRIES - login_attempts
        if remaining <= 0:
            messagebox.showerror("Access Denied", "Maximum login attempts reached!")
            sys.exit()
        else:
            messagebox.showerror("Incorrect Password", f"Wrong password! {remaining} tries left.")


# ---------------------- SELF-UPDATE (compiled EXE only) ----------------------
def is_frozen():
    """True only when running as a PyInstaller-built .exe, not a raw .py script."""
    return getattr(sys, "frozen", False)


def download_new_exe(progress_callback=None):
    """Stream-download the latest release exe to a temp file next to the current exe."""
    current_exe = os.path.abspath(sys.executable)
    app_dir = os.path.dirname(current_exe)
    new_exe_path = os.path.join(app_dir, "_update_download.exe")

    with requests.get(EXE_DOWNLOAD_URL, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(new_exe_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total:
                        progress_callback(downloaded / total)

    return new_exe_path, current_exe


def launch_swap_helper(new_exe_path, current_exe):
    """
    Windows won't let a running exe overwrite itself, so we hand off to a tiny
    batch script that waits for this process to fully exit, then swaps the
    files and relaunches the new version. The batch file deletes itself last.
    """
    app_dir = os.path.dirname(current_exe)
    exe_name = os.path.basename(current_exe)
    new_name = os.path.basename(new_exe_path)
    pid = os.getpid()
    helper_path = os.path.join(app_dir, "_update_helper.bat")

    script = f"""@echo off
:waitloop
tasklist /fi "PID eq {pid}" | find "{pid}" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto waitloop
)
del /f /q "{exe_name}"
ren "{new_name}" "{exe_name}"
start "" "{exe_name}"
del /f /q "%~f0"
"""
    with open(helper_path, "w") as f:
        f.write(script)

    subprocess.Popen(
        ["cmd", "/c", helper_path],
        cwd=app_dir,
        creationflags=subprocess.CREATE_NO_WINDOW
    )


def run_update(status_label, win):
    try:
        status_label.config(text="Downloading update...", fg=COLOR_SUBTEXT)
        win.update()

        def on_progress(fraction):
            status_label.config(text=f"Downloading update... {int(fraction * 100)}%")
            win.update()

        new_exe_path, current_exe = download_new_exe(on_progress)

        status_label.config(text="Installing update...", fg=COLOR_SUCCESS)
        win.update()

        launch_swap_helper(new_exe_path, current_exe)

        win.destroy()
        root.destroy()
        sys.exit()

    except Exception as e:
        messagebox.showerror("Update Failed", f"Could not install the update.\n{e}")


def show_update_prompt(new_version):
    win = tk.Toplevel(root)
    win.title("Update Available")
    win.configure(bg=COLOR_PANEL)
    win.geometry("380x190")
    win.resizable(False, False)
    win.grab_set()

    tk.Label(
        win, text="A new version is available",
        font=(FONT_FAMILY, 13, "bold"), bg=COLOR_PANEL, fg=COLOR_TEXT
    ).pack(pady=(20, 4))

    tk.Label(
        win, text=f"Installed: v{APP_VERSION}   →   Latest: v{new_version}",
        font=(FONT_FAMILY, 10), bg=COLOR_PANEL, fg=COLOR_SUBTEXT
    ).pack(pady=(0, 16))

    status_label = tk.Label(win, text="", font=(FONT_FAMILY, 9), bg=COLOR_PANEL, fg=COLOR_SUBTEXT)
    status_label.pack(pady=(0, 8))

    btn_frame = tk.Frame(win, bg=COLOR_PANEL)
    btn_frame.pack(pady=4)

    make_button(btn_frame, "Update Now", lambda: run_update(status_label, win), width=12).pack(side="left", padx=8)
    make_button(btn_frame, "Later", win.destroy, bg="#2a3f56", hover="#33495f",
                fg=COLOR_TEXT, width=12).pack(side="left", padx=8)


def check_update_silent():
    try:
        online_version = requests.get(VERSION_URL, timeout=10).text.strip()
        if not online_version or online_version == APP_VERSION:
            messagebox.showinfo(
                f"Check Update (v{APP_VERSION})",
                f"You are using the latest version ({APP_VERSION})."
            )
            return

        if not is_frozen():
            messagebox.showinfo(
                "Update Available",
                f"Version {online_version} is available.\n\n"
                "Automatic install only works in the compiled .exe build - "
                "you're currently running the raw script, so there's nothing to swap.\n"
                "Build and test the .exe to verify the update flow."
            )
            return

        show_update_prompt(online_version)

    except requests.exceptions.RequestException as e:
        messagebox.showerror("Update Check Failed", f"Could not reach the update server.\n{e}")
    except Exception as e:
        messagebox.showerror("Update Check Failed", f"Could not check for updates.\n{e}")


# ---------------------- FILE SELECTION ----------------------
def select_file():
    global file_path
    file_path = filedialog.askopenfilename(
        title="Select CSV file",
        filetypes=[("CSV files", "*.csv")]
    )
    if file_path:
        label_file.config(text=os.path.basename(file_path), fg=COLOR_TEXT)
        status_var.set("File loaded. Choose a mode and click Process File.")


# ---------------------- FILE PROCESSING ----------------------
def process_file():
    global file_path

    if not file_path:
        messagebox.showerror("Error", "Please select a file first.")
        return

    try:
        status_var.set("Processing...")
        root.update()

        df = pd.read_csv(file_path)
        df = df.iloc[:, :4].copy()
        df.columns = ["Data Code No.", "Plate No.", "Activity", "Zone"]

        for col in ["Plate No.", "Activity", "Zone"]:
            df[col] = df[col].astype(str).str.strip()

        df_result = df.copy()
        mode = mode_var.get()

        if mode == "activity":
            df_result["dup"] = df_result.groupby(["Activity", "Plate No."]).cumcount()
        elif mode == "zone":
            df_result["dup"] = df_result.groupby(["Zone", "Plate No."]).cumcount()
        elif mode == "both":
            df_result["dup_activity"] = df_result.groupby(["Activity", "Plate No."]).cumcount()
            df_result["dup_zone"] = df_result.groupby(["Zone", "Plate No."]).cumcount()
            df_result["dup"] = df_result[["dup_activity", "dup_zone"]].max(axis=1)
            df_result.drop(columns=["dup_activity", "dup_zone"], inplace=True)
        else:
            messagebox.showerror("Error", "Please select a mode.")
            status_var.set("Ready.")
            return

        mask = df_result["dup"] > 0
        df_result.loc[mask, "Activity"] = df_result.loc[mask, "Activity"] + df_result.loc[mask, "dup"].apply(lambda x: "-" * x)
        changed_rows = df_result.index[mask].tolist()
        df_result.drop(columns=["dup"], inplace=True)

        base_dir = os.path.dirname(file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_output = os.path.join(base_dir, f"processed_dumptrucks_{timestamp}.csv")
        excel_output = os.path.join(base_dir, f"processed_dumptrucks_{timestamp}.xlsx")

        df_result.to_csv(csv_output, index=False)
        with pd.ExcelWriter(excel_output, engine="openpyxl") as writer:
            df_result.to_excel(writer, index=False, sheet_name="Sheet1")
            worksheet = writer.sheets["Sheet1"]
            bold_font = Font(bold=True)
            activity_col_index = df_result.columns.get_loc("Activity") + 1
            for row in range(2, len(df_result) + 2):
                if (row - 2) in changed_rows:
                    worksheet.cell(row=row, column=activity_col_index).font = bold_font

        os.startfile(base_dir)

        status_var.set(f"Done. {len(changed_rows)} row(s) adjusted.")
        messagebox.showinfo("Success", f"Processing complete!\nFiles saved successfully.\nTimestamp: {timestamp}")

    except Exception as e:
        status_var.set("Error occurred.")
        messagebox.showerror("Error", str(e))


# ---------------------- MAIN APP GUI ----------------------
def main_app():
    global label_file, mode_var, root, status_var

    root = tk.Tk()
    root.title("Dump Truck Activity Adjuster")
    root.geometry("480x560")
    root.configure(bg=COLOR_BG)
    root.resizable(False, False)

    header = tk.Frame(root, bg=COLOR_BG)
    header.pack(fill="x", pady=(24, 10), padx=24)

    tk.Label(
        header, text="🚛  Dump Truck Activity Adjuster",
        font=(FONT_FAMILY, 17, "bold"), bg=COLOR_BG, fg=COLOR_TEXT
    ).pack(anchor="w")

    tk.Label(
        header, text="Clean and de-duplicate daily dump truck activity logs",
        font=(FONT_FAMILY, 9), bg=COLOR_BG, fg=COLOR_SUBTEXT
    ).pack(anchor="w", pady=(2, 0))

    file_card = card(root)
    file_card.pack(fill="x", padx=24, pady=10)

    tk.Label(
        file_card, text="1. SELECT FILE", font=(FONT_FAMILY, 9, "bold"),
        bg=COLOR_PANEL, fg=COLOR_ACCENT
    ).pack(anchor="w", padx=16, pady=(14, 4))

    file_row = tk.Frame(file_card, bg=COLOR_PANEL)
    file_row.pack(fill="x", padx=16, pady=(0, 16))

    make_button(file_row, "Browse CSV...", select_file, width=14).pack(side="left")
    label_file = tk.Label(
        file_row, text="No file selected", font=(FONT_FAMILY, 9),
        bg=COLOR_PANEL, fg=COLOR_SUBTEXT
    )
    label_file.pack(side="left", padx=12)

    mode_card = card(root)
    mode_card.pack(fill="x", padx=24, pady=10)

    tk.Label(
        mode_card, text="2. DUPLICATE HANDLING MODE", font=(FONT_FAMILY, 9, "bold"),
        bg=COLOR_PANEL, fg=COLOR_ACCENT
    ).pack(anchor="w", padx=16, pady=(14, 6))

    mode_var = tk.StringVar()
    for value, label in [
        ("activity", "Activity only"),
        ("zone", "Zone only"),
        ("both", "Activity OR Zone"),
    ]:
        tk.Radiobutton(
            mode_card, text=label, value=value, variable=mode_var,
            font=(FONT_FAMILY, 10), bg=COLOR_PANEL, fg=COLOR_TEXT,
            selectcolor=COLOR_BG, activebackground=COLOR_PANEL,
            activeforeground=COLOR_TEXT, anchor="w", cursor="hand2"
        ).pack(anchor="w", padx=20, pady=2)

    tk.Frame(mode_card, bg=COLOR_PANEL, height=10).pack()

    action_card = card(root)
    action_card.pack(fill="x", padx=24, pady=10)

    tk.Label(
        action_card, text="3. RUN", font=(FONT_FAMILY, 9, "bold"),
        bg=COLOR_PANEL, fg=COLOR_ACCENT
    ).pack(anchor="w", padx=16, pady=(14, 8))

    make_button(
        action_card, "▶  Process File", process_file,
        bg=COLOR_ACCENT, hover=COLOR_ACCENT_DARK, width=30
    ).pack(padx=16, pady=(0, 16))

    status_var = tk.StringVar(value="Ready.")
    status_bar = tk.Label(
        root, textvariable=status_var, font=(FONT_FAMILY, 9),
        bg=COLOR_BG, fg=COLOR_SUBTEXT, anchor="w"
    )
    status_bar.pack(fill="x", padx=26, pady=(6, 0))

    footer = tk.Frame(root, bg=COLOR_BG)
    footer.pack(fill="x", side="bottom", padx=24, pady=18)

    make_button(
        footer, "Check for Updates", check_update_silent,
        bg="#2a3f56", hover="#33495f", fg=COLOR_TEXT, width=16
    ).pack(side="left")

    tk.Label(
        footer, text=f"v{APP_VERSION}", font=(FONT_FAMILY, 9),
        bg=COLOR_BG, fg=COLOR_SUBTEXT
    ).pack(side="right")

    root.mainloop()


# ---------------------- LOGIN GUI ----------------------
def build_login():
    global login_window, password_entry

    login_window = tk.Tk()
    login_window.title("DT Activity Filterer")
    login_window.geometry("340x260")
    login_window.configure(bg=COLOR_BG)
    login_window.resizable(False, False)

    tk.Label(
        login_window, text="🚛", font=(FONT_FAMILY, 32),
        bg=COLOR_BG, fg=COLOR_ACCENT
    ).pack(pady=(30, 0))

    tk.Label(
        login_window, text="DT Activity Filterer",
        font=(FONT_FAMILY, 14, "bold"), bg=COLOR_BG, fg=COLOR_TEXT
    ).pack(pady=(4, 20))

    entry_card = card(login_window)
    entry_card.pack(padx=30, fill="x")

    tk.Label(
        entry_card, text="PASSWORD", font=(FONT_FAMILY, 8, "bold"),
        bg=COLOR_PANEL, fg=COLOR_ACCENT
    ).pack(anchor="w", padx=16, pady=(14, 4))

    password_entry = tk.Entry(
        entry_card, show="*", font=(FONT_FAMILY, 11),
        bg=COLOR_BG, fg=COLOR_TEXT, insertbackground=COLOR_TEXT,
        relief="flat"
    )
    password_entry.pack(fill="x", padx=16, pady=(0, 16), ipady=6)
    password_entry.bind("<Return>", lambda e: login())
    password_entry.focus_set()

    make_button(login_window, "Login", login, width=20).pack(pady=20)


if __name__ == "__main__":
    build_login()
    login_window.mainloop()
