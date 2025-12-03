# ================================
# pipeline.py
# Core spectral → XYZ → Lab → ΔE2000 logic
# ================================

import pandas as pd
import numpy as np
import colour


# --------------------------------
# Internal loader to normalize plate Excel files
# --------------------------------
def _load_plate_dataframe(excel_file):
    """
    Load an Excel export and normalize it into:

      - Column "Wavelength"  (numeric)
      - One column per well  (A1, B3, etc.)

    We autodetect the row containing "Wavelength" and use it as header.
    This makes the pipeline robust to different spectrometer export formats.
    """
    # Load without header so we can scan for the wavelength row
    raw = pd.read_excel(excel_file, header=None)

    header_row_index = None
    for i in range(len(raw)):
        row = raw.iloc[i].astype(str).str.lower()
        if "wavelength" in row.values:
            header_row_index = i
            break

    if header_row_index is None:
        raise ValueError("Could not find a 'Wavelength' header row automatically.")

    # Re-read with the detected header row
    df = pd.read_excel(excel_file, header=header_row_index)

    # Drop truly empty or unnamed columns
    df = df.dropna(axis=1, how="all")
    df = df.loc[:, ~df.columns.astype(str).str.contains("unnamed", case=False)]

    # Keep only rows where wavelength parses as a number
    df = df[pd.to_numeric(df["Wavelength"], errors="coerce").notnull()]

    # Detect well-like columns: letter+digits (A1, B10, etc.)
    available_wells = []
    for col in df.columns:
        name = str(col).strip()
        if len(name) >= 2 and name[0].isalpha() and name[1:].isdigit():
            available_wells.append(name)

    if not available_wells:
        raise ValueError("No well columns detected in this file.")

    return df, available_wells


# --------------------------------
# Public helper: get raw matrix (for Scientist Mode / downloads)
# --------------------------------
def get_raw_matrix(excel_file):
    """
    Return (df_raw, available_wells) after normalization.

    df_raw has:
      - 'Wavelength' column
      - one column per well in available_wells
    """
    df, available_wells = _load_plate_dataframe(excel_file)
    cols = ["Wavelength"] + available_wells
    df_raw = df[cols].copy()
    return df_raw, available_wells


