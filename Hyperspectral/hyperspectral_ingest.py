"""
hyperspectral_ingest.py

Stateful drag-and-drop hyperspectral ingestion + ENVI validation + mixed English/technical results view.
Single-file FastAPI app (no coupling to other codebases).

What it does:
- Upload a folder OR a ZIP archive into /tmp/hyperspectral_ingest/current
- Classify files (raw capture / dark / white / reflectance / metadata / settings / preview)
- Validate ENVI cubes by parsing .hdr and checking:
  - required header fields
  - wavelength list (optional but strongly preferred)
  - binary file exists
  - binary byte-size matches header-declared shape * dtype
- Return a UI that mixes plain English + technical details
"""
import zipfile
import io
import re
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List

import numpy as np
import pandas as pd

from fastapi import UploadFile, APIRouter, File, HTTPException, FastAPI
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse

router = APIRouter(
    prefix="/hyperspectral",
    tags=["hyperspectral"]
)

# =========================
# CONFIG
# =========================

MAX_UPLOAD_MB = 1000
BASE_DIR = Path("/tmp/hyperspectral_ingest")
BASE_DIR.mkdir(parents=True, exist_ok=True)
WORKSPACE = BASE_DIR / "current"
def safe_join_workspace(rel_path: str) -> Path:
    """
    Ensure a user-provided relative path stays inside WORKSPACE.
    """
    rel = (rel_path or "").replace("\\", "/").lstrip("/")
    dest = (WORKSPACE / rel).resolve()
    ws = WORKSPACE.resolve()
    if ws not in dest.parents and dest != ws:
        raise HTTPException(status_code=400, detail="Invalid path")
    return dest


def run_envi_validations() -> List[Dict[str, Any]]:
    """
    Validate all ENVI headers found in the current workspace.
    """
    results = []
    for hdr_path in WORKSPACE.rglob("*.hdr"):
        if hdr_path.is_file():
            results.append(validate_envi_pair(hdr_path))
    return results


# =========================
# FILE CLASSIFICATION
# =========================

FILE_MEANINGS = {
    "capture": "Binary hyperspectral cube (raw sensor data)",
    "darkref": "Dark reference (sensor noise baseline)",
    "whiteref": "White reference (illumination normalization)",
    "reflectance": "Calibrated reflectance cube",
    "metadata": "Instrument / acquisition metadata",
    "preview": "RGB or grayscale preview image",
    "settings": "Acquisition or processing configuration",
    "unknown": "Unclassified file",
}

EXTENSION_TYPES = {
    ".hdr": "ENVI header (describes hyperspectral cube)",
    ".raw": "Binary hyperspectral cube (raw sensor data)",
    ".dat": "Binary hyperspectral cube",
    ".img": "Binary hyperspectral cube (ENVI)",
    ".xml": "Structured metadata",
    ".xsl": "XML stylesheet (presentation only)",
    ".json": "Settings or configuration",
    ".png": "Preview image",
    ".jpg": "Preview image",
    ".jpeg": "Preview image",
}


def reset_workspace() -> None:
    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)
    WORKSPACE.mkdir(parents=True, exist_ok=True)

def extract_zip_to_workspace(file: UploadFile) -> int:
    """
    Safely extract a zip archive into WORKSPACE.
    Returns total extracted bytes.
    """
    total_size = 0

    with zipfile.ZipFile(file.file) as z:
        for info in z.infolist():
            if info.is_dir():
                continue

            # Prevent zip-slip
            rel = info.filename.replace("\\", "/").lstrip("/")
            dest = safe_join_workspace(rel)
            dest.parent.mkdir(parents=True, exist_ok=True)

            with z.open(info) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)

            total_size += info.file_size

    return total_size


def classify_file(path: Path) -> Dict[str, Any]:
    """
    Classify based on filename and extension heuristics.
    """
    name = path.name.lower()
    suffix = path.suffix.lower()
    parts_lower = [p.lower() for p in path.parts]

    if "dark" in name or "darkref" in name:
        role = "darkref"
    elif "white" in name or "whiteref" in name:
        role = "whiteref"
    elif "reflectance" in name or "refl" in name:
        role = "reflectance"
    elif suffix == ".hdr":
        # If there's an obvious reflectance tag in the filename, treat as reflectance header
        if "reflectance" in name or "refl" in name:
            role = "reflectance"
        else:
            role = "capture"
    elif suffix in {".raw", ".dat", ".img"}:
        # Try to infer reflectance vs capture from filename
        if "reflectance" in name or "refl" in name:
            role = "reflectance"
        else:
            role = "capture"
    elif suffix in {".xml", ".xsl"}:
        role = "metadata"
    elif suffix in {".png", ".jpg", ".jpeg"}:
        role = "preview"
    elif suffix == ".json":
        role = "settings"
    else:
        role = "unknown"

    return {
        "path": str(path.relative_to(WORKSPACE)).replace("\\", "/"),
        "name": path.name,
        "extension": suffix,
        "type": role,
        "meaning": FILE_MEANINGS[role],
        "details": EXTENSION_TYPES.get(suffix, "Unrecognized file type"),
        "size_bytes": int(path.stat().st_size),
    }


def scan_workspace() -> Dict[str, Any]:
    files = []
    for f in WORKSPACE.rglob("*"):
        if f.is_file():
            files.append(classify_file(f))

    summary: Dict[str, int] = {}
    for f in files:
        summary[f["type"]] = summary.get(f["type"], 0) + 1

    return {
        "workspace": str(WORKSPACE),
        "file_count": len(files),
        "summary": summary,
        "files": files,
    }


# =========================
# ENVI PARSING + VALIDATION
# =========================

