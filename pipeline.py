# ================================
# pipeline.py
# Core spectral -> XYZ -> Lab -> DeltaE2000 logic
# Now with Universal Loader (xls, xlsx, csv)
# UPDATED: Fixed L* scaling bug (0-100 normalization)
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
# Main color pipeline (DeltaE2000 only)
# --------------------------------
def process_plate(
    excel_file,
    reference_well=None,
    plate_type="96",
    illuminant_key="D65",
    observer_angle_deg=2.0,
    blank_wells=None,
    lab_target=None, # <--- NEW ARGUMENT: Fixed L*a*b* target for Delta E
):
    """
    Full spectral -> XYZ -> Lab -> DeltaE2000 pipeline.
    Includes Baseline Correction (Blanking) and Fixed Reference Target.
    """

    # ---- Load & normalize data ----
    df, available_wells = _load_plate_dataframe(excel_file)

    # ---- Basic plate-type sanity check ----
    if str(plate_type) not in {"48", "96", "384"}:
        raise ValueError(f"Unsupported plate type: {plate_type}")
        
    if lab_target is None:
        # CRITICAL: Ensures a target is always set from app.py
        raise ValueError("L*a*b* Target (lab_target) must be provided.")

    # ---- 1. BASELINE CORRECTION (BLANKING) LOGIC ----
    # If blanks are provided, calculate average and subtract from all wells
    valid_blanks = []
    if blank_wells:
        # Filter to ensure user didn't type a non-existent well
        valid_blanks = [w for w in blank_wells if w in available_wells]
        
        if valid_blanks:
            # Calculate the average spectrum of the blank wells
            # axis=1 means we average across the columns (wells) for each wavelength row
            avg_blank_spectrum = df[valid_blanks].mean(axis=1)

            # Subtract this average from ALL available wells
            for well in available_wells:
                df[well] = df[well] - avg_blank_spectrum
            
            # Clip negative absorbance to 0 (Physically, T cannot be > 100%)
            num_cols = df[available_wells].select_dtypes(include=[np.number]).columns
            df[num_cols] = df[num_cols].clip(lower=0)
            
    # ---- Reference well determination (now only for naming the Delta E column) ----
    if reference_well is None:
        if "A10" in available_wells: reference_well = "A10"
        elif "A1" in available_wells: reference_well = "A1"
        else: reference_well = available_wells[0]     
    elif reference_well not in available_wells:
        reference_well = available_wells[0]

    # ---- Build spectral shape from file wavelengths ----
    wavelengths = df["Wavelength"].values.astype(float)
    if len(wavelengths) < 2:
        raise ValueError("Not enough wavelength samples in file.")

    interval = float(wavelengths[1] - wavelengths[0])
    
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

    illuminant_sd = illuminant_sd.align(shape)
    domain = illuminant_sd.domain

    # ---- Observer angle ----
    angle = float(observer_angle_deg)
    if angle in (0.0, 2.0, 5.0):
        observer_label = "CIE 1931 2 Degree Standard Observer"
    elif angle == 10.0:
        observer_label = "CIE 1964 10 Degree Standard Observer"
    else:
        raise ValueError(f"Unsupported observer angle: {angle}deg")

    try:
        whitepoint = colour.CCS_ILLUMINANTS[observer_label][illuminant_key]
    except KeyError:
        raise ValueError(f"No whitepoint defined for observer '{observer_label}'")

    # ---- Normalization Factor (Fixes L* scale) ----
    perfect_white_sd = illuminant_sd.copy()
    perfect_white_sd.values = illuminant_sd.values * 1.0 
    XYZ_perfect = colour.sd_to_XYZ(perfect_white_sd, illuminant=illuminant_sd)
    Y_max = XYZ_perfect[1] 

    # ---- Helper: compute XYZ / Lab for a single well ----
    def compute_xyz_lab_for_well(well_name: str):
        absorbance = df[well_name].values.astype(float)
        
        # Transmittance T = 10^(-A)
        transmittance = 10 ** (-absorbance)

        # Interpolation
        if len(transmittance) != len(domain) or not np.allclose(wavelengths, domain):
            trans_interp = np.interp(domain, wavelengths, transmittance)
        else:
            trans_interp = transmittance

        # Spectral Distribution
        sample_sd = colour.SpectralDistribution(
            data=illuminant_sd.values * trans_interp,
            domain=domain,
        )

        # 1. Get Raw XYZ
        XYZ_raw = colour.sd_to_XYZ(sample_sd, illuminant=illuminant_sd)
        
        # 2. Normalize XYZ to 0-1 scale (Critical fix for correct Lab conversion)
        # Previous bug: multiplying by 100 here caused L* to go > 100
        XYZ_0_1 = XYZ_raw / Y_max 

        # 3. Convert to Lab (Library expects 0-1 input)
        Lab = colour.XYZ_to_Lab(XYZ_0_1, whitepoint)

        # 4. Scale XYZ up to 0-100 just for display/CSV readability
        XYZ_display = XYZ_0_1 * 100.0

        return XYZ_display, Lab

    # ---- Compute colors for all wells ----
    results = []

    # The fixed L*a*b* target is now the reference point
    ref_Lab_fixed = np.array(lab_target) 
    
    # We name the column based on the target selected
    delta_col = f"DeltaE_vs_Target"

    for well in available_wells:
        XYZ, Lab = compute_xyz_lab_for_well(well)
        
        # Delta E is always calculated against the FIXED user-defined target
        delta_e = float(colour.delta_E(ref_Lab_fixed, Lab, method="CIE 2000"))
        
        results.append({
            "Well": well,
            "X": float(XYZ[0]), "Y": float(XYZ[1]), "Z": float(XYZ[2]),
            "L*": float(Lab[0]), "a*": float(Lab[1]), "b*": float(Lab[2]),
            delta_col: delta_e, 
        })

    df_results = pd.DataFrame(results)
    
    return df_results, available_wells, reference_well, valid_blanks

# Fixed L*a*b* Presets for Reference Point (Delta E = 0)
LAB_PRESETS = {
    "Buffer": (100.0, 0.0, 0.0),      # Perfect White/Clear (L*=100, a*=0, b*=0)
    "WhiteTile": (95.0, -1.0, 1.0),   # Typical slightly bluish commercial white reference tile
    "Black": (0.0, 0.0, 0.0),         # Perfect Black
}
# =====================================================
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