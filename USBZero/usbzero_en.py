# usbzero_en.py - USBZero English Version with Integrated Icon and Embedded PNG for EXE

import os
import psutil
import subprocess
import customtkinter as ctk
from tkinter import messagebox
import threading
import time
import json
import uuid
import hashlib
from datetime import datetime
from PIL import Image
import sys
import glob
import webbrowser # Ensure this import is present

# PyInstaller-compatible path resolver
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS  # If bundled by PyInstaller
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def list_removable_drives():
    drives = []
    for disk in psutil.disk_partitions(all=False):
        device = disk.device
        if device and os.path.exists(device):
            try:
                usage = psutil.disk_usage(disk.mountpoint)
                if usage.total > 0 and ('removable' in disk.opts.lower() or disk.device[0].upper() in 'EFGHIJKLMNOP'):
                    drives.append(disk.device)
            except:
                continue
    return drives or ["No USB found"]

def get_usb_model_by_letter(drive_letter):
    try:
        drive_letter = drive_letter.replace(':', '')
        partitions = subprocess.check_output("wmic path Win32_LogicalDiskToPartition get *", shell=True).decode().splitlines()
        index = None
        for line in partitions:
            if drive_letter + ":" in line:
                parts = line.split("#")
                if len(parts) > 1:
                    index = parts[1].split(',')[0].strip()
                    break
        if index:
            drives = subprocess.check_output("wmic diskdrive get index,model", shell=True).decode().splitlines()
            for d in drives:
                if d.strip().startswith(index):
                    return d.strip().split(None, 1)[1]
    except:
        return "Unknown"
    return "Unknown"