# ENVI "data type" codes → bytes per sample
# Common ones:
# 1=uint8, 2=int16, 3=int32, 4=float32, 5=float64, 12=uint16, 13=uint32, 14=int64, 15=uint64
ENVI_DTYPE_BYTES = {
    1: 1,
    2: 2,
    3: 4,
    4: 4,
    5: 8,
    12: 2,
    13: 4,
    14: 8,
    15: 8,
}
def _strip_envi_value(v: str) -> str:
    return v.strip().strip("{}").strip()


def parse_envi_header(hdr_path: Path) -> Dict[str, Any]:
    """
    Parse minimal ENVI header keys needed for cube validation.
    Also tries to parse wavelength list if present.
    """
    text = hdr_path.read_text(errors="ignore")
    meta: Dict[str, Any] = {}

    # Basic key=value parsing; ENVI headers can be messy but this covers typical exports.
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip().lower()
        v = v.strip()
        meta[k] = v

    def as_int(key: str) -> Optional[int]:
        if key not in meta:
            return None
        try:
            return int(re.findall(r"-?\d+", str(meta[key]))[0])
        except Exception:
            return None

    samples = as_int("samples")
    lines = as_int("lines")
    bands = as_int("bands")
    data_type = as_int("data type")
    meta["data_type"] = data_type


    interleave = _strip_envi_value(str(meta.get("interleave", ""))).lower() or None
    byte_order = as_int("byte order")

    wavelengths: Optional[List[float]] = None
    if "wavelength" in meta:
        raw = str(meta["wavelength"])
        raw = raw.strip()
        if raw.count("{") != raw.count("}") or raw.endswith("{"):
            m = re.search(r"wavelength\s*=\s*\{([\s\S]*?)\}", text, flags=re.IGNORECASE)
            if m:
                raw = "{" + m.group(1) + "}"
        raw2 = re.sub(r"[\r\n]", "", raw).strip().strip("{}")
        toks = [t.strip() for t in raw2.split(",") if t.strip()]
        vals = []
        for t in toks:
            try:
                vals.append(float(t))
            except Exception:
                pass
        if vals:
            wavelengths = vals

    return {
        "hdr_path": str(hdr_path.relative_to(WORKSPACE)).replace("\\", "/"),
        "samples": samples,
        "lines": lines,
        "bands": bands,
        "data_type": data_type,
        "interleave": interleave,
        "byte_order": byte_order,
        "header_offset": as_int("header offset") or 0,
        "has_wavelengths": wavelengths is not None,
        "wavelength_count": len(wavelengths) if wavelengths else 0,
        "wavelengths_preview": (wavelengths[:5] + ["..."] + wavelengths[-5:])
            if (wavelengths and len(wavelengths) > 12)
            else wavelengths,
        "wavelengths": wavelengths,
        "raw_keys_present": sorted(
            [k for k in ("samples", "lines", "bands", "data type", "interleave", "wavelength", "header offset") if k in meta]
        ),
        "meta": meta,
    }

def expected_binary_size_bytes(samples: int, lines: int, bands: int, data_type: int) -> Optional[int]:
    bps = ENVI_DTYPE_BYTES.get(int(data_type))
    if not bps:
        return None
    return int(samples) * int(lines) * int(bands) * int(bps)

def load_envi_cube(hdr: Dict[str, Any], bin_path: Path) -> np.ndarray:
    """
    Load ENVI binary cube into a NumPy array with shape (lines, samples, bands).
    Supports interleave: bil, bip, bsq.
    """
    samples = int(hdr["samples"])
    lines = int(hdr["lines"])
    bands = int(hdr["bands"])
    data_type = int(hdr["data_type"])
    interleave = (hdr.get("interleave") or "").lower()
    header_offset = int(hdr.get("header_offset") or 0)

    dtype_map = {
        1: np.uint8,
        2: np.int16,
        3: np.int32,
        4: np.float32,
        5: np.float64,
        12: np.uint16,
        13: np.uint32,
        14: np.int64,
        15: np.uint64,
    }
    dtype = dtype_map.get(data_type)
    if dtype is None:
        raise ValueError(f"Unsupported ENVI data type: {data_type}")

    with open(bin_path, "rb") as f:
        f.seek(header_offset)
        data = np.fromfile(f, dtype=dtype, count=samples * lines * bands)
    expected = samples * lines * bands
    if data.size != expected:
        raise ValueError(
            f"Binary size mismatch: expected {expected} elements, got {data.size}"
       )

    if interleave == "bil":
        cube = data.reshape((lines, bands, samples)).transpose(0, 2, 1)
    elif interleave == "bip":
        cube = data.reshape((lines, samples, bands))
    elif interleave == "bsq":
        cube = data.reshape((bands, lines, samples)).transpose(1, 2, 0)
    else:
        raise ValueError(f"Unsupported interleave: {interleave}")

    return cube

def generate_plate_rois(
    image_height: int,
    image_width: int,
    plate_type: str = "96",
    margin: int = 0,
) -> Dict[str, tuple]:
    """
    Generate fixed grid ROIs for a microplate.
    Returns: { "A1": (r0, r1, c0, c1), ... }
    """
    if plate_type != "96":
        raise ValueError("Only 96-well plates supported in step 1.")

    rows = list("ABCDEFGH")
    cols = list(range(1, 13))

    cell_h = (image_height - 2 * margin) // len(rows)
    cell_w = (image_width - 2 * margin) // len(cols)

    rois = {}

    for i, r in enumerate(rows):
        for j, c in enumerate(cols):
            r0 = margin + i * cell_h
            r1 = r0 + cell_h
            c0 = margin + j * cell_w
            c1 = c0 + cell_w
            rois[f"{r}{c}"] = (r0, r1, c0, c1)

    return rois

