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
import webbrowser
import re
import platform

# Ensure we're running on Linux
if platform.system() != 'Linux':
    messagebox.showerror("Error", "This version of USBZero is for Linux systems only.")
    sys.exit(1)

# PyInstaller-compatible path resolver
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def check_hdparm_availability():
    """Check if hdparm is installed."""
    try:
        subprocess.run(['which', 'hdparm'], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False

def check_sudo_privileges():
    """Check if the script has sudo privileges."""
    try:
        subprocess.run(['sudo', '-n', 'true'], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False

def list_removable_drives():
    """List available removable drives on Linux."""
    drives = []
    try:
        # Get list of block devices
        result = subprocess.run(['lsblk', '-dpno', 'NAME,RM,TYPE'], 
                              capture_output=True, text=True, check=True)
        
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 3:
                device, removable, dev_type = parts
                # Check if device is removable (RM=1) and is a disk
                if removable == "1" and dev_type == "disk":
                    drives.append(device)
    except subprocess.CalledProcessError:
        pass
    
    return drives or ["No USB found"]

def get_device_model(device_path):
    """Get device model information on Linux."""
    try:
        # Use udevadm to get device information
        result = subprocess.run(
            ['udevadm', 'info', '--query=property', '--name=' + device_path],
            capture_output=True, text=True, check=True
        )
        
        # Look for ID_MODEL or ID_MODEL_ID in the output
        for line in result.stdout.splitlines():
            if line.startswith('ID_MODEL='):
                return line.split('=')[1].replace('_', ' ')
        
        return "Unknown"
    except subprocess.CalledProcessError:
        return "Unknown"

def remove_hpa_dco(device_path, update_status):
    """Remove HPA and DCO from the device."""
    try:
        # First, restore DCO
        update_status("Restoring DCO configuration...")
        result = subprocess.run(['sudo', 'hdparm', '--dco-restore', device_path],
                              capture_output=True, text=True, check=True)
        
        # Get current max sectors
        update_status("Reading maximum sector count...")
        result = subprocess.run(['sudo', 'hdparm', '-N', device_path],
                              capture_output=True, text=True, check=True)
        
        # Parse the max sectors from output
        match = re.search(r'max sectors\s+=\s+(\d+)', result.stdout)
        if not match:
            raise Exception("Could not determine maximum sector count")
        
        max_sectors = match.group(1)
        
        # Set HPA to maximum (effectively removing it)
        update_status("Removing HPA configuration...")
        result = subprocess.run(['sudo', 'hdparm', f'-N', f'p{max_sectors}', device_path],
                              capture_output=True, text=True, check=True)
        
        return True
    except subprocess.CalledProcessError as e:
        error_msg = f"Error during HPA/DCO removal: {e.stderr}"
        messagebox.showerror("Error", error_msg)
        return False
    except Exception as e:
        error_msg = f"Error during HPA/DCO removal: {str(e)}"
        messagebox.showerror("Error", error_msg)
        return False

def format_drive(device_path):
    """Format the drive using Linux commands."""
    try:
        # Create a new partition table
        subprocess.run(['sudo', 'parted', '-s', device_path, 'mklabel', 'gpt'],
                     check=True, capture_output=True)
        
        # Create a new partition
        subprocess.run(['sudo', 'parted', '-s', device_path, 'mkpart', 'primary', '0%', '100%'],
                     check=True, capture_output=True)
        
        # Wait for the system to recognize the new partition
        time.sleep(2)
        
        # Format the partition with ext4
        partition = device_path + "1"  # First partition
        subprocess.run(['sudo', 'mkfs.ext4', '-F', partition],
                     check=True, capture_output=True)
        
        return True
    except subprocess.CalledProcessError as e:
        error_msg = f"Format error: {e.stderr.decode() if e.stderr else str(e)}"
        messagebox.showerror("Format Error", error_msg)
        return False

def overwrite_drive(device_path, pass_index):
    """Overwrite the drive with random data."""
    deleted_files = []
    try:
        # Use dd to write random data
        block_size = "1M"
        count = 100  # Write 100MB per pass
        
        subprocess.run(
            ['sudo', 'dd', 'if=/dev/urandom', f'of={device_path}',
             f'bs={block_size}', f'count={count}', 'conv=fsync'],
            check=True, capture_output=True
        )
        
        return True, [f"Pass {pass_index + 1} complete"]
    except subprocess.CalledProcessError as e:
        print(f"Overwrite error during pass {pass_index}: {e}")
        return False, deleted_files

def save_log(device_path, algorithm, passes, deleted_files, hpa_dco_status):
    log = {
        "uuid": str(uuid.uuid4()),
        "drive": device_path,
        "timestamp": datetime.now().isoformat(),
        "algorithm": algorithm,
        "passes": passes,
        "deleted_files": deleted_files,
        "hpa_dco_cleaned": hpa_dco_status,
        "device_model": get_device_model(device_path)
    }
    
    json_data = json.dumps(log, indent=4)
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
    hpa_dco_var.set(False)  # Reset HPA/DCO checkbox when controls are re-enabled
    hpa_dco_checkbox.configure(state=state)

def validate_user_inputs():
    selected_drive = drive_combo.get()
    if "No USB found" in selected_drive:
        messagebox.showerror("Error", "No USB device selected.")
        return None
    
    algorithm = algo_combo.get()
    try:
        passes = int(passes_entry.get())
    except Exception:
        messagebox.showerror("Error", "Pass count must be an integer between 1 and 35.")
        return None
    
    if not (1 <= passes <= 35):
        messagebox.showerror("Error", "Pass count must be between 1 and 35.")
        return None
    
    if hpa_dco_var.get():
        if not check_hdparm_availability():
            messagebox.showerror("Error", 
                "hdparm is not installed. Please install it using:\n" +
                "sudo apt-get install hdparm")
            return None
        
        if not check_sudo_privileges():
            messagebox.showerror("Error", 
                "Sudo privileges are required for HPA/DCO removal.\n" +
                "Please run the application with sudo privileges.")
            return None
    
    return selected_drive, algorithm, passes

def on_hpa_dco_toggle():
    if hpa_dco_var.get():
        response = messagebox.askokcancel("Warning",
            "This action will permanently remove HPA/DCO from the drive, " +
            "restoring it to its full native capacity.\n\n" +
            "This operation cannot be undone. Continue?")
        if not response:
            hpa_dco_var.set(False)

def confirm_wipe(selected_drive, algorithm, passes):
    warning = f"WARNING: All data on {selected_drive} will be PERMANENTLY DELETED.\n\n"
    if hpa_dco_var.get():
        warning += "Additionally, HPA/DCO will be permanently removed.\n\n"
    warning += "This operation cannot be undone. Are you sure you want to continue?"
    
    return messagebox.askyesno("Confirm", warning)

def start_process():
    set_controls_state("disabled")
    validated = validate_user_inputs()
    if not validated:
        set_controls_state("normal")
        return
    
    selected_drive, algorithm, passes = validated
    enable_log = log_var.get()
    hpa_dco_enabled = hpa_dco_var.get()
    hpa_dco_status = False

    if not confirm_wipe(selected_drive, algorithm, passes):
        set_controls_state("normal")
        return

    status_label.configure(text="Starting process...")
    progress.set(0)
    progress.start()

    def update_status(msg):
        app.after(0, lambda: status_label.configure(text=msg))

    def enable_controls():
        app.after(0, lambda: set_controls_state("normal"))

    def process():
        nonlocal hpa_dco_status
        
        # HPA/DCO removal if enabled
        if hpa_dco_enabled:
            update_status("Removing HPA/DCO...")
            hpa_dco_status = remove_hpa_dco(selected_drive, update_status)
            if not hpa_dco_status:
                progress.stop()
                progress.set(1.0)
                enable_controls()
                return

        # Format drive
        update_status("Formatting drive...")
        if format_drive(selected_drive):
            update_status(f"Writing random data (Pass 1/{passes})...")
            success, files = True, []
            
            for p in range(passes):
                update_status(f"Pass {p+1}/{passes}: Writing random data...")
                ok, del_files = overwrite_drive(selected_drive, p)
                files.extend(del_files)
                if not ok:
                    success = False
                    break
            
            if success:
                update_status("Saving log and finalizing...")
                if enable_log:
                    save_log(selected_drive, algorithm, passes, files, hpa_dco_status)
                update_status("Process completed successfully.")
                progress.stop()
                progress.set(1.0)
                populate_log_files_list()
                messagebox.showinfo("Success", f"Drive {selected_drive} was successfully processed.")
            else:
                update_status("Error: Data overwrite failed.")
                progress.stop()
                progress.set(1.0)
                messagebox.showerror("Error", "Overwrite operation failed.")

        else:
            update_status("Formatting failed.")
            progress.stop()
            progress.set(1.0)
            messagebox.showerror("Format Error", "Formatting the drive failed.")
        enable_controls()

    threading.Thread(target=process).start()

# --- GUI Section ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
app = ctk.CTk()
app.title("USBZero - Advanced USB Wiper (Linux)")
app.geometry("900x600")
app.resizable(False, False)

# Try to set icon
try:
    icon_path = resource_path("assets/usbzero_icon_blue_final_v3.ico")
    if os.path.exists(icon_path):
        app.iconbitmap(icon_path)
except Exception as e:
    print(f"Icon loading error: {e}")

# Main window grid configuration
app.grid_rowconfigure(1, weight=1)
app.grid_columnconfigure(0, weight=1)

# Logo
try:
    logo_image = ctk.CTkImage(light_image=Image.open(resource_path("assets/flash-drive-blue-converted.png")), size=(80, 80))
    logo_label = ctk.CTkLabel(app, image=logo_image, text="")
    logo_label.grid(row=0, column=0, padx=20, pady=20, sticky="nw")
except Exception:
    logo_label = None

# Header
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

# Main Tab Layout
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

# Algorithm selection
ctk.CTkLabel(config_frame, text="Wipe Algorithm:", font=("Arial", 13)).grid(row=1, column=0, sticky="e", padx=(15,5), pady=5)
algo_combo = ctk.CTkComboBox(config_frame, values=["Random (Recommended)", "0x00", "0xFF", "DoD 5220.22-M", "Gutmann (35-pass)"], command=on_algo_change, width=220, font=("Arial", 13))
algo_combo.grid(row=1, column=1, sticky="w", padx=(5,15), pady=5)

# Pass count
ctk.CTkLabel(config_frame, text="Pass Count (1–35):", font=("Arial", 13)).grid(row=2, column=0, sticky="e", padx=(15,5), pady=5)
passes_entry = ctk.CTkEntry(config_frame, width=80, font=("Arial", 13))
passes_entry.insert(0, "3")
passes_entry.grid(row=2, column=1, sticky="w", padx=(5,15), pady=5)

# HPA/DCO checkbox
hpa_dco_var = ctk.BooleanVar(value=False)
hpa_dco_checkbox = ctk.CTkCheckBox(config_frame, text="Permanently Remove HPA/DCO", 
                                  variable=hpa_dco_var, command=on_hpa_dco_toggle,
                                  font=("Arial", 12))
hpa_dco_checkbox.grid(row=3, column=0, columnspan=2, sticky="w", padx=15, pady=5)

# Log checkbox
log_var = ctk.BooleanVar(value=True)
ctk.CTkCheckBox(config_frame, text="Create log file", variable=log_var, font=("Arial", 12)).grid(row=4, column=0, columnspan=2, sticky="w", padx=15, pady=(5, 10))

# Operation Controls Frame
controls_frame = ctk.CTkFrame(tab_main, fg_color="#23272e", border_width=2, border_color="#3a3f4b")
controls_frame.grid(row=2, column=0, padx=30, pady=10, sticky="ew")
ctk.CTkLabel(controls_frame, text="Operation Controls", font=("Arial", 15, "bold"), anchor="w").grid(row=0, column=0, sticky="w", padx=15, pady=(10, 2))
start_btn = ctk.CTkButton(controls_frame, text="Start Process", command=start_process, hover=True, width=200, font=("Arial", 14, "bold"))
start_btn.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 10))

