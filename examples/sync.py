"""
"""

import random
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import *

from googleapiutils2 import Drive


def generate_random_data(size_kb: int) -> bytes:
    """Generate random data of the specified size in kilobytes."""
    return bytes(random.randint(0, 255) for _ in range(size_kb * 1024))


def create_random_file(parent: Path, min_kb: int = 1, max_kb: int = 10) -> None:
    """Create a random file with a random size between min_kb and max_kb."""
    file_path = parent / f"file_{random.randint(1, 9999)}.txt"
    file_path.write_bytes(generate_random_data(random.randint(min_kb, max_kb)))


def populate_folder(folder: Path, depth: int) -> None:
    """Populate the given folder with nested folders and files, up to the specified depth."""
    if depth == 0:
        return

    # Create a random number of subdirectories
    for _ in range(random.randint(1, 3)):
        sub_folder = folder / f"folder_{random.randint(1, 9999)}"
        sub_folder.mkdir(exist_ok=True)
        populate_folder(sub_folder, depth - 1)

    # Create a random number of files
    for _ in range(random.randint(1, 5)):
        create_random_file(folder)


base_folder = Path("./data/sync_folder")
base_folder.mkdir(parents=True, exist_ok=True)

# Clear the folder
for child in base_folder.iterdir():
    if child.is_dir():
        shutil.rmtree(child)
    else:
        child.unlink()


populate_folder(base_folder, 3)

# Initialize the Google Drive, Sheets, and Permissions objects
drive = Drive()


folder_id = (
    "https://drive.google.com/drive/u/0/folders/14PokFTuIIUQoqurb3EYwWN7hkb6hpyuS"
)

for file in drive.list(folder_id):
    drive.delete(file["id"])
    
drive.upload(filepath=base_folder, parents=folder_id, recursive=True, update=True)

# download to a tmp dir, and then compare the two folders
with tempfile.TemporaryDirectory() as tmp_dir:
    drive.download(filepath=tmp_dir, file_id=folder_id, recursive=True)
    out = subprocess.run(["diff", "-r", base_folder, tmp_dir])
    print(out)
