import os
import zipfile
import shutil
import tempfile
import re
from typing import Dict, List, Tuple

# Supported image extensions
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

# Well name regex: A1, A01, h12, etc.
WELL_REGEX = re.compile(r"^([A-Ha-h])\s*0*([1-9]|1[0-2])$")


def normalize_well_name(name: str) -> str | None:
    """
    Convert filename stem to normalized well ID (A1–H12).
    Returns None if invalid.
    """
    m = WELL_REGEX.match(name.strip())
    if not m:
        return None
    row, col = m.groups()
    return f"{row.upper()}{int(col)}"


def is_image(filename: str) -> bool:
    return os.path.splitext(filename.lower())[1] in IMAGE_EXTS


def load_images_from_upload(
    uploaded_files: List,
) -> Tuple[str, Dict[str, str]]:
    """
    Main entry point.

    Parameters
    ----------
    uploaded_files : list of FileStorage
        Flask request.files.getlist(...)

    Returns
    -------
    temp_dir : str
        Temporary directory containing extracted images
    well_to_image : dict
        { "A1": "/tmp/.../A1.jpg", ... }
    """

    temp_dir = tempfile.mkdtemp(prefix="plate_images_")
    image_dir = os.path.join(temp_dir, "images")
    os.makedirs(image_dir, exist_ok=True)

    # Case 1: single ZIP upload
    if len(uploaded_files) == 1 and uploaded_files[0].filename.lower().endswith(".zip"):
        _extract_zip(uploaded_files[0], image_dir)

    # Case 2: single image OR multiple images
    else:
        for f in uploaded_files:
            if not is_image(f.filename):
                continue
            dst = os.path.join(image_dir, os.path.basename(f.filename))
            f.save(dst)

    # Map wells → images
    well_to_image = {}
    for fname in os.listdir(image_dir):
        path = os.path.join(image_dir, fname)
        if not is_image(fname):
            continue

        stem = os.path.splitext(fname)[0]
        well = normalize_well_name(stem)
        if not well:
            continue

        well_to_image[well] = path

    return temp_dir, well_to_image


def _extract_zip(zip_file, out_dir: str) -> None:
    """
    Safely extract zip file to directory.
    """
    with zipfile.ZipFile(zip_file) as zf:
        for member in zf.namelist():
            if member.endswith("/"):
                continue
            if not is_image(member):
                continue

            filename = os.path.basename(member)
            out_path = os.path.join(out_dir, filename)

            with zf.open(member) as src, open(out_path, "wb") as dst:
                shutil.copyfileobj(src, dst)


def cleanup_temp_dir(temp_dir: str) -> None:
    """
    Remove temp directory after processing.
    """
    if temp_dir and os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)
