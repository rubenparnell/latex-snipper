from __future__ import annotations

import ctypes
from ctypes import wintypes
import io
import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from PIL import Image, ImageGrab
from windows_toasts import InteractableWindowsToaster, Toast
from pynput import keyboard

LOG_PATH = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "pix2tex-mouse-helper.log"
logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

os.environ.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")

busy = threading.Lock()
model = None
toaster = InteractableWindowsToaster("LaTeX OCR")

# Win32 Constants for F24
MOD_NOREPEAT = 0x4000
VK_F24 = 0x87
HOTKEY_ID_F24 = 1

# State tracking for keyboard hook
current_keys = set()
running = True


def show_notification(title: str, body: str) -> None:
    try:
        toast = Toast()
        toast.text_fields = [title, body]
        toaster.show_toast(toast)
    except Exception:
        logging.exception("Failed to show toast notification")


def put_text_on_clipboard(value: str) -> None:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalAlloc.argtypes = (ctypes.c_uint, ctypes.c_size_t)
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = (ctypes.c_void_p,)
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = (ctypes.c_void_p,)
    kernel32.GlobalUnlock.restype = ctypes.c_int
    user32.SetClipboardData.argtypes = (ctypes.c_uint, ctypes.c_void_p)
    user32.SetClipboardData.restype = ctypes.c_void_p

    payload = (value + "\0").encode("utf-16-le")
    for _ in range(20):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("Windows clipboard is busy")

    handle = None
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(0x0002, len(payload))
        if not handle:
            raise MemoryError("Could not allocate clipboard memory")
        address = kernel32.GlobalLock(handle)
        if not address:
            raise MemoryError("Could not lock clipboard memory")
        ctypes.memmove(address, payload, len(payload))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(13, handle):
            raise OSError("Could not set clipboard text")
        handle = None
    finally:
        user32.CloseClipboard()
        if handle:
            kernel32.GlobalFree.argtypes = (ctypes.c_void_p,)
            kernel32.GlobalFree(handle)


def get_image_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def single_action_ocr() -> None:
    if not busy.acquire(blocking=False):
        return

    try:
        initial_image = ImageGrab.grabclipboard()
        initial_bytes = None
        if initial_image is not None and hasattr(initial_image, "convert"):
            initial_bytes = get_image_bytes(initial_image)

        # Trigger Snipping Tool overlay
        subprocess.Popen(["explorer.exe", "ms-screenclip:"])

        new_image = None
        start_time = time.time()
        while time.time() - start_time < 30:
            time.sleep(0.3)
            current_image = ImageGrab.grabclipboard()
            if current_image is not None and hasattr(current_image, "convert"):
                current_bytes = get_image_bytes(current_image)
                if initial_bytes is None or current_bytes != initial_bytes:
                    new_image = current_image
                    break

        if new_image is None:
            logging.warning("No new screen snip detected within timeout")
            return

        result = str(model(new_image.convert("RGB"))).strip()
        if not result:
            raise RuntimeError("pix2tex returned an empty result")

        put_text_on_clipboard(result)
        logging.info("Recognized formula and copied to clipboard")
        show_notification("LaTeX Copied!", result)

    except Exception:
        logging.exception("OCR pipeline failed")
        show_notification("LaTeX OCR Failed", "Check log for details.")
    finally:
        busy.release()


def on_press(key):
    global running
    current_keys.add(key)

    # Detect Alt + Shift + S (OCR Trigger)
    alt_down = any(k in current_keys for k in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr))
    shift_down = any(k in current_keys for k in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r))
    s_down = hasattr(key, "char") and key.char in ("s", "S")

    if alt_down and shift_down and s_down:
        logging.info("Alt + Shift + S triggered via keyboard")
        threading.Thread(target=single_action_ocr, daemon=True).start()
        return

    # Detect Exit: Alt + Shift + Q
    q_down = hasattr(key, "char") and key.char in ("q", "Q")

    if alt_down and shift_down and q_down:
        logging.info("Exit hotkey pressed (Alt + Shift + Q)")
        running = False
        ctypes.windll.user32.PostQuitMessage(0)
        return False


def on_release(key):
    current_keys.discard(key)


def start_pynput_listener():
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


def main() -> None:
    global model

    try:
        from pix2tex.cli import LatexOCR
        logging.info("Loading pix2tex model")
        model = LatexOCR()
        logging.info("Model ready")
    except Exception:
        logging.exception("Could not load pix2tex")
        return

    # 1. Start pynput keyboard hook in background thread (handles Alt+Shift+S)
    listener_thread = threading.Thread(target=start_pynput_listener, daemon=True)
    listener_thread.start()

    # 2. Register F24 with native Win32 API on main thread (handles Mouse action)
    user32 = ctypes.windll.user32
    if not user32.RegisterHotKey(None, HOTKEY_ID_F24, MOD_NOREPEAT, VK_F24):
        logging.error("Failed to register F24 hotkey via Win32")
    else:
        logging.info("Registered F24 via Win32 successfully")

    logging.info("Merged helper active: F24 (Mouse) and Alt+Shift+S (Keyboard)")

    # Standard Windows message dispatch loop
    msg = wintypes.MSG()
    try:
        while running and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == 0x0312:  # WM_HOTKEY
                if msg.wParam == HOTKEY_ID_F24:
                    logging.info("F24 triggered via mouse")
                    threading.Thread(target=single_action_ocr, daemon=True).start()
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    finally:
        user32.UnregisterHotKey(None, HOTKEY_ID_F24)
        logging.info("Background helper stopped")


if __name__ == "__main__":
    main()