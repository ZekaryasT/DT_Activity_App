import os
import sys
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox
from openpyxl.styles import Font
import requests
from datetime import datetime
import webbrowser

# ---------------------- CONFIG ----------------------
APP_VERSION = "1.0.2"  # Update this when releasing a new version
PASSWORD = "ZackT"
VERSION_URL = "https://raw.githubusercontent.com/ZekaryasT/DT_Activity_App/refs/heads/main/version.txt"
UPDATE_PAGE_URL = "https://raw.githubusercontent.com/ZekaryasT/DT_Activity_App/refs/heads/main/dumptruck_app.py"
MAX_TRIES = 3
# ----------------------------------------------------

# Global variables
file_path = ""
login_attempts = 0

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

# ---------------------- UPDATE CHECK ----------------------
def show_update_window(url, new_version):
    def open_update():
        webbrowser.open(url)
        win.destroy()

    win = tk.Toplevel()
    win.title(f"Check Update (v{APP_VERSION})")
    win.geometry("460x180")
    win.resizable(False, False)

    tk.Label(
        win,
        text=f"A new version {new_version} is available.",
        font=("Arial", 12, "bold")
    ).pack(pady=10)

    tk.Label(
        win,
        text="Do you want to update the app?",
        font=("Arial", 10)
    ).pack(pady=5)

    button_frame = tk.Frame(win)
    button_frame.pack(pady=10)

    tk.Button(button_frame, text="Yes", command=open_update, bg="green", fg="white", width=10).pack(side="left", padx=10)
    tk.Button(button_frame, text="No", command=win.destroy, bg="red", fg="white", width=10).pack(side="right", padx=10)

    # Copyable URL
    url_entry = tk.Entry(win, width=60)
    url_entry.insert(0, url)
    url_entry.config(state="readonly")
    url_entry.pack(pady=5)

    def copy_url():
        win.clipboard_clear()
        win.clipboard_append(url)
        win.update()

    tk.Button(win, text="Copy Link", command=copy_url).pack(pady=4)

def check_update():
    try:
        online_version = requests.get(VERSION_URL, timeout=10).text.strip()
        if online_version != APP_VERSION:
            show_update_window(UPDATE_PAGE_URL, online_version)
        else:
            messagebox.showinfo(
                f"Check Update (v{APP_VERSION})",
                f"You are using the latest version ({APP_VERSION})."
            )
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
        label_file.config(text=f"Selected: {os.path.basename(file_path)}")

# ---------------------- FILE PROCESSING ----------------------
def process_file():
    global file_path

    if not file_path:
        messagebox.showerror("Error", "Please select a file first.")
        return

    try:
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
            return

        mask = df_result["dup"] > 0
        df_result.loc[mask, "Activity"] = df_result.loc[mask, "Activity"] + df_result.loc[mask, "dup"].apply(lambda x: "-" * x)
        changed_rows = df_result.index[mask].tolist()
        df_result.drop(columns=["dup"], inplace=True)

        # Save files
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

        # Open folder automatically
        os.startfile(base_dir)

        messagebox.showinfo("Success", f"Processing complete!\nFiles saved successfully.\nTimestamp: {timestamp}")

    except Exception as e:
        messagebox.showerror("Error", str(e))

# ---------------------- MAIN APP GUI ----------------------
def main_app():
    global label_file, mode_var
    global root
    root = tk.Tk()
    root.title("Dump Truck Activity Adjuster")
    root.geometry("450x380")

    # File selection
    tk.Button(root, text="Select CSV File", command=select_file).pack(pady=10)
    label_file = tk.Label(root, text="No file selected")
    label_file.pack()

    # Mode selection
    mode_var = tk.StringVar()
    tk.Label(root, text="Choose duplicate handling mode:").pack(pady=10)
    tk.Radiobutton(root, text="Activity only", variable=mode_var, value="activity").pack()
    tk.Radiobutton(root, text="Zone only", variable=mode_var, value="zone").pack()
    tk.Radiobutton(root, text="Activity OR Zone", variable=mode_var, value="both").pack()

    # Process button
    tk.Button(root, text="Process File", command=process_file, bg="green", fg="white").pack(pady=10)

    # Update button
    tk.Button(root, text=f"Check Update (v{APP_VERSION})", command=check_update).pack(pady=5)

    # Current version label
    tk.Label(root, text=f"Current Version: {APP_VERSION}").pack(side="bottom", pady=5)

    root.mainloop()

# ---------------------- LOGIN GUI ----------------------
login_window = tk.Tk()
login_window.title("Login")
login_window.geometry("300x150")
tk.Label(login_window, text="Enter Password:").pack(pady=10)
password_entry = tk.Entry(login_window, show="*")
password_entry.pack()
tk.Button(login_window, text="Login", command=login).pack(pady=10)
login_window.mainloop()
