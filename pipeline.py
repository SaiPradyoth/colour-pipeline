# ================================
# pipeline.py  (FINAL VERSION)
# Spectral → XYZ → Lab → ΔE2000
# Supports: Lab Target OR Reference Well
# Correct λmax detection (RAW absorbance, 400–700 nm)
# ================================

import os
import pandas as pd
import numpy as np
import colour
from colorimetry import compute_xyz_lab_from_absorbance, delta_e2000

# ----------------------------------------------------
# LOAD DATAFRAME (supports xlsx, xls, csv)
# ----------------------------------------------------
def _load_plate_dataframe(file_path):
    ext = os.path.splitext(file_path)[1].lower()

    # First load raw text to locate header row
    try:
        if ext == ".csv":
            raw = pd.read_csv(file_path, header=None, on_bad_lines="skip")
        elif ext == ".xls":
            raw = pd.read_excel(file_path, header=None, engine="xlrd")
        else:
            raw = pd.read_excel(file_path, header=None)
    except Exception as e:
        raise ValueError(f"Could not read file: {e}")

    # Locate header row containing “Wavelength”
    header_row_index = None
    for i in range(min(50, len(raw))):
        row_str = " ".join(raw.iloc[i].astype(str).values).lower()
        if "wavelength" in row_str:
            header_row_index = i
            break

    if header_row_index is None:
        raise ValueError("No 'Wavelength' header found in the first 50 rows.")

    # Reload with header row
    if ext == ".csv":
        df = pd.read_csv(file_path, header=header_row_index, on_bad_lines="skip")
    elif ext == ".xls":
        df = pd.read_excel(file_path, header=header_row_index, engine="xlrd")
    else:
        df = pd.read_excel(file_path, header=header_row_index)

    # Clean columns
    df = df.dropna(axis=1, how="all")
    df = df.loc[:, ~df.columns.astype(str).str.contains("unnamed", case=False)]

    # Normalize wavelength column
    wl_col = next((c for c in df.columns if "wavelength" in str(c).lower()), None)
    if wl_col is None:
        raise ValueError("Wavelength column not found.")

    df.rename(columns={wl_col: "Wavelength"}, inplace=True)
    df = df[pd.to_numeric(df["Wavelength"], errors="coerce").notnull()]
    df["Wavelength"] = df["Wavelength"].astype(float)

    # Detect well columns (A1, B2, C3, …)
    wells = []
    for c in df.columns:
        s = str(c).strip()
        if len(s) >= 2 and s[0].isalpha() and s[1:].isdigit():
            wells.append(s)

    if not wells:
        raise ValueError("No valid well names detected.")

    return df, wells


# ----------------------------------------------------
# RAW MATRIX EXPORTER
# ----------------------------------------------------
def get_raw_matrix(file_path):
    df, wells = _load_plate_dataframe(file_path)
    return df[["Wavelength"] + wells].copy(), wells