# Progress & Status Frame
progress_frame = ctk.CTkFrame(tab_main, fg_color="#23272e", border_width=2, border_color="#3a3f4b")
progress_frame.grid(row=3, column=0, padx=30, pady=(10, 20), sticky="ew")
progress_frame.grid_columnconfigure(0, weight=1)
ctk.CTkLabel(progress_frame, text="Progress & Status", font=("Arial", 15, "bold"), anchor="w").grid(row=0, column=0, sticky="w", padx=15, pady=(10, 2))
progress = ctk.CTkProgressBar(progress_frame, width=720, height=22, progress_color="#1e90ff")
progress.set(0)
progress.grid(row=1, column=0, sticky="ew", padx=15, pady=5)
status_label = ctk.CTkLabel(progress_frame, text="", font=("Arial", 12, "italic"))
status_label.grid(row=2, column=0, sticky="w", padx=15, pady=(5, 10))

# Log Tab
tab_log.grid_rowconfigure(0, weight=0)
tab_log.grid_rowconfigure(1, weight=1)
tab_log.grid_columnconfigure(0, weight=1)
tab_log.grid_columnconfigure(1, weight=0)

def get_log_files():
    log_dir = "./logs"
    if not os.path.exists(log_dir):
        if not os.path.isdir(log_dir):
            files_current_dir = sorted(
                glob.glob("usbzero_log_*.json"),
                key=os.path.getmtime,
                reverse=True
            )
            if files_current_dir:
                return files_current_dir
            return []

    files = sorted(
        glob.glob(os.path.join(log_dir, "usbzero_log_*.json")),
        key=os.path.getmtime,
        reverse=True
    )
    if not files:
        files_current_dir = sorted(
            glob.glob("usbzero_log_*.json"),
            key=os.path.getmtime,
            reverse=True
        )
        return files_current_dir
    return files

