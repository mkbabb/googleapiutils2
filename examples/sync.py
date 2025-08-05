from __future__ import annotations

import random
import shutil
import subprocess
import tempfile
from pathlib import Path

from googleapiutils2 import Drive


def generate_random_data(size_kb: int) -> bytes:
    """Generate random data of the specified size in kilobytes."""
    return bytes(random.randint(0, 255) for _ in range(size_kb * 1024))


def create_random_file(parent: Path, min_kb: int = 1, max_kb: int = 10) -> None:
    """Create a random file with a random size between min_kb and max_kb."""
    file_path = parent / f"file_{random.randint(1, 9999)}.txt"
    file_path.write_bytes(generate_random_data(random.randint(min_kb, max_kb)))


def populate_folder(folder: Path, dir_count: int = 3, file_count: int = 5) -> None:
    """Populate the given folder with nested folders and files."""

    def inner(folder: Path, depth: int) -> None:
        if depth == 0:
            return

        for _ in range(random.randint(1, dir_count)):
            sub_folder = folder / f"folder_{random.randint(1, 9999)}"
            sub_folder.mkdir(exist_ok=True)
            inner(sub_folder, depth - 1)

        for _ in range(random.randint(1, file_count)):
            create_random_file(folder)

    inner(folder, dir_count)


def clear_folder(folder: Path) -> None:
    """Clear the given folder."""
    for child in folder.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


base_folder = Path("./data/sync_folder")
base_folder.mkdir(parents=True, exist_ok=True)

clear_folder(base_folder)


populate_folder(
    base_folder,
    dir_count=3,
    file_count=5,
)


drive = Drive()

folder_id = "https://drive.google.com/drive/u/0/folders/14PokFTuIIUQoqurb3EYwWN7hkb6hpyuS"

for file in drive.list(folder_id):
    drive.delete(file["id"])

drive.upload(filepath=base_folder, parents=folder_id, recursive=True, update=True)


# download to a tmp dir, and then compare the two folders
with tempfile.TemporaryDirectory() as tmp_dir:
    drive.download(filepath=tmp_dir, file_id=folder_id, recursive=True)
    out = subprocess.run(["diff", "-r", base_folder, tmp_dir])
    print(out)