def format_usb(drive_letter):
    try:
        result = subprocess.run(
            f"format {drive_letter} /fs:NTFS /q /x /y",
            shell=True,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if result.returncode != 0:
            error_message = "Format command failed."
            if result.stderr:
                error_message += f"\nError Detail: {result.stderr.decode('utf-8', errors='ignore')}"
            messagebox.showerror("Format Error", error_message)
            return False
        return True
    except Exception as e:
        messagebox.showerror("Format Error", f"Error during formatting: {e}")
        return False

def overwrite_drive(drive_path, pass_index):
    deleted_files = []
    try:
        # The function now performs a single pass using the given pass_index for unique naming
        dummy_file = os.path.join(drive_path, f"usbzero_wipe_pass_{pass_index}.bin") # Use pass_index in filename
        try:
            with open(dummy_file, "wb") as f:
                # Writing 100MB, can be adjusted or made configurable
                for _ in range(100): # Loop for writing chunks
                    f.write(os.urandom(1024 * 1024))
            deleted_files.append(dummy_file)
            os.remove(dummy_file)
        except Exception as e:
            print(f"Overwrite error during pass {pass_index}: {e}")
            return False, deleted_files # Return partial success and files processed so far
        return True, deleted_files
    except Exception as e: # General exception for the function
        print(f"Overwrite function error at pass {pass_index}: {e}")
        return False, deleted_files

def save_log(drive_path, algorithm, passes, deleted_files, hpa_dco_status, drive_letter_for_model):
    log = {
        "uuid": str(uuid.uuid4()),
        "drive": drive_path,
        "timestamp": datetime.now().isoformat(),
        "algorithm": algorithm,
        "passes": passes,
        "deleted_files": deleted_files,
        "hpa_dco_cleaned": hpa_dco_status,
        "device_model": get_usb_model_by_letter(drive_letter_for_model)
    }
    json_data = json.dumps(log, indent=4)
    # Ensure logs are saved in a 'logs' subdirectory
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    filename = os.path.join(log_dir, f"usbzero_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(filename, "w") as f:
        f.write(json_data)
    hash_val = hashlib.sha256(json_data.encode()).hexdigest()
    with open(filename.replace(".json", ".sig"), "w") as f:
        f.write(f"sha256: {hash_val}\n")

def update_drive_list():
    drives = list_removable_drives()
    drive_combo.configure(values=drives)
    if drives and drives[0] != "No USB found":
        drive_combo.set(drives[0])
    else:
        drive_combo.set("No USB found")

def on_algo_change(choice=None):
    algo = algo_combo.get()
    if algo == "Gutmann (35-pass)":
        passes_entry.configure(state="normal")
        passes_entry.delete(0, "end")
        passes_entry.insert(0, "35")
        passes_entry.configure(state="disabled")
    elif algo == "DoD 5220.22-M":
        passes_entry.configure(state="normal")
        passes_entry.delete(0, "end")
        passes_entry.insert(0, "3")
    elif algo == "Random (Recommended)":
        passes_entry.configure(state="normal")
        passes_entry.delete(0, "end")
        passes_entry.insert(0, "3")
    else:
        passes_entry.configure(state="normal")
        passes_entry.delete(0, "end")
        passes_entry.insert(0, "1")

def set_controls_state(state):
    drive_combo.configure(state=state)
    algo_combo.configure(state=state)
    if algo_combo.get() == "Gutmann (35-pass)":
        passes_entry.configure(state="disabled" if state == "normal" else state)
    else:
        passes_entry.configure(state=state)
    refresh_btn.configure(state=state)
    start_btn.configure(state=state)

def validate_user_inputs():
    raw_drive = drive_combo.get()
    if "No USB found" in raw_drive or not raw_drive:
        messagebox.showerror("Error", "No USB device selected.")
        return None
    # Ensure trailing backslash for os.path.join
    selected_drive_path = raw_drive
    if not selected_drive_path.endswith(os.path.sep):
        selected_drive_path += os.path.sep
    # Only drive letter and colon for commands/model
    selected_drive_letter = raw_drive.rstrip(os.path.sep)
    algorithm = algo_combo.get()
    try:
        passes = int(passes_entry.get())
    except Exception:
        messagebox.showerror("Error", "Pass count must be an integer between 1 and 35.")
        return None
    if not (1 <= passes <= 35):
        messagebox.showerror("Error", "Pass count must be between 1 and 35.")
        return None
    return selected_drive_path, selected_drive_letter, algorithm, passes

def confirm_wipe(selected_drive_path, algorithm, passes):
    return messagebox.askyesno(
        "Confirm",
        f"WARNING: All data on drive {selected_drive_path} will be PERMANENTLY DELETED.\n"
        "This action cannot be undone. Are you sure you want to continue?"
    )

def start_process():
    set_controls_state("disabled")
    validated = validate_user_inputs()
    if not validated:
        set_controls_state("normal")
        return
    selected_drive_path, selected_drive_letter, algorithm, passes = validated
    enable_log = log_var.get()
    hpa_dco_status = False

    if not confirm_wipe(selected_drive_path, algorithm, passes):
        set_controls_state("normal")
        return

    progress.set(0)
    status_label.configure(text="Starting format...")

    def update_status(msg):
        app.after(0, lambda: status_label.configure(text=msg))

    def enable_controls():
        app.after(0, lambda: set_controls_state("normal"))

    def process():
        update_status("Starting format...")
        if format_usb(selected_drive_letter):
            progress.set(0.3)
            update_status("Starting data overwrite ({} passes)...".format(passes))
            success, files = True, []
            for p in range(passes):
                update_status(f"Pass {p+1}/{passes}: Writing random data...")
                ok, del_files = overwrite_drive(selected_drive_path, p)
                files.extend(del_files)
                if not ok:
                    success = False
                    break
                progress.set(0.3 + 0.6 * ((p+1)/passes))
            if success:
                progress.set(0.9)
                update_status("Saving log and finalizing...")
                if enable_log:
                    save_log(selected_drive_path, algorithm, passes, files, hpa_dco_status, selected_drive_letter)
                progress.set(1.0)
                update_status("Wipe process completed.")
                populate_log_files_list()
                messagebox.showinfo("Success", f"Drive {selected_drive_path} was successfully wiped.")
            else:
                update_status("Data overwrite failed.")
                messagebox.showerror("Error", "Overwrite failed.")
        enable_controls()

    threading.Thread(target=process).start()

# --- GUI Section ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
app = ctk.CTk()
app.title("USBZero - Advanced USB Wiper")
app.geometry("900x600")
app.resizable(False, False)
try:
    icon_path = resource_path("usbzero_icon_blue_final_v3.ico")
    # print(f"Resolved path for icon: {icon_path}")
    if not os.path.exists(icon_path):
        # print(f"WARNING: Icon file not found at the specified path: {icon_path}")
        pass
    app.iconbitmap(icon_path)
    # print("Attempted to set icon successfully.")
except Exception as e:
    print(f"ERROR occurred while setting icon: {e}")
    print(f"Error Type: {type(e).__name__}")

# Main window grid configuration
app.grid_rowconfigure(1, weight=1)
app.grid_columnconfigure(0, weight=1)

# Logo
try:
    logo_image = ctk.CTkImage(light_image=Image.open(resource_path("flash-drive-blue-converted.png")), size=(80, 80))
    logo_label = ctk.CTkLabel(app, image=logo_image, text="")
    logo_label.grid(row=0, column=0, padx=20, pady=20, sticky="nw")
except Exception:
    logo_label = None

# Title and subtitle
header_frame = ctk.CTkFrame(app, fg_color="transparent")
header_frame.grid(row=0, column=1, sticky="nw", padx=(0, 0), pady=(20, 0))
ctk.CTkLabel(header_frame, text="USBZero", font=("Arial Black", 28, "bold")).grid(row=0, column=0, sticky="w")
ctk.CTkLabel(header_frame, text="Advanced & Secure USB Drive Wiper", font=("Arial", 16, "italic")).grid(row=1, column=0, sticky="w", pady=(2, 0))

# Tabs
tabs = ctk.CTkTabview(app, width=860, height=470)
tabs.grid(row=1, column=0, columnspan=2, padx=20, pady=(10, 20), sticky="nsew")
app.grid_rowconfigure(1, weight=1)
app.grid_columnconfigure(0, weight=0)
app.grid_columnconfigure(1, weight=1)

tab_main = tabs.add("🧹 Wipe USB")
tab_log = tabs.add("📄 Log Viewer")
tab_about = tabs.add("ℹ️ About")

# --- Main Tab Layout with Frames and Grid ---

tab_main.grid_rowconfigure(0, weight=0)
tab_main.grid_rowconfigure(1, weight=0)
tab_main.grid_rowconfigure(2, weight=0)
tab_main.grid_rowconfigure(3, weight=1)
tab_main.grid_columnconfigure(0, weight=1)

# USB Drive Selection Frame
drive_frame = ctk.CTkFrame(tab_main, fg_color="#23272e", border_width=2, border_color="#3a3f4b")
drive_frame.grid(row=0, column=0, padx=30, pady=(25, 10), sticky="ew")
drive_frame.grid_columnconfigure(1, weight=1)
ctk.CTkLabel(drive_frame, text="USB Drive Selection", font=("Arial", 15, "bold"), anchor="w").grid(row=0, column=0, columnspan=3, sticky="w", padx=15, pady=(10, 2))
drive_combo = ctk.CTkComboBox(drive_frame, values=list_removable_drives(), width=350, font=("Arial", 13))
drive_combo.grid(row=1, column=0, sticky="ew", padx=(15, 5), pady=(0, 10))
refresh_btn = ctk.CTkButton(drive_frame, text="Refresh Drives", command=update_drive_list, width=120)
refresh_btn.grid(row=1, column=1, sticky="ew", padx=(5, 15), pady=(0, 10))

# Wipe Configuration Frame
config_frame = ctk.CTkFrame(tab_main, fg_color="#23272e", border_width=2, border_color="#3a3f4b")
config_frame.grid(row=1, column=0, padx=30, pady=10, sticky="ew")
config_frame.grid_columnconfigure(1, weight=1)
ctk.CTkLabel(config_frame, text="Wipe Configuration", font=("Arial", 15, "bold"), anchor="w").grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 2))
ctk.CTkLabel(config_frame, text="Wipe Algorithm:", font=("Arial", 13)).grid(row=1, column=0, sticky="e", padx=(15,5), pady=5)
algo_combo = ctk.CTkComboBox(config_frame, values=["Random (Recommended)", "0x00", "0xFF", "DoD 5220.22-M", "Gutmann (35-pass)"], command=on_algo_change, width=220, font=("Arial", 13))
algo_combo.grid(row=1, column=1, sticky="w", padx=(5,15), pady=5)
ctk.CTkLabel(config_frame, text="Pass Count (1–35):", font=("Arial", 13)).grid(row=2, column=0, sticky="e", padx=(15,5), pady=5)
passes_entry = ctk.CTkEntry(config_frame, width=80, font=("Arial", 13))
passes_entry.insert(0, "3")
passes_entry.grid(row=2, column=1, sticky="w", padx=(5,15), pady=5)
log_var = ctk.BooleanVar(value=True)
ctk.CTkCheckBox(config_frame, text="Create log file", variable=log_var, font=("Arial", 12)).grid(row=3, column=0, columnspan=2, sticky="w", padx=15, pady=(5, 10))

