````markdown
# USBZero 🔒

**USBZero** is a cross-platform, GUI-based USB wiping tool written in Python. It offers secure, multi-pass data erasure and (on Linux) optional HPA/DCO removal.

## 🔥 Features

- 💻 CustomTkinter GUI (Dark Mode, Animated Elements)
- 🔁 Multiple wiping algorithms:
  - Random (Recommended)
  - Zero-fill (0x00)
  - FF-fill (0xFF)
  - DoD 5220.22-M
  - Gutmann (35-pass)
- 🧼 Log generation with SHA-256 signature
- 📦 PyInstaller-compatible (EXE build support)
- 🧠 Linux version supports **HPA/DCO removal**

## 🖥️ Platform Support

| Platform | GUI | HPA/DCO Removal | Notes |
|----------|-----|------------------|-------|
| Windows  | ✅   | ❌               | Recommended for general users |
| Linux    | ✅   | ✅               | Requires `sudo` and `hdparm` |

## 🚀 Usage

### Windows:
```bash
python usbzero_en.py
````

### Linux:

```bash
sudo python3 usbzero_linux.py
```

> For full functionality on Linux, make sure `hdparm` is installed.

## 🔐 Wipe Logs

All operations are saved in `/logs/` as JSON + `.sig` signature.

## 🧩 Dependencies

Install requirements:

```bash
pip install -r requirements.txt
```

`requirements.txt` content:

```
psutil
customtkinter
Pillow
```

## 🧑‍💻 Author

* GitHub: [ardaispartalioglu](https://github.com/ardaispartalioglu)

## 📄 License

MIT License

````

---

### 📦 requirements.txt

```txt
psutil
customtkinter
Pillow
````

---
