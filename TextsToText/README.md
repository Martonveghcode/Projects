# TextsToText (TXT Splicer)

A small Tkinter app that combines all `.txt` files in a selected folder into a single output file without changing the original bytes or line endings.

## Features
- Picks a folder and splices all `.txt` files (non-recursive)
- Writes `spliced_output.txt` in the same folder
- Preserves original formatting by copying raw bytes
- Adds a clear separator header between files

## Requirements
- Python 3 (Tkinter is included with standard Python on Windows)

## Usage
1. Run the app:

```powershell
python txtconverter.py
```

2. Click "Choose Folder" and select a directory containing `.txt` files.
3. The output file is created as `spliced_output.txt` in that folder.

## Notes
- Files are processed in case-insensitive alphabetical order.
- Only top-level `.txt` files are included (no subfolders).
