# ================================
# pipeline.py
# Core spectral → XYZ → Lab → ΔE2000 logic
# Now with Universal Loader (xls, xlsx, csv)
# ================================

import pandas as pd
import numpy as np
import colour
import os

# --------------------------------
# Internal loader to normalize plate Data (Universal Loader)
# --------------------------------
def _load_plate_dataframe(file_path):
    """
    Robust loader that handles .xlsx, .xls (SpectraMax), and .csv.
    It scans the file to find the row starting with 'Wavelength'.
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    # 1. Read the raw file based on extension to find the structure
    # We read without a header first to scan the rows.
    try:
        if ext == '.csv':
            # Handle CSVs (often exported from Excel)
            raw = pd.read_csv(file_path, header=None, on_bad_lines='skip')
        elif ext == '.xls':
            # Legacy Excel 97-2003 (requires xlrd installed)
            raw = pd.read_excel(file_path, header=None, engine='xlrd')
        else:
            # Standard .xlsx
            raw = pd.read_excel(file_path, header=None)
    except Exception as e:
        raise ValueError(f"Could not read file format {ext}. Error: {e}")

    # 2. Hunt for the Header Row
    # We look for the row that contains the word "Wavelength" (case-insensitive)
    header_row_index = None
    
    # Limit scan to first 50 rows to be efficient
    scan_limit = min(len(raw), 50)
    
    for i in range(scan_limit):
        # Convert row to string, lowercase, and check for 'wavelength'
        # We join the row values to ensure we catch it in any column
        row_str = " ".join(raw.iloc[i].astype(str).values).lower()
        
        if "wavelength" in row_str:
            header_row_index = i
            break
    
    if header_row_index is None:
        raise ValueError("Could not find a 'Wavelength' header row in the file. Ensure the file has a 'Wavelength' column.")

    # 3. Reload with the correct header
    if ext == '.csv':
        df = pd.read_csv(file_path, header=header_row_index, on_bad_lines='skip')
    elif ext == '.xls':
        df = pd.read_excel(file_path, header=header_row_index, engine='xlrd')
    else:
        df = pd.read_excel(file_path, header=header_row_index)

    # 4. Clean Data
    # Drop columns that are entirely empty (NaN)
    df = df.dropna(axis=1, how="all")
    
    # Remove columns that are automatically named "Unnamed" by pandas (garbage columns)
    df = df.loc[:, ~df.columns.astype(str).str.contains("unnamed", case=False)]
    
    # Ensure "Wavelength" column exists and clean it
    # (Sometimes headers have spaces like "Wavelength (nm)")
    cols = list(df.columns)
    wavelength_col = next((c for c in cols if "wavelength" in str(c).lower()), None)
    
    if not wavelength_col:
        raise ValueError("Header found, but specific 'Wavelength' column is missing.")
    
    # Rename it strictly to "Wavelength" for internal logic
    df.rename(columns={wavelength_col: "Wavelength"}, inplace=True)

    # Drop rows where Wavelength is not a number (removes metadata footers)
    df = df[pd.to_numeric(df["Wavelength"], errors="coerce").notnull()]
    df["Wavelength"] = df["Wavelength"].astype(float)

    # 5. Detect well columns (A1, B2, etc.)
    available_wells = []
    for col in df.columns:
        name = str(col).strip()
        # Regex-like check: Starts with Letter, ends with Number (e.g., A1, H12)
        # We ignore "Wavelength", "Temperature", etc.
        if len(name) >= 2 and name[0].isalpha() and name[1:].isdigit():
            available_wells.append(name)

    if not available_wells:
        raise ValueError("No valid well columns (A1, B12...) detected.")

    return df, available_wells


# --------------------------------
# Public helper: get raw matrix (for Scientist Mode / downloads)
# --------------------------------
def get_raw_matrix(file_path):
    """
    Return (df_raw, available_wells) after normalization.

    df_raw has:
      - 'Wavelength' column
      - one column per well in available_wells
    """
    df, available_wells = _load_plate_dataframe(file_path)
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
    """

    # ---- Load & normalize data ----
    df, available_wells = _load_plate_dataframe(excel_file)

    # ---- Basic plate-type sanity check ----
    if str(plate_type) not in {"48", "96", "384"}:
        raise ValueError(f"Unsupported plate type: {plate_type}")

    # ---- Reference well selection ----
    if reference_well is None:
        # Default to A10 if present, else A1, else first available
        if "A10" in available_wells:
            reference_well = "A10"
        elif "A1" in available_wells:
            reference_well = "A1"
        else:
            reference_well = available_wells[0]
            
    elif reference_well not in available_wells:
        # Fallback if selected reference is missing in this specific file
        reference_well = available_wells[0]

    # ---- Build spectral shape from file wavelengths ----
    wavelengths = df["Wavelength"].values.astype(float)
    if len(wavelengths) < 2:
        raise ValueError("Not enough wavelength samples in file.")

    interval = float(wavelengths[1] - wavelengths[0])
    
    # Handle non-uniform intervals slightly gracefully (warn-ish) by taking average
    # But for colour-science, we usually need uniform. 
    # If the file is messy, this might crash, but SpectraMax is usually uniform.
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
        # Handle potential negatives (noise) or super high values
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
def get_well_spectrum(file_path, well_name):
    """
    Return raw absorbance spectrum for a single well.
    """
    df, available_wells = _load_plate_dataframe(file_path)

    if well_name not in available_wells:
        raise ValueError(f"Well {well_name} not present in dataset.")

    wavelengths = df["Wavelength"].values.astype(float)
    absorbance = df[well_name].values.astype(float)

    return wavelengths.tolist(), absorbance.tolist()


# --------------------------------
# Multi-well spectrum extractor (for overlays)
# --------------------------------
def get_wells_spectra(file_path, wells):
    """
    Efficiently return spectra for multiple wells from a single file read.
    """
    df, available_wells = _load_plate_dataframe(file_path)
    available_set = set(available_wells)

    target_wells = [w for w in wells if w in available_set]
    if not target_wells:
        raise ValueError("None of the requested wells are present in the dataset.")

    wavelengths = df["Wavelength"].values.astype(float)
    spectra = {}
    for w in target_wells:
        spectra[w] = df[w].values.astype(float).tolist()

    return wavelengths.tolist(), spectra