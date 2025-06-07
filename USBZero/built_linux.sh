#!/bin/bash
pyinstaller --onefile --noconsole --icon=assets/usbzero_icon_blue_final_v3.ico --add-data "assets/flash-drive-blue-converted.png:assets" usbzero_linux.py