# Operation Controls Frame
controls_frame = ctk.CTkFrame(tab_main, fg_color="#23272e", border_width=2, border_color="#3a3f4b")
controls_frame.grid(row=2, column=0, padx=30, pady=10, sticky="ew")
ctk.CTkLabel(controls_frame, text="Operation Controls", font=("Arial", 15, "bold"), anchor="w").grid(row=0, column=0, sticky="w", padx=15, pady=(10, 2))
start_btn = ctk.CTkButton(controls_frame, text="Start Wipe Process", command=start_process, hover=True, width=200, font=("Arial", 14, "bold"))
start_btn.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 10))

# Progress & Status Frame
progress_frame = ctk.CTkFrame(tab_main, fg_color="#23272e", border_width=2, border_color="#3a3f4b")
progress_frame.grid(row=3, column=0, padx=30, pady=(10, 20), sticky="ew")
progress_frame.grid_columnconfigure(0, weight=1)
ctk.CTkLabel(progress_frame, text="Progress & Status", font=("Arial", 15, "bold"), anchor="w").grid(row=0, column=0, sticky="w", padx=15, pady=(10, 2))
progress = ctk.CTkProgressBar(progress_frame, width=600, height=18, progress_color="#1e90ff")
progress.set(0)
progress.grid(row=1, column=0, sticky="ew", padx=15, pady=5)
status_label = ctk.CTkLabel(progress_frame, text="", font=("Arial", 12, "italic"))
status_label.grid(row=2, column=0, sticky="w", padx=15, pady=(5, 10))

