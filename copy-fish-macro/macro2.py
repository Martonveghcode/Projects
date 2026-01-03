from pynput import keyboard
import time

kb = keyboard.Controller()

def on_press(key):
    try:
        if key.char == '¡':
            time.sleep(7)  # wait 7 seconds

            kb.press(keyboard.Key.ctrl)
            kb.press('w')
            kb.release('w')
            kb.release(keyboard.Key.ctrl)

    except AttributeError:
        pass  # Ignore special keys

# Start listening
with keyboard.Listener(on_press=on_press) as listener:
    listener.join()