# =========================
# CANONICAL PLATE SCHEMA
# =========================
#
# Hyperspectral plate data MUST conform to:
#
# Columns:
#   Wavelength (float, nm)
#   A1, A2, ..., H12           → mean spectrum per well
#   A1_std, A2_std, ...        → per-band spatial std
#   A1_cv, A2_cv, ...          → per-band CV (%)
#
# Semantics:
# - Values represent REFLECTANCE-derived absorbance OR raw intensity
# - Wavelength axis is absolute (nm), monotonically increasing
# - No interpolation downstream; pipeline assumes this is final
#
# This schema intentionally mirrors spectrometer plate exports
# so downstream code does not branch on data source.
#

def hyperspectral_cube_to_plate_dataframe(
    cube: np.ndarray,
    wavelengths: List[float],
    role: str,
    plate_type: str = "96",
) -> pd.DataFrame:
    """
    Convert hyperspectral cube into the exact table format
    expected by the spectral pipeline.

    Output columns:
    Wavelength | A1 | A2 | ... | H12
    """
    if cube.ndim != 3:
        raise ValueError("Cube must have shape (rows, cols, bands).")

    rows, cols, bands = cube.shape

    if len(wavelengths) != bands:
        raise ValueError("Wavelength count does not match cube bands.")

    rois = generate_plate_rois(rows, cols, plate_type=plate_type)

    data = {
        "Wavelength": [float(w) for w in wavelengths]
    }

    for well, (r0, r1, c0, c1) in rois.items():
        roi = cube[r0:r1, c0:c1, :]

        mean_spectrum = roi.mean(axis=(0, 1))
        std_native = roi.std(axis=(0, 1))

        if role == "reflectance":
            # Reflectance → absorbance (plate-compatible)
            mean_safe = np.clip(mean_spectrum, 1e-6, None)
            absorbance = -np.log10(mean_safe)
        
            std_spectrum = std_native / (mean_safe * np.log(10))
            cv_spectrum = (std_native / mean_safe) * 100
        else:
            mean_safe = np.clip(mean_spectrum, 1e-6, None)
            absorbance = mean_spectrum
            std_spectrum = std_native
            cv_spectrum = (std_native / mean_safe) * 100

        data[well] = absorbance if role == "reflectance" else mean_spectrum
        data[f"{well}_std"] = std_spectrum
        data[f"{well}_cv"] = cv_spectrum

    df = pd.DataFrame(data)

    # Attach provenance metadata (non-invasive)
    df.attrs["data_source"] = "hyperspectral"
    df.attrs["source_role"] = role
    df.attrs["plate_type"] = plate_type
    df.attrs["wavelength_unit"] = "nm"

    return df

def select_primary_envi_cube() -> Optional[Dict[str, Any]]:
    """
    Choose which ENVI cube to use for plate extraction.
    Priority:
      1) reflectance
      2) capture (raw)
    Returns dict with keys: hdr, bin_path, role
    """
    candidates = []

    for hdr_path in WORKSPACE.rglob("*.hdr"):
        if not hdr_path.is_file():
            continue

        hdr = parse_envi_header(hdr_path)
        bin_path = find_associated_binary(hdr_path, hdr.get("meta", {}))
        if not bin_path:
            continue

        role = classify_file(hdr_path)["type"]
        candidates.append({
            "hdr": hdr,
            "bin_path": bin_path,
            "role": role,
        })

    # prefer reflectance
    for c in candidates:
        if c["role"] == "reflectance":
            return c

    # fallback to raw capture
    for c in candidates:
        if c["role"] == "capture":
            return c

    return None

def load_selected_cube_and_wavelengths():
    """
    Load the chosen ENVI cube and its wavelength axis.
    Returns: (cube, wavelengths, role)
    """
    selected = select_primary_envi_cube()
    if not selected:
        raise RuntimeError("No suitable ENVI cube found (reflectance or raw).")

    hdr = selected["hdr"]
    bin_path = selected["bin_path"]
    role = selected["role"]

    cube = load_envi_cube(hdr, bin_path)

    wavelengths = hdr.get("wavelengths")

    if not wavelengths:
        raise RuntimeError("Selected cube has no wavelength definition.")

    wavelengths = [float(w) for w in wavelengths]

    return cube, wavelengths, role

def build_qc_summary(
    df: pd.DataFrame,
    cv_warn: float = 10.0,
    cv_fail: float = 20.0,
    wl_min: float = 450.0,
    wl_max: float = 2510.0
) -> pd.DataFrame:
    """
    Build one-row-per-well QC decision table.
    Missing inputs → 'Unknown'
    """

    rows = []

    for col in df.columns:
        if not col.endswith("_cv"):
            continue

        well = col.replace("_cv", "")
        cv_vals = df[col].dropna()
        cv_vals = cv_vals[np.isfinite(cv_vals)]

        wavelengths = df["Wavelength"]
        mask = (wavelengths >= wl_min) & (wavelengths <= wl_max)
        cv_vals = cv_vals[mask.values]

        if cv_vals.empty:
            mean_cv = None
            max_cv = None
            status = "Unknown"
            reason = "CV not available"
        else:
            mean_cv = float(cv_vals.mean())
            max_cv = float(cv_vals.max())

            if max_cv >= cv_fail:
                status = "FAIL"
                reason = f"High spectral variability (CV {max_cv:.1f}%)"
            elif mean_cv >= cv_warn:
                status = "REVIEW"
                reason = f"Moderate spectral variability (CV {mean_cv:.1f}%)"
            else:
                status = "PASS"
                reason = "Spectrally stable"

        if status == "PASS":
            interpretation = "Spectrally stable. Measurements are consistent across the well."
            action = "Use directly for analysis."
        elif status == "REVIEW":
            interpretation = "Moderate spectral variability detected."
            action = "Cross-check with HSV texture or replicates."
        elif status == "FAIL":
            interpretation = "High spectral instability. Measurements are unreliable."
            action = "Exclude from biological interpretation."
        else:
            interpretation = "Spectral quality could not be determined."
            action = "Review metadata and raw data."
        rows.append({
            "Well": well,
            "Mean_CV_%": mean_cv,
            "Max_CV_%": max_cv,
            "Spectral_CV_Status": status,
            "Interpretation": interpretation,
            "Recommended_Action": action,
            "Reason": reason
        })

    return pd.DataFrame(rows)

