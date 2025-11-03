import sys
import time
import logging
import queue
import threading

import keyboard
import pyperclip
import tkinter as tk

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)

CMD_TOGGLE = "TOGGLE"
CMD_PASTE  = "PASTE"
CMD_EXIT   = "EXIT"
CMD_TOAST  = "TOAST"

class TkApp:
    """All Tk + clipboard work stays on the main thread."""
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.toast = None

    def show_toast(self, text, millis=900):
        try:
            if self.toast is not None:
                try:
                    self.toast.destroy()
                except Exception:
                    pass
            t = tk.Toplevel(self.root)
            self.toast = t
            t.overrideredirect(True)
            t.attributes("-topmost", True)
            w, h = 220, 44
            t.update_idletasks()
            sw, sh = t.winfo_screenwidth(), t.winfo_screenheight()
            x = sw - w - 24
            y = sh - h - 48
            t.geometry(f"{w}x{h}+{x}+{y}")

            frame = tk.Frame(t, bg="#111", bd=0, highlightthickness=0)
            frame.pack(fill="both", expand=True)
            lbl = tk.Label(frame, text=text, fg="#fff", bg="#111",
                           font=("Segoe UI", 11, "bold"))
            lbl.pack(expand=True)
            t.after(millis, lambda: t.destroy())
        except Exception as e:
            logging.debug(f"Toast error: {e}")

    def get_clip_text(self) -> str:
        try:
            return self.root.clipboard_get()
        except Exception:
            try:
                return pyperclip.paste()
            except Exception:
                return ""

    def set_clip_text(self, text: str):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
        except Exception:
            try:
                pyperclip.copy(text)
            except Exception:
                pass

class PlainPasteController:
    def __init__(self):
        self.app = TkApp()
        self.enabled = False
        self.cmdq: queue.Queue[tuple] = queue.Queue()
        self._hotkey_id = None
        self._pasting = False  # reentrancy guard
        self._install_hotkeys()
        self._enqueue(CMD_TOAST, "Plain Paste: OFF (F8)")
        logging.info("Plain Paste: OFF (press F8 to toggle)")

    # ---------- Hotkeys run on worker threads ----------
    def _install_hotkeys(self):
        keyboard.add_hotkey("f8", lambda: self._enqueue(CMD_TOGGLE))
        keyboard.add_hotkey("ctrl+alt+p", lambda: self._enqueue(CMD_TOGGLE))
        keyboard.add_hotkey("ctrl+alt+q", lambda: self._enqueue(CMD_EXIT))

        # ctrl+v interceptor is registered only when enabled
        # so we don't touch normal paste while OFF.

    def _register_plain_paste(self):
        if self._hotkey_id is None:
            # suppress=True prevents the original paste
            self._hotkey_id = keyboard.add_hotkey(
                "ctrl+v",
                lambda: self._enqueue(CMD_PASTE),
                suppress=True
            )

    def _unregister_plain_paste(self):
        if self._hotkey_id is not None:
            try:
                keyboard.remove_hotkey(self._hotkey_id)
            except Exception:
                pass
            self._hotkey_id = None

    def _enqueue(self, cmd, payload=None):
        try:
            self.cmdq.put_nowait((cmd, payload))
        except Exception:
            pass

    # ---------- Main-thread command pump ----------
    def pump(self):
        # Process all queued commands
        while True:
            try:
                cmd, payload = self.cmdq.get_nowait()
            except queue.Empty:
                break

            if cmd == CMD_TOGGLE:
                self.enabled = not self.enabled
                if self.enabled:
                    self._register_plain_paste()
                    self.app.show_toast("Plain Paste: ON")
                    logging.info("Plain Paste: ON")
                else:
                    self._unregister_plain_paste()
                    self.app.show_toast("Plain Paste: OFF")
                    logging.info("Plain Paste: OFF")

            elif cmd == CMD_PASTE:
                if not self.enabled:
                    # If we somehow get here while off, do nothing
                    continue
                self._do_plain_paste()

            elif cmd == CMD_TOAST:
                self.app.show_toast(payload)

            elif cmd == CMD_EXIT:
                self.app.show_toast("Exiting…")
                logging.info("Exiting…")
                self.app.root.after(200, self.app.root.quit)

        # Schedule next pump
        self.app.root.after(10, self.pump)

    # ---------- Plain paste implementation (main thread) ----------
    def _do_plain_paste(self):
        if self._pasting:
            return  # guard against recursion

        self._pasting = True
        try:
            # Get best-effort text from clipboard (strip formatting)
            txt = self.app.get_clip_text()
            if not isinstance(txt, str):
                txt = ""
            txt = txt.replace("\r\n", "\n").replace("\r", "\n")

            # Put cleaned text on clipboard
            self.app.set_clip_text(txt)

            # Temporarily disable the hotkey so our synthetic Ctrl+V
            # cannot re-trigger the handler and cause a double paste.
            self._unregister_plain_paste()

            # Small delay helps some apps (first paste quirk)
            time.sleep(0.01)

            # Perform the paste
            keyboard.send("ctrl+v")

            # Restore the interceptor
            if self.enabled:
                # Another tiny delay avoids capturing the tail of the synth keyup
                time.sleep(0.01)
                self._register_plain_paste()

            logging.info(f"[PASTE] {len(txt)} chars")

        finally:
            self._pasting = False

def main():
    ctrl = PlainPasteController()
    # Start the command pump and enter Tk mainloop (main thread)
    ctrl.app.root.after(10, ctrl.pump)
    try:
        ctrl.app.root.mainloop()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    # On Windows, run as admin the first time for global hooks.
    main()
