"""Compile all firmware sources with mpy-cross without leaving build artifacts."""
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='pi-timer-mpy-') as directory:
    for source in sorted((root / 'firmware').glob('*.py')):
        subprocess.run([sys.executable, '-m', 'mpy_cross', '-o',
                        str(Path(directory) / (source.stem + '.mpy')), str(source)], check=True)
        print('MicroPython syntax OK:', source.name)
