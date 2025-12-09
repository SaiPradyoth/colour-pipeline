# ================================
# pipeline.py
# Spectral → XYZ → Lab → ΔE2000 Pipeline
# Supports: Fixed Lab Target OR Reference Well
# ================================

import pandas as pd
import numpy as np
import colour
import os

# --------------------------------
# Internal loader (normalizes any input: xlsx, xls, csv)
# --------------------------------
def _load_plate_dataframe(file_path):
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".csv":
            raw = pd.read_csv(file_path, header=None, on_bad_lines="skip")
        elif ext == ".xls":
            raw = pd.read_excel(file_path, header=None, engine="xlrd")
        else:
            raw = pd.read_excel(file_path, header=None)
    except Exception as e:
        raise ValueError(f"Could not read file: {e}")

    # Find header row with "Wavelength"
    header_row_index = None
    for i in range(min(50, len(raw))):
        row_str = " ".join(raw.iloc[i].astype(str).values).lower()
        if "wavelength" in row_str:
            header_row_index = i
            break

    if header_row_index is None:
        raise ValueError("No 'Wavelength' header found.")

    if ext == ".csv":
        df = pd.read_csv(file_path, header=header_row_index, on_bad_lines="skip")
    elif ext == ".xls":
        df = pd.read_excel(file_path, header=header_row_index, engine="xlrd")
    else:
        df = pd.read_excel(file_path, header=header_row_index)

    df = df.dropna(axis=1, how="all")
    df = df.loc[:, ~df.columns.astype(str).str.contains("unnamed", case=False)]

    wavelength_col = next((c for c in df.columns if "wavelength" in str(c).lower()), None)
    if not wavelength_col:
        raise ValueError("Wavelength column not found.")

    df.rename(columns={wavelength_col: "Wavelength"}, inplace=True)
    df = df[pd.to_numeric(df["Wavelength"], errors="coerce").notnull()]
    df["Wavelength"] = df["Wavelength"].astype(float)

    # Detect wells
    available_wells = []
    for col in df.columns:
        name = str(col).strip()
        if len(name) >= 2 and name[0].isalpha() and name[1:].isdigit():
            available_wells.append(name)

    if not available_wells:
        raise ValueError("No valid well names detected.")

    return df, available_wells


# --------------------------------
# Scientist mode: raw matrix
# --------------------------------
def get_raw_matrix(file_path):
    df, wells = _load_plate_dataframe(file_path)
    return df[["Wavelength"] + wells].copy(), wells


# --------------------------------
# MAIN PIPELINE
# --------------------------------
def process_plate(
    excel_file,
    reference_well=None,
    plate_type="96",
    illuminant_key="D65",
    observer_angle_deg=2.0,
    blank_wells=None,
    lab_target=None,
    reference_mode="lab"
):

    df, available_wells = _load_plate_dataframe(excel_file)

    if str(plate_type) not in {"48", "96", "384"}:
        raise ValueError("Invalid plate type.")

    if lab_target is None and reference_mode == "lab":
        raise ValueError("lab_target must be provided when reference_mode='lab'.")

    # ---- BLANK SUBTRACTION ----
    valid_blanks = []
    if blank_wells:
        valid_blanks = [w for w in blank_wells if w in available_wells]
        if valid_blanks:
            blank_avg = df[valid_blanks].mean(axis=1)
            for w in available_wells:
                df[w] = (df[w] - blank_avg).clip(lower=0)

    # ---- Fallback reference well ----
    if reference_well is None or reference_well not in available_wells:
        reference_well = available_wells[0]

    # ---- Build spectral domain ----
    wavelengths = df["Wavelength"].values.astype(float)
    interval = wavelengths[1] - wavelengths[0]

    shape = colour.SpectralShape(wavelengths.min(), wavelengths.max(), interval)
    illuminant_sd = colour.SDS_ILLUMINANTS[illuminant_key].copy().align(shape)
    domain = illuminant_sd.domain

    # ---- Observer whitepoint ----
    angle = float(observer_angle_deg)
    if angle in (0.0, 2.0, 5.0):
        observer_name = "CIE 1931 2 Degree Standard Observer"
    elif angle == 10.0:
        observer_name = "CIE 1964 10 Degree Standard Observer"
    else:
        raise ValueError("Unsupported observer angle.")

    whitepoint = colour.CCS_ILLUMINANTS[observer_name][illuminant_key]

    # ---- Compute Y_max using perfect transmittance ----
    perfect_trans = np.ones_like(domain, float)
    perfect_sd = colour.SpectralDistribution(perfect_trans, domain)
    XYZ_white = colour.sd_to_XYZ(perfect_sd, illuminant=illuminant_sd)
    Y_max = max(float(XYZ_white[1]), 1e-8)

    # ---- Single-well computation helper ----
    def compute_xyz_lab(well):
        absorb = df[well].astype(float).values
        trans = 10 ** (-absorb)

        # Interpolate if needed
        if not np.allclose(wavelengths, domain):
            trans = np.interp(domain, wavelengths, trans)

        sample_sd = colour.SpectralDistribution(trans, domain)
        XYZ_raw = colour.sd_to_XYZ(sample_sd, illuminant=illuminant_sd)
        XYZ_norm = XYZ_raw / Y_max
        Lab = colour.XYZ_to_Lab(XYZ_norm, whitepoint)
        XYZ_display = XYZ_norm * 100
        return XYZ_display, Lab

    # ---- Prepare table ----
    results = []

    # Reference logic
    if reference_mode == "lab":
        ref_lab = np.array(lab_target)
        delta_col = "DeltaE_vs_Target"
    else:
        ref_lab = None
        delta_col = f"DeltaE_vs_{reference_well}"

    # ---- Process all wells ----
    for w in available_wells:
        XYZ, Lab = compute_xyz_lab(w)

        if reference_mode == "lab":
            delta_e = float(colour.delta_E(ref_lab, Lab, method="CIE 2000"))
        else:
            if ref_lab is None:
                _, ref_Lab = compute_xyz_lab(reference_well)
                ref_lab = ref_Lab
            delta_e = float(colour.delta_E(ref_lab, Lab, method="CIE 2000"))

        results.append({
            "Well": w,
            "X": float(XYZ[0]),
            "Y": float(XYZ[1]),
            "Z": float(XYZ[2]),
            "L*": float(Lab[0]),
            "a*": float(Lab[1]),
            "b*": float(Lab[2]),
            delta_col: delta_e
        })

    return pd.DataFrame(results), available_wells, reference_well, valid_blanks, delta_col


# --------------------------------
# Spectrum accessors
# --------------------------------
def get_well_spectrum(file_path, well):
    df, wells = _load_plate_dataframe(file_path)
    if well not in wells:
        raise ValueError(f"{well} not found.")
    return df["Wavelength"].tolist(), df[well].tolist()


def get_wells_spectra(file_path, wells):
    df, available = _load_plate_dataframe(file_path)
    spectra = {w: df[w].tolist() for w in wells if w in available}
    return df["Wavelength"].tolist(), spectra
