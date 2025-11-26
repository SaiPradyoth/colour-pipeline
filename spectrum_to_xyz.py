import pandas as pd
import numpy as np
import colour

# =========================================================
# CONFIG
# =========================================================
EXCEL_PATH = "shrimp-10-10-25.xlsx"   # your plate file
REFERENCE_WELL = None                 # set to None = first well will be used


# =========================================================
# STEP 1 — Load raw file WITHOUT assuming header
# =========================================================
raw = pd.read_excel(EXCEL_PATH, header=None)

# Detect the row that contains the real "Wavelength" header
header_row_index = None
for i in range(len(raw)):
    row = raw.iloc[i].astype(str).str.lower()
    if "wavelength" in row.values:
        header_row_index = i
        break

if header_row_index is None:
    raise ValueError("Could not find a 'Wavelength' header row automatically.")

print(f"Detected header row at index {header_row_index}")

# =========================================================
# STEP 2 — Re-read using detected header row & clean columns
# =========================================================
df = pd.read_excel(EXCEL_PATH, header=header_row_index)

# Drop fully empty columns
df = df.dropna(axis=1, how="all")

# Drop "Unnamed" junk columns
df = df.loc[:, ~df.columns.astype(str).str.contains("unnamed", case=False)]

# Keep only rows where wavelength is numeric
df = df[pd.to_numeric(df["Wavelength"], errors="coerce").notnull()]

print("\nCleaned Data Preview:")
print(df.head())
print(f"\n[rows x cols] = {df.shape}")

print("\nColumn Names:")
print(df.columns.tolist())

# =========================================================
# STEP 3 — Detect valid wells (A10, B1, C3, etc.)
# =========================================================
available_wells = []
for col in df.columns:
    col_str = str(col)
    # Well pattern: first char letter, remaining chars digits
    if len(col_str) >= 2 and col_str[0].isalpha() and col_str[1:].isdigit():
        available_wells.append(col_str)

if not available_wells:
    raise ValueError("No well columns detected!")

print("\nAvailable wells:")
print(available_wells)

# Decide reference well
if REFERENCE_WELL is None:
    REFERENCE_WELL = available_wells[0]
print(f"\nReference well for ΔE: {REFERENCE_WELL}")

# =========================================================
# STEP 4 — Prepare wavelength axis & illuminant D65
# =========================================================
wavelengths = df["Wavelength"].values.astype(float)

# Build spectral shape from wavelength grid
interval = wavelengths[1] - wavelengths[0]
shape = colour.SpectralShape(
    wavelengths.min(),
    wavelengths.max(),
    interval
)

# Load and align D65 illuminant
illuminant_sd = colour.SDS_ILLUMINANTS["D65"].copy()
illuminant_sd = illuminant_sd.align(shape)

# Domain (should match the wavelengths)
domain = np.arange(shape.start, shape.end + shape.interval, shape.interval)

# CIE 1931 2° D65 white point for Lab conversion
whitepoint_D65 = colour.CCS_ILLUMINANTS[
    "CIE 1931 2 Degree Standard Observer"
]["D65"]

# =========================================================
# STEP 5 — Helper: compute XYZ + Lab for a single well
# =========================================================
def compute_xyz_lab_for_well(well_name: str):
    """Given a well name (e.g. 'A10'), return (XYZ, Lab)."""
    absorbance = df[well_name].values.astype(float)

    # Absorbance -> transmittance
    transmittance = 10 ** (-absorbance)

    # Sample spectrum under D65: S(λ) = T(λ) * D65(λ)
    sample_sd = colour.SpectralDistribution(
        data=illuminant_sd.values * transmittance,
        domain=domain
    )

    # Spectrum -> XYZ
    XYZ = colour.sd_to_XYZ(
        sample_sd,
        illuminant=illuminant_sd,
        method="Integration"
    )

    # XYZ -> Lab
    Lab = colour.XYZ_to_Lab(XYZ, whitepoint_D65)

    return XYZ, Lab


# =========================================================
# STEP 6 — Compute XYZ + Lab for ALL wells
# =========================================================
results = []
lab_by_well = {}

print("\nComputing XYZ + Lab for all wells...")

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

print(f"Done. Processed {len(results)} wells.")

# =========================================================
# STEP 7 — Compute ΔE vs reference well for all wells
# =========================================================
print(f"\nComputing ΔE vs reference well {REFERENCE_WELL}...")

ref_Lab = lab_by_well[REFERENCE_WELL]

for row in results:
    well = row["Well"]
    Lab = lab_by_well[well]
    deltaE = colour.delta_E(ref_Lab, Lab)
    row[f"DeltaE_vs_{REFERENCE_WELL}"] = float(deltaE)

print("ΔE computation complete.")

# =========================================================
# STEP 8 — Save results to CSV
# =========================================================
df_results = pd.DataFrame(results)
output_name = "well_colors.csv"
df_results.to_csv(output_name, index=False)

print(f"\nSaved results to {output_name}")
print("\nPreview of results:")
print(df_results.head())
