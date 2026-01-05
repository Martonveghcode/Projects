from pynput import keyboard

# Function to execute when ¡ is pressed
def on_press(key):
    try:
        if key.char == '¡':
            kb = keyboard.Controller()
            kb.press(keyboard.Key.ctrl)
            kb.press('i')
            kb.release('i')
            kb.release(keyboard.Key.ctrl)
    except AttributeError:
        pass  # Ignore special keys

# Start listening
with keyboard.Listener(on_press=on_press) as listener:
    listener.join()