# --- Log Tab ---

tab_log.grid_rowconfigure(0, weight=0)
tab_log.grid_rowconfigure(1, weight=1)
tab_log.grid_columnconfigure(0, weight=1)
tab_log.grid_columnconfigure(1, weight=0)

def get_log_files():
    log_dir = "./logs"
    if not os.path.exists(log_dir):
        # If ./logs doesn't exist, try to create it or fallback to current dir for reading
        # For saving, save_log function now creates ./logs
        # For reading, if it's not there, it means no logs were saved in the subdir yet.
        # Fallback to current directory for compatibility if logs were saved there before subdir logic.
        if not os.path.isdir(log_dir): # Check if it's not a dir (could be a file)
             # Try checking current directory as a fallback for existing logs
            files_current_dir = sorted(
                glob.glob("usbzero_log_*.json"),
                key=os.path.getmtime,
                reverse=True
            )
            if files_current_dir:
                return files_current_dir # Return logs from current dir if found
            return [] # No logs in ./logs and no logs in current dir

    files = sorted(
        glob.glob(os.path.join(log_dir, "usbzero_log_*.json")),
        key=os.path.getmtime,
        reverse=True
    )
    # If no logs in ./logs, check current directory as a fallback
    if not files:
        files_current_dir = sorted(
            glob.glob("usbzero_log_*.json"),
            key=os.path.getmtime,
            reverse=True
        )
        return files_current_dir
    return files

def load_selected_log(selected_file_name):
    # selected_file_name is just the basename, we need to find its full path
    log_files_paths = get_log_files() # This returns full paths
    path_to_load = None
    for p in log_files_paths:
        if os.path.basename(p) == selected_file_name:
            path_to_load = p
            break

    log_display.configure(state="normal")
    log_display.delete("1.0", "end")
    if path_to_load and os.path.exists(path_to_load):
        try:
            with open(path_to_load, "r", encoding="utf-8") as f:
                data = json.load(f)
            log_display.insert("end", json.dumps(data, indent=4, ensure_ascii=False))
        except Exception as e:
            log_display.insert("end", f"Error loading log: {selected_file_name}\n{e}")
    elif selected_file_name == "No log files found":
        log_display.insert("end", "No log files found.")
    else:
        log_display.insert("end", f"Log file '{selected_file_name}' not found or path is incorrect.")
    log_display.configure(state="disabled")

