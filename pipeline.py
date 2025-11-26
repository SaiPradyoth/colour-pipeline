# pipeline.py
import pandas as pd
import numpy as np
import colour


def process_plate(excel_file, reference_well=None):
    """
    Run the full spectral→XYZ→Lab→ΔE pipeline on a plate .xlsx file.

    excel_file can be:
      - a file path (str)
      - a file-like object (e.g. from Flask upload)

    Returns: pandas DataFrame with columns:
      Well, X, Y, Z, L*, a*, b*, DeltaE_vs_<reference>
    """

    # -------------------------------------------------
    # STEP 1 — Load raw file WITHOUT assuming header
    # -------------------------------------------------
    raw = pd.read_excel(excel_file, header=None)

    # Detect the row that contains the real "Wavelength" header
    header_row_index = None
    for i in range(len(raw)):
        row = raw.iloc[i].astype(str).str.lower()
        if "wavelength" in row.values:
            header_row_index = i
            break

    if header_row_index is None:
        raise ValueError("Could not find a 'Wavelength' header row automatically.")

    # -------------------------------------------------
    # STEP 2 — Re-read using detected header row & clean
    # -------------------------------------------------
    df = pd.read_excel(excel_file, header=header_row_index)

    # Drop fully empty columns
    df = df.dropna(axis=1, how="all")

    # Drop "Unnamed" junk columns
    df = df.loc[:, ~df.columns.astype(str).str.contains("unnamed", case=False)]

    # Keep only rows where wavelength is numeric
    df = df[pd.to_numeric(df["Wavelength"], errors="coerce").notnull()]

    # Detect well columns
    available_wells = []
    for col in df.columns:
        col_str = str(col)
        if len(col_str) >= 2 and col_str[0].isalpha() and col_str[1:].isdigit():
            available_wells.append(col_str)

    if not available_wells:
        raise ValueError("No well columns detected in this file.")

    # Use first well as reference if none given
    if reference_well is None:
        reference_well = available_wells[0]
    if reference_well not in available_wells:
        raise ValueError(f"Reference well {reference_well} not found in data.")

    # -------------------------------------------------
    # STEP 3 — Prepare wavelength axis & illuminant D65
    # -------------------------------------------------
    wavelengths = df["Wavelength"].values.astype(float)
    interval = wavelengths[1] - wavelengths[0]

    shape = colour.SpectralShape(
        wavelengths.min(),
        wavelengths.max(),
        interval
    )

    illuminant_sd = colour.SDS_ILLUMINANTS["D65"].copy()
    illuminant_sd = illuminant_sd.align(shape)

    domain = np.arange(shape.start, shape.end + shape.interval, shape.interval)

    whitepoint_D65 = colour.CCS_ILLUMINANTS[
        "CIE 1931 2 Degree Standard Observer"
    ]["D65"]

    # Helper function for a single well
    def compute_xyz_lab_for_well(well_name: str):
        absorbance = df[well_name].values.astype(float)
        transmittance = 10 ** (-absorbance)

        sample_sd = colour.SpectralDistribution(
            data=illuminant_sd.values * transmittance,
            domain=domain
        )

        XYZ = colour.sd_to_XYZ(
            sample_sd,
            illuminant=illuminant_sd,
            method="Integration"
        )

        Lab = colour.XYZ_to_Lab(XYZ, whitepoint_D65)
        return XYZ, Lab

    # -------------------------------------------------
    # STEP 4 — Compute XYZ + Lab for all wells
    # -------------------------------------------------
    results = []
    lab_by_well = {}

    for well in available_wells:
        XYZ, Lab = compute_xyz_lab_for_well(well)
        lab_by_well[well] = Lab
        results.append({
            "Well": well,
            "X": XYZ[0],
            "Y": XYZ[1],
            "Z": XYZ[2],
            "L*": Lab[0],
            "a*": Lab[1],
            "b*": Lab[2],
        })

    # -------------------------------------------------
    # STEP 5 — Compute ΔE vs reference well
    # -------------------------------------------------
    ref_Lab = lab_by_well[reference_well]
    delta_col_name = f"DeltaE_vs_{reference_well}"

    for row in results:
        well = row["Well"]
        Lab = lab_by_well[well]
        deltaE = colour.delta_E(ref_Lab, Lab)
        row[delta_col_name] = float(deltaE)

    df_results = pd.DataFrame(results)
    return df_results