# --------------------------------
# Main color pipeline (ΔE2000 only)
# --------------------------------
def process_plate(
    excel_file,
    reference_well=None,
    plate_type="96",
    illuminant_key="D65",
    observer_angle_deg=2.0,
):
    """
    Full spectral → XYZ → Lab → ΔE2000 pipeline.

    Args:
        excel_file:
            Path to Excel file.

        reference_well:
            Well ID for ΔE reference (if None, choose A10 or first well).

        plate_type:
            "48", "96", or "384" (currently used only for validation).

        illuminant_key:
            Key into colour.SDS_ILLUMINANTS, e.g. "D65", "D50", "A", "F2", "E".

        observer_angle_deg:
            Requested observer angle (0, 2, 5, or 10) in degrees.
            Internally:
              - 0 / 2 / 5  → CIE 1931 2° observer
              - 10         → CIE 1964 10° observer

    Returns:
        df_results:
            DataFrame with XYZ, Lab, and ΔE2000 columns.

        available_wells:
            List of well IDs actually present.

        reference_well:
            Reference well ultimately used for ΔE.
    """

    # ---- Load & normalize data ----
    df, available_wells = _load_plate_dataframe(excel_file)

    # ---- Basic plate-type sanity check ----
    if str(plate_type) not in {"48", "96", "384"}:
        raise ValueError(f"Unsupported plate type: {plate_type}")

    # ---- Reference well selection ----
    if reference_well is None:
        reference_well = "A10" if "A10" in available_wells else available_wells[0]
    elif reference_well not in available_wells:
        raise ValueError(f"Reference well {reference_well} not in dataset.")

    # ---- Build spectral shape from file wavelengths ----
    wavelengths = df["Wavelength"].values.astype(float)
    if len(wavelengths) < 2:
        raise ValueError("Not enough wavelength samples in file.")

    interval = float(wavelengths[1] - wavelengths[0])

    # Use the file's wavelength range as the spectral shape.
    shape = colour.SpectralShape(
        wavelengths.min(),
        wavelengths.max(),
        interval,
    )

    # ---- Illuminant selection & alignment ----
    try:
        illuminant_sd = colour.SDS_ILLUMINANTS[illuminant_key].copy()
    except KeyError:
        raise ValueError(f"Unsupported illuminant key: {illuminant_key}")

    # Align illuminant to our shape
    illuminant_sd = illuminant_sd.align(shape)

    # We'll use the illuminant's domain for integration
    domain = illuminant_sd.domain

    # ---- Observer angle → which CIE observer table to use ----
    angle = float(observer_angle_deg)
    if angle in (0.0, 2.0, 5.0):
        observer_label = "CIE 1931 2 Degree Standard Observer"
    elif angle == 10.0:
        observer_label = "CIE 1964 10 Degree Standard Observer"
    else:
        raise ValueError(
            f"Unsupported observer angle: {angle}°. Use 0, 2, 5, or 10 degrees."
        )

    try:
        whitepoint = colour.CCS_ILLUMINANTS[observer_label][illuminant_key]
    except KeyError:
        raise ValueError(
            f"No whitepoint defined for observer '{observer_label}' and "
            f"illuminant '{illuminant_key}'."
        )

    # ---- Helper: compute XYZ / Lab for a single well ----
    def compute_xyz_lab_for_well(well_name: str):
        absorbance = df[well_name].values.astype(float)
        # Convert absorbance to transmittance: T = 10^(-A)
        transmittance = 10 ** (-absorbance)

        # Interpolate transmittance onto the illuminant domain if needed
        if len(transmittance) != len(domain) or not np.allclose(
            wavelengths, domain
        ):
            # simple linear interpolation
            trans_interp = np.interp(domain, wavelengths, transmittance)
        else:
            trans_interp = transmittance

        # Build sample spectral distribution under the illuminant
        sample_sd = colour.SpectralDistribution(
            data=illuminant_sd.values * trans_interp,
            domain=domain,
        )

        XYZ = colour.sd_to_XYZ(sample_sd, illuminant=illuminant_sd)
        Lab = colour.XYZ_to_Lab(XYZ, whitepoint)

        return XYZ, Lab

    # ---- Compute colors for all wells ----
    results = []
    lab_by_well = {}

    for well in available_wells:
        XYZ, Lab = compute_xyz_lab_for_well(well)
        lab_by_well[well] = Lab

        row = {
            "Well": well,
            "X": float(XYZ[0]),
            "Y": float(XYZ[1]),
            "Z": float(XYZ[2]),
            "L*": float(Lab[0]),
            "a*": float(Lab[1]),
            "b*": float(Lab[2]),
        }

        results.append(row)

    # ---- Compute ΔE2000 vs reference well ----
    ref_Lab = lab_by_well[reference_well]
    delta_col = f"DeltaE_vs_{reference_well}"  # always ΔE2000 underneath

    for row in results:
        Lab = lab_by_well[row["Well"]]
        row[delta_col] = float(colour.delta_E(ref_Lab, Lab, method="CIE 2000"))

    df_results = pd.DataFrame(results)
    return df_results, available_wells, reference_well


# --------------------------------
# Per-well spectrum extractor (single)
# --------------------------------
def get_well_spectrum(excel_file, well_name):
    """
    Return raw absorbance spectrum for a single well.

    Output:
        wavelengths: list[float]
        absorbance: list[float]
    """
    df, available_wells = _load_plate_dataframe(excel_file)

    if well_name not in available_wells:
        raise ValueError(f"Well {well_name} not present in dataset.")

    wavelengths = df["Wavelength"].values.astype(float)
    absorbance = df[well_name].values.astype(float)

    return wavelengths.tolist(), absorbance.tolist()


# --------------------------------
# Multi-well spectrum extractor (for overlays)
# --------------------------------
def get_wells_spectra(excel_file, wells):
    """
    Efficiently return spectra for multiple wells from a single file read.

    Args:
        excel_file:
            Path to Excel export.

        wells:
            Iterable of well IDs (strings).

    Returns:
        wavelengths:
            list[float] wavelength axis, shared across wells.

        spectra:
            dict[well_id] -> list[float] absorbance values.
            Only wells actually present in the file are returned.
    """
    df, available_wells = _load_plate_dataframe(excel_file)
    available_set = set(available_wells)

    target_wells = [w for w in wells if w in available_set]
    if not target_wells:
        raise ValueError("None of the requested wells are present in the dataset.")

    wavelengths = df["Wavelength"].values.astype(float)
    spectra = {}
    for w in target_wells:
        spectra[w] = df[w].values.astype(float).tolist()

    return wavelengths.tolist(), spectra
