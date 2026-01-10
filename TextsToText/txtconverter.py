import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox


def splice_txt_files(folder_path: str) -> str:
    """
    Reads all .txt files in folder_path (non-recursive), concatenates them
    into one output file, preserving original formatting.
    Returns the output file path.
    """
    # Collect .txt files (non-recursive) and sort for predictable order
    txt_files = [
        f for f in os.listdir(folder_path)
        if os.path.isfile(os.path.join(folder_path, f)) and f.lower().endswith(".txt")
    ]
    txt_files.sort(key=lambda s: s.lower())

    if not txt_files:
        raise FileNotFoundError("No .txt files found in the selected folder.")

    output_path = os.path.join(folder_path, "spliced_output.txt")

    # Write using binary mode to preserve bytes & line endings exactly.
    # This avoids newline translation and helps prevent formatting changes.
    with open(output_path, "wb") as out_f:
        for i, filename in enumerate(txt_files):
            file_path = os.path.join(folder_path, filename)

            # Add a separator between files (as bytes, using a stable newline)
            sep = (
                b"\n\n"
                + b"=" * 80
                + b"\n"
                + f"FILE: {filename}".encode("utf-8", errors="replace")
                + b"\n"
                + b"=" * 80
                + b"\n"
            )
            if i != 0:
                out_f.write(sep)
            else:
                # For the first file, still include a header (optional)
                out_f.write(
                    b"=" * 80
                    + b"\n"
                    + f"FILE: {filename}".encode("utf-8", errors="replace")
                    + b"\n"
                    + b"=" * 80
                    + b"\n"
                )

            # Read raw bytes and write them unchanged
            with open(file_path, "rb") as in_f:
                out_f.write(in_f.read())

    return output_path


def choose_folder_and_run():
    folder = filedialog.askdirectory(title="Select a folder containing .txt files")
    if not folder:
        return

    try:
        output_path = splice_txt_files(folder)
        messagebox.showinfo(
            "Done",
            f"Created:\n{output_path}\n\nAll .txt files were spliced in alphabetical order."
        )
    except Exception as e:
        messagebox.showerror("Error", str(e))


def main():
    root = tk.Tk()
    root.title("TXT Splicer")
    root.geometry("420x180")
    root.resizable(False, False)

    label = tk.Label(
        root,
        text="Select a folder and combine all .txt files into one.",
        wraplength=380,
        justify="center"
    )
    label.pack(pady=20)

    btn = tk.Button(root, text="Choose Folder", width=20, command=choose_folder_and_run)
    btn.pack(pady=10)

    note = tk.Label(
        root,
        text="Output file will be saved as: spliced_output.txt\n(in the selected folder)",
        fg="gray",
        justify="center"
    )
    note.pack(pady=10)

    root.mainloop()


if __name__ == "__main__":
    # Helps on some Windows setups when launching from explorer
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