def build_plate_dataframe_from_workspace(plate_type: str = "96") -> pd.DataFrame:
    """
    Full in-memory conversion:
    hyperspectral ENVI → plate-style absorbance DataFrame.
    """
    cube, wavelengths, role = load_selected_cube_and_wavelengths()

    # --- Auto-extract acquisition metadata ---
    meta = {}

    # From ENVI header
    selected = select_primary_envi_cube()
    hdr_meta = selected["hdr"].get("meta", {}) if selected else {}

    for k in ("exposure", "integration time", "gain", "illumination", "sensor mode"):
        if k in hdr_meta:
            meta[k.replace(" ", "_")] = hdr_meta[k]

    # From XML metadata files (best-effort)
    for xml_path in WORKSPACE.rglob("*.xml"):
        try:
            text = xml_path.read_text(errors="ignore").lower()
            if "exposure" in text:
                meta.setdefault("exposure", "present (xml)")
            if "illumination" in text:
                meta.setdefault("illumination", "present (xml)")
            if "gain" in text:
                meta.setdefault("gain", "present (xml)")
        except Exception:
            pass


    df = hyperspectral_cube_to_plate_dataframe(
        cube=cube,
        wavelengths=wavelengths,
        role=role,
        plate_type=plate_type,
    )

    df.attrs["source_role"] = role
    df.attrs.update(meta)
    qc_df = build_qc_summary(df)
    df.attrs["qc_summary"] = qc_df.to_dict(orient="records")
    return df


