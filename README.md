
# win-snip2tex

A zero-friction, background LaTeX OCR companion for Windows powered by [`pix2tex`](https://github.com/lukas-blecher/LaTeX-OCR).

Trigger a hotkey or mapped mouse button, snip any equation on your screen using the native Windows Snipping Tool, and have the generated LaTeX code immediately placed onto your clipboard with a native notification preview.

---

## Features

* **Native Snip Experience:** Spawns Windows Snipping Tool (`ms-screenclip:`) directly—no bulky custom overlay needed.
* **Dual Triggering:**
* **Keyboard:** `Alt + Shift + S`
* **Mouse:** `F24` (easily mapped via Logitech G Hub, Logi Options+, Razer Synapse, or mouse configuration software).
* **Fast & Headless:** Keeps the PyTorch/pix2tex model resident in memory to avoid cold-start inference lag.
* **Direct Win32 Clipboard Injection:** Uses UTF-16 Win32 global memory allocation to prevent encoding or truncation quirks.
* **Native Toast Feedback:** Displays the recognized LaTeX equation right after copying.
* **Clean Exit:** Press `Alt + Shift + Q` to cleanly stop the background listener.

---

## Installation

### 1. Prerequisites

* Windows 10/11
* Python 3.9 – 3.11 recommended

### 2. Clone & Setup Virtual Environment

```bash
git clone https://github.com/rubenparnell/latex-snipper.git
cd latex-snipper

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

> *Note: On the first run, `pix2tex` will automatically download the OCR model weights (~100 MB).*

---

## Usage

### Run in Foreground (Testing & Debugging)

Run standard Python to view real-time log messages and verify initial model loading:

```bash
python main.py
```

### Run Silently in the Background

Run using `pythonw` to execute completely detached without keeping a command prompt window open:

```powershell
pythonw main.py
```

---

## Mouse Setup (F24 Mapping)

The script binds to native Windows `F24` virtual keycodes, allowing you to trigger OCR with a single mouse click without interfering with standard keys:

1. Open your mouse configuration software (e.g., **Logi Options+**, **Logitech G HUB**, or **Razer Synapse**).
2. Select the button you wish to use (such as a gesture button, thumb button, or scroll-wheel tilt).
3. Assign that button to keystroke **F24**.
4. Pressing that mouse button will trigger the snipping tool overlay and OCR pipeline.

---

## Run on Windows Startup (Optional)

To start `win-snip2tex` automatically and silently when Windows boots:

1. Press `Win + R`, type `shell:startup`, and press **Enter** to open your Windows Startup folder.
2. In that folder, create a file named `launch_snip2tex.vbs`.
3. Add the following code (adjust paths to match your exact directory structure):

```vbs
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "C:\path\to\latex-snipper\.venv\Scripts\pythonw.exe C:\path\to\latex-snipper\main.py", 0, False
Set WshShell = Nothing
```

---

## Logs & Diagnostics

Traces, hotkey events, and errors are written directly to:

```text
%LOCALAPPDATA%\pix2tex-mouse-helper.log
```

To tail the logs live in PowerShell:

```powershell
Get-Content "$env:LOCALAPPDATA\pix2tex-mouse-helper.log" -Wait
```