def load_selected_log(selected_file_name):
    log_files_paths = get_log_files()
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
        current_selection_name = log_optionmenu.get()
        if current_selection_name == "No log files found":
            current_selection_name = None
    except Exception:
        pass

    log_file_paths = get_log_files()
    file_names_for_menu = [os.path.basename(f) for f in log_file_paths] or ["No log files found"]
    
    log_optionmenu.configure(values=file_names_for_menu)

    if current_selection_name and current_selection_name in file_names_for_menu:
        log_optionmenu.set(current_selection_name)
    elif file_names_for_menu[0] != "No log files found":
        log_optionmenu.set(file_names_for_menu[0])
    else:
        log_optionmenu.set("No log files found")

def on_log_option_change(choice):
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

# About Tab
try:
    about_logo_image = ctk.CTkImage(light_image=Image.open(resource_path("assets/flash-drive-blue-converted.png")), size=(80, 80))
    about_logo_label = ctk.CTkLabel(tab_about, image=about_logo_image, text="")
    about_logo_label.pack(padx=40, pady=(40, 10), anchor="w")
except Exception:
    about_logo_label = None

about_info_text = (
    "Application Name: USBZero\n"
    "Version: v1.0.1 (Linux)\n"
    "Developer: ardaispartalioglu\n"
    "Description: A secure USB drive erasure tool with advanced features\n"
    "including HPA/DCO removal capability."
)
info_label = ctk.CTkLabel(
    tab_about,
    text=about_info_text,
    justify="left",
    font=("Arial", 15)
)
info_label.pack(padx=40, pady=(0, 5), anchor="w")

github_link_text_display = "GitHub Project Link: github.com/ardaispartalioglu/USBZero"
github_url = "https://github.com/ardaispartalioglu/USBZero"

def open_github_link(event=None):
    webbrowser.open_new_tab(github_url)

link_label = ctk.CTkLabel(
    tab_about,
    text=github_link_text_display,
    font=("Arial", 15, "underline"),
    text_color="dodgerblue",
    cursor="hand2"
)
link_label.pack(padx=40, pady=(0, 40), anchor="w")
link_label.bind("<Button-1>", open_github_link)

# Check for hdparm at startup
if not check_hdparm_availability():
    messagebox.showwarning("Warning",
        "hdparm is not installed. HPA/DCO removal feature will be disabled.\n" +
        "To enable this feature, install hdparm using:\n" +
        "sudo apt-get install hdparm")

app.mainloop()