def find_associated_binary(hdr_path: Path, hdr_meta: Dict[str, Any]) -> Optional[Path]:
    for k in ("data file", "datafile", "file name", "filename"):
        v = hdr_meta.get(k)
        if v:
            name = _strip_envi_value(str(v)).strip().strip('"')
            cand = (hdr_path.parent / name)
            if cand.exists() and cand.is_file():
                return cand

    candidates = [
        hdr_path.with_suffix(".raw"),
        hdr_path.with_suffix(".dat"),
        hdr_path.with_suffix(".img"),
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c

    parent = hdr_path.parent
    stem = hdr_path.stem.lower()
    for ext in (".raw", ".dat", ".img"):
        c = parent / (stem + ext)
        if c.exists() and c.is_file():
            return c
    return None


def validate_envi_pair(hdr_path: Path) -> Dict[str, Any]:
    """
    Validate one ENVI header + its binary cube.
    """
    issues: List[str] = []
    hdr = parse_envi_header(hdr_path)
    bin_path = find_associated_binary(hdr_path, hdr.get("meta", {}))

    if not bin_path:
        issues.append("No associated binary cube found for this header (.raw/.dat/.img).")

    # Required header fields
    for field in ("samples", "lines", "bands", "data_type", "interleave"):
        if hdr.get(field) in (None, "", 0):
            issues.append(f"Missing or invalid header field: {field}")

        # -------------------------
    # Data type validation
    # -------------------------
    dt = hdr.get("data_type")
    if dt is None:
        issues.append("Missing ENVI data type.")
    elif int(dt) not in ENVI_DTYPE_BYTES:
        issues.append(f"Unsupported ENVI data type code: {dt}")

    # -------------------------
    # Binary size validation
    # -------------------------
    size_expected = None
    size_actual = None
    header_offset = int(hdr.get("header_offset") or 0)

    if bin_path:
        try:
            size_actual = int(bin_path.stat().st_size)
        except Exception:
            issues.append("Unable to read binary file size.")

    if (
        bin_path
        and hdr.get("samples")
        and hdr.get("lines")
        and hdr.get("bands")
        and dt is not None
        and int(dt) in ENVI_DTYPE_BYTES
    ):
        base_size = expected_binary_size_bytes(
            hdr["samples"], hdr["lines"], hdr["bands"], dt
        )

        if base_size is not None:
            size_expected = header_offset + base_size

            if size_actual is not None and size_expected != size_actual:
                issues.append(
                    f"Binary size mismatch: expected {size_expected:,} bytes, got {size_actual:,} bytes."
                )
        else:
            issues.append("Cannot compute expected byte size (unsupported dtype).")
    else:
        issues.append("Insufficient header information to validate binary size.")

    # -------------------------
    # Wavelength sanity check
    # -------------------------
    bands = int(hdr.get("bands") or 0)
    wavelength_count = int(hdr.get("wavelength_count") or 0)

    if hdr.get("has_wavelengths"):
        if bands and wavelength_count and wavelength_count != bands:
            issues.append(
                f"Wavelength count ({wavelength_count}) does not match band count ({bands})."
            )
    else:
        issues.append(
            "No wavelength list found in header (recommended for spectral analysis)."
        )

    # -------------------------
    # Error / warning split
    # -------------------------
    errors: List[str] = []
    warnings: List[str] = []

    for msg in issues:
        msg_l = msg.lower()
        if any(k in msg_l for k in ("missing", "mismatch", "unsupported", "unable", "insufficient")):
            errors.append(msg)
        else:
            warnings.append(msg)

    return {
        "hdr": hdr,
        "binary_path": (
            str(bin_path.relative_to(WORKSPACE)).replace("\\", "/")
            if bin_path and WORKSPACE in bin_path.parents
            else str(bin_path) if bin_path
            else None
        ),
        "binary_size_bytes": size_actual,
        "expected_size_bytes": size_expected,
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }

# =========================
# INGEST ROUTES
# =========================

@router.post("/upload-folder")
async def upload_folder(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files received")

    # ❌ Reject unsupported .7z archives explicitly
    if len(files) == 1 and files[0].filename.lower().endswith(".7z"):
        raise HTTPException(
            status_code=400,
            detail=(
                "7z archives are not supported. "
                "Please upload the extracted folder or a .zip file."
            )
        )

    reset_workspace()

    total_size = 0
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024

    try:
        # ZIP upload
        if len(files) == 1 and files[0].filename.lower().endswith(".zip"):
            try:
                total_size = extract_zip_to_workspace(files[0])
            finally:
                await files[0].close()

            if total_size > max_bytes:
                raise HTTPException(status_code=413, detail="ZIP contents exceed upload limit")

        # Folder upload
        else:
            for f in files:
                dest = safe_join_workspace(f.filename)
                dest.parent.mkdir(parents=True, exist_ok=True)

                try:
                    with open(dest, "wb") as out:
                        while True:
                            chunk = await f.read(1024 * 1024)
                            if not chunk:
                                break

                            total_size += len(chunk)
                            if total_size > max_bytes:
                                raise HTTPException(status_code=413, detail="Upload exceeds 1 GB limit")

                            out.write(chunk)
                finally:
                    await f.close()

    except HTTPException:
        reset_workspace()
        raise

    except Exception as e:
        reset_workspace()
        raise HTTPException(status_code=500, detail=str(e))

    scan = scan_workspace()
    scan["status"] = "ingested"
    scan["total_mb"] = round(total_size / (1024 * 1024), 2)
    scan["envi_validation"] = run_envi_validations()

    return JSONResponse(content=scan)

@router.get("/status")
def status():
    if not WORKSPACE.exists() or not any(WORKSPACE.rglob("*")):
        return {"status": "empty"}
    scan = scan_workspace()
    scan["envi_validation"] = run_envi_validations()
    scan["status"] = "ready"
    return scan

@router.get("/download_plate_excel")
def download_plate_excel():
    """
    Convert hyperspectral data in workspace into
    pipeline-compatible plate Excel and download it.
    """
    try:
        df = build_plate_dataframe_from_workspace(plate_type="96")
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    out_path = WORKSPACE / "hyperspectral_plate_96.xlsx"
    with pd.ExcelWriter(out_path) as writer:
         df.to_excel(writer, index=False, sheet_name="Spectra")
         pd.DataFrame([df.attrs]).to_excel(writer, index=False, sheet_name="Metadata")

         if "qc_summary" in df.attrs:
            pd.DataFrame(df.attrs["qc_summary"]).to_excel(
                writer, index=False, sheet_name="Spectral_QC"
            )

    return FileResponse(
        path=out_path,
        filename="hyperspectral_plate_96.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# =========================
# UI (HTML + JS)
# =========================

@router.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Hyperspectral Ingest</title>
  <style>
    body {
      font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: #0f172a;
      color: #e5e7eb;
      margin: 0;
      padding: 2rem;
    }
    h2 { margin: 0 0 0.75rem 0; }
    .muted { color: #94a3b8; font-size: 0.92rem; }
    code { color: #93c5fd; }

    .dropzone {
      border: 2px dashed #64748b;
      border-radius: 14px;
      padding: 2.5rem;
      text-align: center;
      cursor: pointer;
      background: #020617;
      transition: border-color 0.15s ease;
      user-select: none;
    }
    .dropzone.dragover { border-color: #22d3ee; }

    .status {
      margin-top: 1rem;
      color: #94a3b8;
      min-height: 1.2rem;
    }

    .progress-container {
      width: 100%;
      height: 10px;
      background: #020617;
      border-radius: 6px;
      overflow: hidden;
      margin-top: 1rem;
      border: 1px solid #111827;
    }
    .progress-bar {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #22d3ee, #38bdf8);
      transition: width 0.15s ease;
    }

    .controls {
      margin-top: 1rem;
      display: flex;
      align-items: center;
      gap: 1rem;
      flex-wrap: wrap;
    }
    .toggle {
      display: inline-flex;
      align-items: center;
      gap: 0.6rem;
      user-select: none;
      color: #cbd5e1;
      background: #020617;
      border: 1px solid #111827;
      padding: 0.5rem 0.75rem;
      border-radius: 999px;
    }
    .toggle input { transform: scale(1.1); }

    .panel {
      margin-top: 1.25rem;
      background: #020617;
      border: 1px solid #1f2937;
      border-radius: 14px;
      padding: 1rem;
      display: none;
    }
    .panel-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      padding-bottom: 0.75rem;
      border-bottom: 1px solid #111827;
      margin-bottom: 1rem;
    }
    .panel-title { font-size: 1.05rem; font-weight: 800; }
    .panel-subtitle { font-size: 0.85rem; color: #94a3b8; margin-top: 0.15rem; }
    .badge {
      padding: 0.35rem 0.65rem;
      border-radius: 999px;
      background: #0b1220;
      border: 1px solid #1f2937;
      color: #a5b4fc;
      font-size: 0.75rem;
      letter-spacing: 0.04em;
      white-space: nowrap;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0.9rem;
    }
    @media (max-width: 900px) {
      .grid { grid-template-columns: 1fr; }
    }
    .card {
      background: #0b1220;
      border: 1px solid #111827;
      border-radius: 14px;
      padding: 0.9rem;
    }
    .card-title {
      font-size: 0.9rem;
      font-weight: 800;
      color: #e5e7eb;
      margin-bottom: 0.6rem;
    }
    .card-body {
      color: #cbd5e1;
      font-size: 0.92rem;
      line-height: 1.45;
    }
    .list { margin: 0; padding-left: 1.2rem; }
    .list li { margin: 0.3rem 0; }
    .kv {
      display: grid;
      grid-template-columns: 180px 1fr;
      gap: 0.35rem 0.75rem;
    }
    .k { color: #94a3b8; font-size: 0.85rem; }
    .v { color: #e5e7eb; font-size: 0.85rem; word-break: break-word; }

    pre {
      margin-top: 1rem;
      padding: 1rem;
      background: #020617;
      border-radius: 12px;
      max-height: 50vh;
      overflow: auto;
      font-size: 0.82rem;
      border: 1px solid #111827;
      display: none;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      border: 1px solid #111827;
      background: #020617;
      padding: 0.35rem 0.6rem;
      border-radius: 999px;
      font-size: 0.82rem;
      color: #cbd5e1;
    }
    .pill.good { border-color: #14532d; color: #bbf7d0; }
    .pill.bad  { border-color: #7f1d1d; color: #fecaca; }

    .section-title {
      font-weight: 800;
      margin: 0.2rem 0 0.5rem 0;
      color: #e5e7eb;
    }
    .tiny { font-size: 0.82rem; color: #94a3b8; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
  </style>
</head>
<body>

  <h2>Hyperspectral Folder Ingest</h2>
  <div class="muted">Drag & drop a hyperspectral folder. Upload replaces previous dataset. (≤ 1 GB)</div>

  <div class="dropzone" id="dropzone" style="margin-top:1rem;">
    Drag & drop a hyperspectral folder here<br/>
    <span class="muted">or click to select a ZIP file</span>
  </div>

  <!-- Folder picker -->
  <input type="file"
        id="folderInput"
        webkitdirectory
        directory
        multiple
        style="display:none"/>

  <!-- ZIP picker -->
  <input type="file"
        id="zipInput"
        accept=".zip"
        style="display:none"/>

  <div class="status" id="status"></div>

  <div class="progress-container">
    <div class="progress-bar" id="progressBar"></div>
  </div>

  <div class="controls">
    <label class="toggle"><input type="checkbox" id="execToggle" checked />Executive view</label>
    <label class="toggle"><input type="checkbox" id="showDebug" />Show raw JSON</label>
    
    <button id="downloadExcelBtn" class="toggle">
      Download plate Excel
    </button>
  </div>
  
  <div class="panel" id="resultPanel">
    <div class="panel-header">
      <div>
        <div class="panel-title" id="panelTitle">Dataset Summary</div>
        <div class="panel-subtitle" id="panelSubtitle"></div>
      </div>
      <div class="badge" id="panelStatusBadge">READY</div>
    </div>

    <div class="grid">
      <div class="card">
        <div class="card-title">What you uploaded</div>
        <div class="card-body" id="englishSummary"></div>
      </div>

      <div class="card">
        <div class="card-title">Data integrity check (automatic)</div>
        <div class="card-body" id="enviValidation"></div>
      </div>

      <div class="card">
        <div class="card-title">What this dataset contains</div>
        <div class="card-body"><ul class="list" id="qualityFlags"></ul></div>
      </div>

      <div class="card">
        <div class="card-title">Warnings</div>
        <div class="card-body"><ul class="list" id="warnings"></ul></div>
      </div>

      <div class="card">
        <div class="card-title">File breakdown</div>
        <div class="card-body" id="technicalSnapshot"></div>
      </div>

      <div class="card">
  <div class="card-title">How the data is converted into real values</div>
  <div class="card-body">

    <div class="section-title">What “calibration” means</div>
    <div class="tiny">
      Calibration converts raw camera measurements into real-world reflectance values
      that can be compared across time, sensors, or locations.
    </div>

    <div class="section-title" style="margin-top:0.7rem;">The idea in simple terms</div>
    <ul class="list">
      <li><b>Raw</b> — what the camera directly recorded (includes noise and lighting effects)</li>
      <li><b>Dark</b> — the camera’s background signal (what it sees with no light)</li>
      <li><b>White</b> — a known bright reference (what “100% reflection” looks like)</li>
    </ul>

    <div class="section-title" style="margin-top:0.7rem;">The standard formula</div>
    <div class="mono">Reflectance = (Raw − Dark) ÷ (White − Dark)</div>

    <div class="tiny" style="margin-top:0.6rem;">
      This removes sensor noise and lighting effects, leaving only the material’s true reflectance.
    </div>

    <div class="section-title" style="margin-top:0.8rem;">What this means for you</div>
    <ul class="list">
      <li>If <b>reflectance data is present</b>, calibration is already done — analyze directly.</li>
      <li>If only <b>raw + dark + white</b> files are present, reflectance can be computed later.</li>
      <li>Most users do <b>not</b> need to redo calibration.</li>
    </ul>

  </div>
</div>

        </div>
      </div>
    </div>
  </div>

  <pre id="output"></pre>

<script>
const dropzone = document.getElementById("dropzone");
const output = document.getElementById("output");
const statusEl = document.getElementById("status");
const folderInput = document.getElementById("folderInput");
const zipInput = document.getElementById("zipInput");
const resultPanel = document.getElementById("resultPanel");
const execToggle = document.getElementById("execToggle");
const showDebug = document.getElementById("showDebug");
const panelSubtitle = document.getElementById("panelSubtitle");
const panelStatusBadge = document.getElementById("panelStatusBadge");
const englishSummary = document.getElementById("englishSummary");
const qualityFlags = document.getElementById("qualityFlags");
const warningsEl = document.getElementById("warnings");
const technicalSnapshot = document.getElementById("technicalSnapshot");
const enviValidation = document.getElementById("enviValidation");
const downloadExcelBtn = document.getElementById("downloadExcelBtn");

let lastResultJson = null;

execToggle.addEventListener("change", () => { if (lastResultJson) renderResult(lastResultJson); });
showDebug.addEventListener("change", () => { if (lastResultJson) renderResult(lastResultJson); });
downloadExcelBtn.addEventListener("click", () => {
  window.location.href = "/hyperspectral/download_plate_excel";
});


dropzone.addEventListener("click", () => {
  // Click = ZIP only (folders via drag & drop)
  zipInput.click();
});


folderInput.addEventListener("change", async () => {
  const files = Array.from(folderInput.files || []);
  if (!files.length) return;
  await handleFiles(files);
  folderInput.value = "";
});

zipInput.addEventListener("change", async () => {
  const files = Array.from(zipInput.files || []);
  if (!files.length) return;
  await handleFiles(files);
  zipInput.value = "";
});


dropzone.addEventListener("dragover", e => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", async e => {
  e.preventDefault();
  dropzone.classList.remove("dragover");

  const items = e.dataTransfer.items;
  if (!items || !items.length) return;

  const files = [];

  // Robust directory traversal for Chrome/WebKit drag-drop
  async function traverse(entry, prefix="") {
    if (entry.isFile) {
      await new Promise(resolve => {
        entry.file(file => {
          file._relativePath = prefix + file.name;
          files.push(file);
          resolve();
        });
      });
    } else if (entry.isDirectory) {
      const reader = entry.createReader();
      // readEntries can return partial batches; loop until empty
      while (true) {
        const batch = await new Promise(resolve => reader.readEntries(resolve));
        if (!batch || batch.length === 0) break;
        for (const child of batch) {
          await traverse(child, prefix + entry.name + "/");
        }
      }
    }
  }

  for (const item of items) {
    const entry = item.webkitGetAsEntry && item.webkitGetAsEntry();
    if (entry) await traverse(entry);
  }

  await handleFiles(files);
});

async function handleFiles(fileList) {
  if (!fileList || fileList.length === 0) {
    statusEl.textContent = "No files detected.";
    return;
  }

  let totalSize = 0;
  const form = new FormData();
  const progressBar = document.getElementById("progressBar");
  progressBar.style.width = "0%";

  for (const file of fileList) {
    totalSize += file.size;
    const rel = file._relativePath || file.webkitRelativePath || file.name;
    form.append("files", file, rel);
  }

  const max = 1024 * 1024 * 1024;
  if (totalSize > max) {
    statusEl.textContent = "Upload exceeds 1 GB limit.";
    return;
  }

  await uploadWithProgress(form);
}

function uploadWithProgress(form) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const progressBar = document.getElementById("progressBar");

    xhr.open("POST", "/hyperspectral/upload-folder");

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const percent = Math.round((e.loaded / e.total) * 100);
        progressBar.style.width = percent + "%";
        statusEl.textContent = `Uploading... ${percent}%`;
      } else {
        statusEl.textContent = "Uploading...";
      }
    };

    xhr.onload = () => {
      let response = xhr.responseText;
      let json = null;
      try { json = response ? JSON.parse(response) : null; } catch (e) {}

      if (xhr.status >= 200 && xhr.status < 300) {
        progressBar.style.width = "100%";
        statusEl.textContent = "✅ Upload complete";
        lastResultJson = json;
        renderResult(json);
        resolve();
      } else {
        progressBar.style.width = "0%";
        statusEl.textContent = `❌ Upload failed (${xhr.status})`;
        output.textContent = response || "(No response body)";
        output.style.display = "block";
        reject(new Error("Upload failed"));
      }
    };

    xhr.onerror = () => {
      progressBar.style.width = "0%";
      statusEl.textContent = "❌ Upload failed (network)";
      reject(new Error("Network error"));
    };

    xhr.send(form);
  });
}

function hasType(json, type) {
  return json && json.summary && json.summary[type] && json.summary[type] > 0;
}

function computeFlagsAndWarnings(json) {
  const flags = [];
  const warnings = [];

  const files = json.files || [];
  const hasRaw = files.some(f => [".raw", ".dat", ".img"].includes(f.extension));
  const hasHdr = files.some(f => f.extension === ".hdr");
  const hasDark = hasType(json, "darkref");
  const hasWhite = hasType(json, "whiteref");
  const hasReflectance = hasType(json, "reflectance");
  const hasPreview = hasType(json, "preview");
  const hasSettings = hasType(json, "settings");
  const hasMetadata = hasType(json, "metadata");

  if (hasHdr && hasRaw)
  flags.push("All data files are complete and correctly linked.");
  if (hasDark && hasWhite)
  flags.push("Reference files are included for optional recalibration.");
  if (hasReflectance)
  flags.push("Data has already been converted into real-world, ready-to-use values.");
  if (hasMetadata) flags.push("Metadata present (traceability/reproducibility).");
  if (hasPreview) flags.push("Preview image present (quick-look validation).");
  if (hasSettings) flags.push("Acquisition settings JSON present.");

  if (hasReflectance && (hasDark || hasWhite || hasRaw)) {
    warnings.push(
  "This dataset already contains final, ready-to-use values. Extra calibration files are optional and only needed for advanced workflows."
);

  }
  if (hasRaw && !hasHdr && !hasReflectance) {
    warnings.push("Binary cube present but no .hdr header detected — cube dimensions/wavelengths may be unavailable.");
  }
  if (hasHdr && !hasRaw && !hasReflectance) {
    warnings.push("Header(s) present but no binary cube detected — dataset may be incomplete.");
  }
  if (hasRaw && (!hasDark || !hasWhite) && !hasReflectance) {
    warnings.push("Raw cube present but missing dark/white references — reflectance recalibration may not be possible.");
  }

  if (warnings.length === 0) warnings.push("No warnings detected.");
  return { flags, warnings };
}

function renderEnviValidation(json) {
  const vals = (json.envi_validation || []);
  if (!vals.length) {
    return `<div class="muted">No ENVI headers (.hdr) were detected, so cube validation could not run.</div>`;
  }

  // Show compact per-header summary (English + technical)
  const blocks = vals.map(v => {
    const ok = v.valid && (!v.errors || v.errors.length === 0);
    const hdr = v.hdr || {};
    const dims = (hdr.samples && hdr.lines && hdr.bands) ? `${hdr.samples}×${hdr.lines}×${hdr.bands}` : "n/a";
    const dt = (hdr.data_type != null) ? String(hdr.data_type) : "n/a";
    const interleave = hdr.interleave || "n/a";
    const wl = hdr.has_wavelengths ? `✅ (${hdr.wavelength_count})` : `❌`;
    const expected = v.expected_size_bytes != null ? v.expected_size_bytes.toLocaleString() : "n/a";
    const actual = v.binary_size_bytes != null ? v.binary_size_bytes.toLocaleString() : "n/a";
    const pill = ok ? `<span class="pill good">✅ File check passed</span>` : `<span class="pill bad">⚠️ Check</span>`;

    const issues = [...(v.errors || []), ...(v.warnings || [])]
  .map(x => `<li>${escapeHtml(x)}</li>`)
  .join("");

const issueHtml = issues ? `<ul class="list" style="margin-top:0.6rem;">${issues}</ul>` : "";


    return `
      <div style="margin-bottom:0.9rem;">
        ${pill}
        <div class="tiny" style="margin-top:0.35rem;">
          <b>${escapeHtml(hdr.hdr_path || "header")}</b>
          ${v.binary_path ? `• <span class="mono">${escapeHtml(v.binary_path)}</span>` : ""}
        </div>
        <div class="tiny" style="margin-top:0.4rem;">
  Image size: ${hdr.samples || "?"} × ${hdr.lines || "?"} pixels<br/>
  Measured colors: ${hdr.wavelength_count || "?"} distinct wavelengths<br/>
  Color information: ${hdr.has_wavelengths ? "fully defined ✅" : "missing ⚠️"}
</div>

        <div class="tiny" style="margin-top:0.25rem;">
  File completeness check: ${expected === actual ? "passed ✅" : "check needed ⚠️"}
</div>

        ${issueHtml}
      </div>
    `;
  }).join("");

  return blocks;
}

function renderResult(json) {
  if (!json) return;

  const executive = execToggle.checked;
  const debug = showDebug.checked;

  resultPanel.style.display = "block";
  panelStatusBadge.textContent = "INGESTED";

  const ws = (json.workspace || "").replace(/\\\\/g, "/");
  const mb = json.total_mb != null ? json.total_mb : "n/a";
  panelSubtitle.textContent = `${json.file_count || 0} files • ${mb} MB • Workspace: ${ws}`;

  const { flags, warnings } = computeFlagsAndWarnings(json);

  const hasReflectance = hasType(json, "reflectance");
  const hasRaw = (json.files || []).some(f => f.extension === ".raw" || f.extension === ".dat" || f.extension === ".img");
  const hasDarkWhite = hasType(json, "darkref") && hasType(json, "whiteref");

  // Mixed English + technical summary
  if (executive) {
    englishSummary.innerHTML = `
      <div>
        <b>Outcome:</b> Upload succeeded.  
        This dataset is <b>ready to use</b> — no extra processing is required before analysis.
      </div>
      <div class="tiny" style="margin-top:0.6rem;">
        • Reflectance: ${hasReflectance ? "<b>present</b> (fast analysis)" : "not detected"}<br/>
        • Raw sensor cube: ${hasRaw ? "<b>present</b>" : "not detected"}<br/>
        • Dark/White references: ${hasDarkWhite ? "<b>present</b> (recalibration possible)" : "incomplete"}<br/>
      </div>
      <div class="tiny" style="margin-top:0.6rem;">
        Next step: ${hasReflectance ? "analyze reflectance cube directly" : "use raw + references to compute reflectance"}.
      </div>
    `;
  } else {
    englishSummary.innerHTML = `
      <div><b>Detected package:</b> ENVI-style hyperspectral export.</div>
      <div class="tiny" style="margin-top:0.6rem;">
        This ingest validates the dataset structure (headers, cube sizes, and wavelengths when available).
      </div>
      <div class="tiny" style="margin-top:0.6rem;">
        <b>Calibration reference:</b> <span class="mono">R = (Raw − Dark) / (White − Dark)</span>
      </div>
    `;
  }

  // ENVI validation panel
  enviValidation.innerHTML = renderEnviValidation(json);

  // Flags/warnings
  qualityFlags.innerHTML = flags.map(x => `<li>${escapeHtml(x)}</li>`).join("");
  warningsEl.innerHTML = warnings.map(x => `<li>${escapeHtml(x)}</li>`).join("");

  // Technical snapshot counts
  const s = json.summary || {};
  const snapshot = [
    ["Raw capture", s.capture || 0],
    ["Dark reference", s.darkref || 0],
    ["White reference", s.whiteref || 0],
    ["Reflectance product", s.reflectance || 0],
    ["Metadata", s.metadata || 0],
    ["Settings", s.settings || 0],
    ["Preview", s.preview || 0],
    ["Unknown", s.unknown || 0],
  ];

  technicalSnapshot.innerHTML = `
    <div class="kv">
      ${snapshot.map(([k,v]) => `
        <div class="k">${escapeHtml(k)}</div>
        <div class="v">${v}</div>
      `).join("")}
    </div>
    ${executive ? `<div class="tiny" style="margin-top:0.7rem;">(Turn off Executive view for more technical wording.)</div>` : ""}
  `;

  // Debug JSON
  output.textContent = JSON.stringify(json, null, 2);
  output.style.display = debug ? "block" : "none";
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
</script>

</body>
</html>
"""
app = FastAPI(title="Hyperspectral Ingest")
app.include_router(router)

from fastapi.responses import RedirectResponse

@app.get("/")
def root():
    return RedirectResponse(url="/hyperspectral")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "Hyperspectral.hyperspectral_ingest:app",
        host="127.0.0.1",
        port=8001,
        reload=True
    )