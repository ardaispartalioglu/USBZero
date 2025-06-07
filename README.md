# USBZero

USBZero is a cross-platform GUI-based USB wiping tool built with Python. It offers secure multi-pass erasure for USB drives and supports advanced disk wipe methods.

## Features

* Clean and modern GUI (CustomTkinter)
* Multiple overwrite algorithms:

  * Random (Recommended)
  * 0x00
  * 0xFF
  * DoD 5220.22-M
  * Gutmann (35-pass)
* Real-time progress and status updates
* Log file creation (JSON + SHA256 .sig)
* Linux version supports optional HPA/DCO removal

## Supported Platforms

| Platform | GUI | HPA/DCO Support | File              |
| -------- | --- | --------------- | ----------------- |
| Windows  | ✅   | ❌               | usbzero\_en.py    |
| Linux    | ✅   | ✅               | usbzero\_linux.py |

## Installation

```
pip install -r requirements.txt
```

## Run

### Windows

```
python usbzero_en.py
```

### Linux

```
sudo python3 usbzero_linux.py
```

## Build Executable

### Windows

```
build_windows.bat
```

### Linux

```
chmod +x build_linux.sh
./build_linux.sh
```

## Requirements

* Python 3.10+
* psutil
* customtkinter
* Pillow
* hdparm (Linux only)

## Screenshot

![USBZero GUI](assets/usbzero_gui_preview.png)

## License

MIT License

## Author

github.com/ardaispartalioglu