# ----------------------------------------------------
# MAIN PLATE PROCESSOR
# ----------------------------------------------------
def process_plate(
    excel_file,
    reference_well=None,
    plate_type="96",
    illuminant_key="D65",
    observer_angle_deg=2.0,
    blank_wells=None,
    lab_target=None,
    reference_mode="lab",
):

    df, wells = _load_plate_dataframe(excel_file)

    # Keep RAW data (before blank subtraction)
    raw_df = df.copy()

    # Must have Lab target in LAB mode
    if lab_target is None and reference_mode == "lab":
        raise ValueError("lab_target must be provided when reference_mode='lab'.")

    # ---------------- BLANK SUBTRACTION ----------------
    valid_blanks = []
    if blank_wells:
        valid_blanks = [b for b in blank_wells if b in wells]
        if valid_blanks:
            blank_avg = df[valid_blanks].mean(axis=1)
            df[wells] = (df[wells].sub(blank_avg, axis=0)).clip(lower=0)

    # Reference fallback
    if reference_well not in wells:
        reference_well = wells[0]

    # ---------------- BUILD SPECTRAL SHAPE ----------------
    wavelengths = df["Wavelength"].values.astype(float)
    interval = wavelengths[1] - wavelengths[0]

    shape = colour.SpectralShape(wavelengths.min(), wavelengths.max(), interval)
    illum_sd = colour.SDS_ILLUMINANTS[illuminant_key].copy().align(shape)
    domain = illum_sd.domain

    # Observer whitepoint
    angle = float(observer_angle_deg)
    if angle in (0.0, 2.0, 5.0):
        observer = "CIE 1931 2 Degree Standard Observer"
    elif angle == 10.0:
        observer = "CIE 1964 10 Degree Standard Observer"
    else:
        raise ValueError("Unsupported observer angle.")

    whitepoint = colour.CCS_ILLUMINANTS[observer][illuminant_key]

    # Normalization factor (perfect transmittance under the same illuminant)
    ones_sd = colour.SpectralDistribution(np.ones_like(domain), domain)
    Y_max = float(colour.sd_to_XYZ(ones_sd, illuminant=illum_sd)[1])

    # ---------------- PREP RESULTS ----------------
    results = []

    # Reference Lab logic
    if reference_mode == "lab":
        ref_lab = np.array(lab_target)
        delta_col = "DeltaE_vs_Target"
    else:
        ref_lab = None
        delta_col = f"DeltaE_vs_{reference_well}"

    # =========================
    # PROCESS EACH WELL
    # =========================
    wl_raw = raw_df["Wavelength"].astype(float).values

    for w in wells:

        # -------- XYZ & Lab --------
        absorb = df[w].astype(float).values
        XYZ, Lab = compute_xyz_lab_from_absorbance(absorb, wavelengths, domain, illum_sd, whitepoint, Y_max)

        # -------- λmax using RAW absorbance --------
        abs_raw = raw_df[w].astype(float).values
        mask = ~np.isnan(abs_raw)

        wl = wl_raw[mask]
        absorb = abs_raw[mask]

        # Restrict λmax to visible region (AuNP color shift)
        vis_mask = (wl >= 400) & (wl <= 700)
        if np.any(vis_mask):
            wl_focus = wl[vis_mask]
            abs_focus = absorb[vis_mask]
        else:
            wl_focus = wl
            abs_focus = absorb

        if len(abs_focus) > 0:
            i_max = int(np.argmax(abs_focus))
            lambda_max = float(wl_focus[i_max])
        else:
            lambda_max = np.nan

        # -------- ΔE --------
        if reference_mode == "lab":
            delta_e = delta_e2000(ref_lab, Lab)
        else:
            if ref_lab is None:
                ref_absorb = df[reference_well].astype(float).values
                _, ref_Lab = compute_xyz_lab_from_absorbance(ref_absorb, wavelengths, domain, illum_sd, whitepoint, Y_max)
                ref_lab = ref_Lab
            delta_e = delta_e2000(ref_lab, Lab)

        # Append results
        results.append({
            "Well": w,
            "X": float(XYZ[0]),
            "Y": float(XYZ[1]),
            "Z": float(XYZ[2]),
            "L*": float(Lab[0]),
            "a*": float(Lab[1]),
            "b*": float(Lab[2]),
            delta_col: delta_e,
            "LambdaMax": lambda_max,
        })

    df_results = pd.DataFrame(results)
    return df_results, wells, reference_well, valid_blanks, delta_col


# ----------------------------------------------------
# SPECTRUM ACCESSORS
# ----------------------------------------------------
def get_well_spectrum(file_path, well):
    df, wells = _load_plate_dataframe(file_path)
    if well not in wells:
        raise ValueError(f"{well} not found.")
    return df["Wavelength"].tolist(), df[well].tolist()


def get_wells_spectra(file_path, wells):
    df, available = _load_plate_dataframe(file_path)
    spectra = {w: df[w].tolist() for w in wells if w in available}
    return df["Wavelength"].tolist(), spectra
