# pipeline.py
import pandas as pd
import numpy as np
import colour


def process_plate(excel_file, reference_well=None):
    """
    Full spectral → XYZ → Lab → ΔE pipeline for 96-well plates.

    Returns:
        df_results        = DataFrame with color metrics
        available_wells   = list of actual detected well IDs
        reference_well    = the reference well used for ΔE
    """

    # -------------------------------------------------
    # STEP 1 — Load raw file WITHOUT assuming header
    # -------------------------------------------------
    raw = pd.read_excel(excel_file, header=None)

    # Detect the row that contains “Wavelength”
    header_row_index = None
    for i in range(len(raw)):
        row = raw.iloc[i].astype(str).str.lower()
        if "wavelength" in row.values:
            header_row_index = i
            break

    if header_row_index is None:
        raise ValueError("Could not find a 'Wavelength' header row automatically.")

    # -------------------------------------------------
    # STEP 2 — Clean the file using the detected header
    # -------------------------------------------------
    df = pd.read_excel(excel_file, header=header_row_index)

    df = df.dropna(axis=1, how="all")  # remove empty columns
    df = df.loc[:, ~df.columns.astype(str).str.contains("unnamed", case=False)]

    df = df[pd.to_numeric(df["Wavelength"], errors="coerce").notnull()]

    # -------------------------------------------------
    # STEP 3 — Detect actual well columns
    # -------------------------------------------------
    available_wells = []

    for col in df.columns:
        name = str(col)
        if len(name) >= 2 and name[0].isalpha() and name[1:].isdigit():
            available_wells.append(name)

    if not available_wells:
        raise ValueError("No well columns detected in this file.")

    # Decide reference well
    if reference_well is None:
        # Prefer A10 if available
        reference_well = "A10" if "A10" in available_wells else available_wells[0]
    else:
        if reference_well not in available_wells:
            raise ValueError(f"Reference well {reference_well} not in dataset.")

    # -------------------------------------------------
    # STEP 4 — Prepare illuminant + spectral shape
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

    # Helper to compute color for each well
    def compute_xyz_lab_for_well(well_name):
        absorbance = df[well_name].values.astype(float)
        transmittance = 10 ** (-absorbance)

        sample_sd = colour.SpectralDistribution(
            data=illuminant_sd.values * transmittance, domain=domain
        )

        XYZ = colour.sd_to_XYZ(sample_sd, illuminant=illuminant_sd)
        Lab = colour.XYZ_to_Lab(XYZ, whitepoint_D65)
        return XYZ, Lab

    # -------------------------------------------------
    # STEP 5 — Compute colors for all wells
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
    # STEP 6 — Compute ΔE vs reference
    # -------------------------------------------------
    ref_Lab = lab_by_well[reference_well]
    delta_col = f"DeltaE_vs_{reference_well}"

    for row in results:
        Lab = lab_by_well[row["Well"]]
        row[delta_col] = float(colour.delta_E(ref_Lab, Lab))

    df_results = pd.DataFrame(results)

    # -------------------------------------------------
    # RETURN 3 things:
    # -------------------------------------------------
    return df_results, available_wells, reference_well