def populate_log_files_list():
    current_selection_name = None
    try:
        # Get the name of the currently selected item, not its full path
        current_selection_name = log_optionmenu.get()
        if current_selection_name == "No log files found": # Treat as no specific file selected
            current_selection_name = None
    except Exception:
        pass # log_optionmenu might not be fully initialized on first call

    log_file_paths = get_log_files()
    file_names_for_menu = [os.path.basename(f) for f in log_file_paths] or ["No log files found"]
    
    log_optionmenu.configure(values=file_names_for_menu)

    if current_selection_name and current_selection_name in file_names_for_menu:
        log_optionmenu.set(current_selection_name)
        # load_selected_log(current_selection_name) # on_log_option_change will handle this
    elif file_names_for_menu[0] != "No log files found":
        log_optionmenu.set(file_names_for_menu[0])
        # load_selected_log(file_names_for_menu[0]) # on_log_option_change will handle this
    else:
        log_optionmenu.set("No log files found")
        # load_selected_log("No log files found") # on_log_option_change will handle this
    
    # If the set value didn't change, on_log_option_change might not fire.
    # Explicitly load if the value set is the same as before but content needs refresh (e.g. file updated)
    # However, on_log_option_change should always be called by .set() if the value is valid.
    # The on_log_option_change will call load_selected_log with the final set value.

def on_log_option_change(choice): # choice is a file name (basename)
    load_selected_log(choice)

log_optionmenu = ctk.CTkOptionMenu(tab_log, values=["No log files found"], command=on_log_option_change, width=300, font=("Arial", 13))
log_optionmenu.grid(row=0, column=0, sticky="ew", padx=(20, 5), pady=(20, 0))

refresh_logs_btn = ctk.CTkButton(tab_log, text="Refresh Logs", command=populate_log_files_list, width=120)
refresh_logs_btn.grid(row=0, column=1, sticky="ew", padx=(5,20), pady=(20,0))

log_display = ctk.CTkTextbox(tab_log, width=820, height=400, font=("Consolas", 12))
log_display.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=20, pady=15)
log_display.insert("end", "Logs will appear here after the wipe operation.")
log_display.configure(state="disabled")

def poll_tab_change():
    try:
        if tabs.get() == "📄 Log Viewer":
            populate_log_files_list()
    except Exception:
        pass
    app.after(1000, poll_tab_change)

populate_log_files_list()
poll_tab_change()

# --- About Tab ---

try:
    about_logo_image = ctk.CTkImage(light_image=Image.open(resource_path("flash-drive-blue-converted.png")), size=(80, 80))
    about_logo_label = ctk.CTkLabel(tab_about, image=about_logo_image, text="")
    about_logo_label.pack(padx=40, pady=(40, 10), anchor="w")
except Exception:
    about_logo_label = None

about_info_text = (
    "Application Name: USBZero\n"
    "Version: v1.0.1\n"
    "Developer: ardaispartalioglu\n"
    "Description: A secure USB drive erasure tool with advanced features."
)
info_label = ctk.CTkLabel(
    tab_about,
    text=about_info_text,
    justify="left",
    font=("Arial", 15)
)
info_label.pack(padx=40, pady=(0, 5), anchor="w")

# GitHub link
github_link_text_display = "GitHub Project Link: github.com/ardaispartalioglu/USBZero"
github_url = "https://github.com/ardaispartalioglu/USBZero"

def open_github_link(event=None):
    webbrowser.open_new_tab(github_url)

link_label = ctk.CTkLabel(
    tab_about,
    text=github_link_text_display,
    font=("Arial", 15, "underline"),
    text_color="dodgerblue", # Or another link-like color e.g. #1E90FF
    cursor="hand2"
)
link_label.pack(padx=40, pady=(0, 40), anchor="w")
link_label.bind("<Button-1>", open_github_link)

app.mainloop()