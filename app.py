# ================================
# app.py
# Flask front-end for Spectral -> Color -> DeltaE Analyzer
# With support for: Fixed Lab Target OR Reference Well
# ================================

import os
import uuid
import base64
import pandas as pd
import numpy as np
from flask import Flask, render_template, request, send_file, jsonify

from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

# Import pipeline
from pipeline import (
    process_plate,
    get_well_spectrum,
    get_wells_spectra,
    get_raw_matrix,
)

app = Flask(__name__)

# -------- JINJA FILTER: base64 encode (for table_html -> hidden input) --------
@app.template_filter("b64encode")
def b64encode_filter(s):
    if s is None:
        return ""
    return base64.b64encode(s.encode("utf-8")).decode("utf-8")

# Allow uploads up to 50 MB
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

# Ensure runtime folders exist
os.makedirs("uploads", exist_ok=True)
os.makedirs("results", exist_ok=True)

# Default L*a*b* presets
LAB_PRESETS = {
    "Buffer": (100.0, 0.0, 0.0),
    "WhiteTile": (95.0, -1.0, 1.0),
    "Black": (0.0, 0.0, 0.0),
}

# --------------------------------
# Helpers
# --------------------------------
def make_token():
    return uuid.uuid4().hex


def normalize_plate_type(plate_type: str) -> str:
    if not plate_type:
        return "96"
    pt = str(plate_type).strip()
    if "48" in pt:
        return "48"
    if "96" in pt:
        return "96"
    if "384" in pt:
        return "384"
    return "96"


def get_plate_layout(plate_type: str):
    pt = normalize_plate_type(plate_type)
    if pt == "48":
        return list("ABCDEF"), range(1, 9)
    if pt == "384":
        return list("ABCDEFGHIJKLMNOP"), range(1, 25)
    return list("ABCDEFGH"), range(1, 13)


def compute_missing_wells(detected, plate_type: str):
    detected = detected or []
    detected_set = set(detected)
    rows, cols = get_plate_layout(plate_type)
    full = [f"{r}{c}" for r in rows for c in cols]
    return [w for w in full if w not in detected_set]


def dataframe_to_html(df):
    return df.to_html(
        classes="table table-sm table-striped table-hover align-middle",
        index=False,
        float_format=lambda x: f"{x:.4f}",
        border=0,
    )

# --------------------------------
# PDF generation
# --------------------------------
def generate_pdf(df, title="Results"):
    filename = f"results/{uuid.uuid4().hex}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=landscape(letter))
    elements = []

    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    title_style.fontSize = 16

    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 12))

    data = [df.columns.to_list()] + df.values.tolist()
    cleaned = []
    for row in data:
        cleaned.append([f"{x:.4f}" if isinstance(x, float) else str(x) for x in row])

    col_width = (9.5 * inch) / len(df.columns)
    table = Table(cleaned, colWidths=[col_width] * len(df.columns))

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )

    elements.append(table)
    doc.build(elements)
    return filename

# =====================================================
# MAIN ROUTE
# =====================================================
@app.route("/", methods=["GET", "POST"])
def index():
    # Defaults
    plate_type = "96"
    illuminant_key = "D65"
    observer_angle = "2"

    table_html = None
    raw_matrix_html = None
    error = None
    detected_wells = None
    missing_wells = None

    # "reference_well" = actual well name (for well-mode)
    reference_well = None
    # "reference_label" = what we show in UI ("Buffer", "WhiteTile", or well id)
    reference_label = "Buffer"

    file_token = None
    uploaded_filename = None
    wavelength_list = []

    blank_input = ""
    used_blanks = []
    ref_target_preset = "Buffer"
    custom_L, custom_a, custom_b = None, None, None
    reference_mode = "lab"  # "lab" or "well"

    # Default target display (Buffer preset)
    target_lab_default = LAB_PRESETS["Buffer"]
    target_display = (
        f"L*={target_lab_default[0]:.2f}, "
        f"a*={target_lab_default[1]:.2f}, "
        f"b*={target_lab_default[2]:.2f}"
    )

    if request.method == "POST":
        # --- basic controls ---
        plate_type = request.form.get("plate_type", plate_type)
        illuminant_key = request.form.get("illuminant_key", illuminant_key)
        observer_angle = request.form.get("observer_angle", observer_angle)

        # --- ΔE mode + reference well ---
        reference_mode = request.form.get("reference_mode", "lab")
        reference_well_form = request.form.get("reference_well") or ""
        reference_well = reference_well_form.strip() or None

        # --- reference target preset ---
        ref_target_preset = request.form.get("ref_target_preset", "Buffer")
        custom_L = request.form.get("custom_L")
        custom_a = request.form.get("custom_a")
        custom_b = request.form.get("custom_b")

        # --- blanks (string of comma-separated wells) ---
        blank_input = request.form.get("blank_wells", "") or ""
        blank_list = [b.strip() for b in blank_input.split(",") if b.strip()]

        # Determine Lab target if in lab mode
        lab_target = None
        if reference_mode == "lab":
            if ref_target_preset == "Custom":
                try:
                    L = float(custom_L) if custom_L else 0.0
                    a = float(custom_a) if custom_a else 0.0
                    b = float(custom_b) if custom_b else 0.0
                    lab_target = (L, a, b)
                except ValueError:
                    error = "Custom L*a*b* values must be valid numbers."
            elif ref_target_preset in LAB_PRESETS:
                lab_target = LAB_PRESETS[ref_target_preset]
            else:
                error = "Invalid Reference Target Preset selected."
        else:
            # For well-mode, pipeline doesn't use lab_target (we still pass something)
            lab_target = (100.0, 0.0, 0.0)

        # file
        uploaded = request.files.get("dataset")

        if not uploaded or uploaded.filename == "":
            error = "Please choose a valid file (.xlsx, .xls, .csv)."

        if reference_mode == "lab" and lab_target is None and not error:
            error = "L*a*b* Target must be defined."

        if not error and uploaded and uploaded.filename:
            try:
                uploaded_filename = uploaded.filename
                token = make_token()
                ext = os.path.splitext(uploaded_filename)[1]
                filepath = os.path.join("uploads", token + ext)
                uploaded.save(filepath)

                plate_type_norm = normalize_plate_type(plate_type)

                df_results, detected_wells, ref_well_used, used_blanks, delta_col = process_plate(
                    excel_file=filepath,
                    reference_well=reference_well,
                    plate_type=plate_type_norm,
                    illuminant_key=illuminant_key,
                    observer_angle_deg=float(observer_angle),
                    blank_wells=blank_list,
                    lab_target=lab_target,
                    reference_mode=reference_mode,
                )

                file_token = token
                missing_wells = compute_missing_wells(detected_wells, plate_type_norm)
                table_html = dataframe_to_html(df_results)

                df_raw, _ = get_raw_matrix(filepath)
                raw_matrix_html = dataframe_to_html(df_raw)
                wavelength_list = df_raw["Wavelength"].astype(float).tolist()

                plate_type = plate_type_norm

                # UI labels
                if reference_mode == "lab":
                    reference_label = ref_target_preset
                    target_display = (
                        f"L*={lab_target[0]:.2f}, "
                        f"a*={lab_target[1]:.2f}, "
                        f"b*={lab_target[2]:.2f}"
                    )
                else:  # well mode
                    reference_well = ref_well_used
                    reference_label = ref_well_used
                    target_display = f"Reference well: {ref_well_used}"

            except Exception as e:
                print("UPLOAD/PROCESS ERROR:", e)
                error = f"Error processing file: {str(e)}"

    plate_rows, plate_cols = get_plate_layout(plate_type)

    return render_template(
        "index.html",
        table_html=table_html,
        raw_matrix_html=raw_matrix_html,
        error=error,
        detected_wells=detected_wells,
        missing_wells=missing_wells,
        reference_well=reference_well,
        reference_label=reference_label,
        file_token=file_token,
        uploaded_filename=uploaded_filename,
        plate_type=plate_type,
        illuminant_key=illuminant_key,
        observer_angle=observer_angle,
        plate_rows=plate_rows,
        plate_cols=plate_cols,
        wavelength_list=wavelength_list,
        blank_input=blank_input,
        used_blanks=used_blanks,
        ref_target_preset=ref_target_preset,
        custom_L=custom_L,
        custom_a=custom_a,
        custom_b=custom_b,
        target_display=target_display,
        reference_mode=reference_mode,
    )

# =====================================================
# RECALCULATE (NO UPLOAD REQUIRED)
# =====================================================
@app.route("/recalculate", methods=["POST"])
def recalculate():
    file_token = request.form.get("file_token")
    plate_type = request.form.get("plate_type", "96")
    illuminant_key = request.form.get("illuminant_key", "D65")
    observer_angle = request.form.get("observer_angle", "2")

    reference_mode = request.form.get("reference_mode", "lab")
    reference_well = request.form.get("reference_well") or None

    ref_target_preset = request.form.get("ref_target_preset", "Buffer")
    custom_L = request.form.get("custom_L")
    custom_a = request.form.get("custom_a")
    custom_b = request.form.get("custom_b")

    uploaded_filename = request.form.get("uploaded_filename", "")

    if not file_token:
        return "Missing file token", 400

    filepath = None
    for f in os.listdir("uploads"):
        if f.startswith(file_token):
            filepath = os.path.join("uploads", f)
            break

    if not filepath:
        return "Dataset missing on server", 404

    # Determine Lab target for lab-mode
    lab_target = None
    if reference_mode == "lab":
        if ref_target_preset == "Custom":
            try:
                lab_target = (
                    float(custom_L or 0),
                    float(custom_a or 0),
                    float(custom_b or 0),
                )
            except Exception:
                return "Invalid custom LAB", 400
        else:
            lab_target = LAB_PRESETS.get(ref_target_preset)
            if lab_target is None:
                return "Invalid reference target", 400
    else:
        lab_target = (100.0, 0.0, 0.0)

    # Blanks (string)
    blank_input = request.form.get("blank_wells", "") or ""
    blank_list = [b.strip() for b in blank_input.split(",") if b.strip()]

    df_results, detected_wells, ref_well_used, used_blanks, delta_col = process_plate(
        excel_file=filepath,
        reference_well=reference_well,
        plate_type=normalize_plate_type(plate_type),
        illuminant_key=illuminant_key,
        observer_angle_deg=float(observer_angle),
        blank_wells=blank_list,
        lab_target=lab_target,
        reference_mode=reference_mode,
    )

    plate_type_norm = normalize_plate_type(plate_type)
    missing_wells = compute_missing_wells(detected_wells, plate_type_norm)
    df_raw, _ = get_raw_matrix(filepath)
    wavelength_list = df_raw["Wavelength"].astype(float).tolist()

    # Resolve actual reference well/label and target display
    reference_well = ref_well_used
    if reference_mode == "lab":
        reference_label = ref_target_preset
        target_display = (
            f"L*={lab_target[0]:.2f}, "
            f"a*={lab_target[1]:.2f}, "
            f"b*={lab_target[2]:.2f}"
        )
    else:
        reference_label = ref_well_used
        target_display = f"Reference well: {ref_well_used}"

    plate_rows, plate_cols = get_plate_layout(plate_type_norm)

    return render_template(
        "index.html",
        table_html=dataframe_to_html(df_results),
        raw_matrix_html=dataframe_to_html(df_raw),
        error=None,
        detected_wells=detected_wells,
        missing_wells=missing_wells,
        reference_well=reference_well,
        reference_label=reference_label,
        file_token=file_token,
        uploaded_filename=uploaded_filename,
        plate_type=plate_type_norm,
        illuminant_key=illuminant_key,
        observer_angle=observer_angle,
        plate_rows=plate_rows,
        plate_cols=plate_cols,
        wavelength_list=wavelength_list,
        blank_input=blank_input,
        used_blanks=used_blanks,
        ref_target_preset=ref_target_preset,
        custom_L=custom_L,
        custom_a=custom_a,
        custom_b=custom_b,
        target_display=target_display,
        reference_mode=reference_mode,
    )

# =====================================================
# DOWNLOAD CSV
# =====================================================
@app.route("/download_csv", methods=["POST"])
def download_csv():
    data_b64 = request.form.get("data_b64")
    if not data_b64:
        return "No data", 400

    try:
        html = base64.b64decode(data_b64).decode("utf-8")
    except Exception as e:
        return f"Base64 decode error: {e}", 400

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("tr")
    if not rows:
        return "No rows in table", 400

    data = [
        [col.get_text(strip=True) for col in row.find_all(["th", "td"])]
        for row in rows
    ]

    # First row = header
    df = pd.DataFrame(data[1:], columns=data[0])

    filename = os.path.join("results", f"table_{uuid.uuid4().hex[:8]}.csv")
    df.to_csv(filename, index=False)

    return send_file(filename, as_attachment=True, download_name="results.csv")

# =====================================================
# DOWNLOAD PDF
# =====================================================
@app.route("/download_pdf", methods=["POST"])
def download_pdf():
    data_b64 = request.form.get("data_b64")
    if not data_b64:
        return "No data", 400

    try:
        html = base64.b64decode(data_b64).decode("utf-8")
    except Exception as e:
        return f"Base64 decode error: {e}", 400

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("tr")
    if not rows:
        return "No rows in table", 400

    data = [
        [col.get_text(strip=True) for col in row.find_all(["th", "td"])]
        for row in rows
    ]

    df = pd.DataFrame(data[1:], columns=data[0])

    try:
        pdf_path = generate_pdf(df, title="Plate Analysis Results")
        return send_file(pdf_path, as_attachment=True, download_name="results.pdf")
    except Exception as e:
        return f"PDF Error: {e}", 500

# =====================================================
# MULTI-WELL SPECTRA API
# =====================================================
@app.route("/spectra_multi")
def spectra_multi():
    token = request.args.get("token")
    wells_raw = request.args.get("wells")

    if not token or not wells_raw:
        return jsonify({"error": "Missing parameters"}), 400

    filepath = None
    for f in os.listdir("uploads"):
        if f.startswith(token):
            filepath = os.path.join("uploads", f)
            break

    if not filepath:
        return jsonify({"error": "Dataset not found"}), 404

    wells = [w.strip() for w in wells_raw.split(",")]

    try:
        wavelengths, spectra = get_wells_spectra(filepath, wells)
        return jsonify({"wavelengths": wavelengths, "spectra": spectra})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# RATIO ENGINE
# =====================================================
@app.route("/compute_ratio", methods=["POST"])
def compute_ratio_route():
    file_token = request.form.get("file_token")
    if not file_token:
        return "Missing token", 400

    wlA = float(request.form.get("wlA"))
    wlB = float(request.form.get("wlB"))
    op = request.form.get("operation")

    filepath = None
    for f in os.listdir("uploads"):
        if f.startswith(file_token):
            filepath = os.path.join("uploads", f)
            break

    if not filepath:
        return "Dataset missing on server", 404

    df_raw, wells = get_raw_matrix(filepath)

    # Find closest wavelengths
    idxA = (df_raw["Wavelength"] - wlA).abs().idxmin()
    idxB = (df_raw["Wavelength"] - wlB).abs().idxmin()

    A = df_raw.loc[idxA, wells].astype(float)
    B = df_raw.loc[idxB, wells].astype(float)

    if op == "divide":
        result = A / B.replace(0, np.nan)
    elif op == "subtract":
        result = A - B
    elif op == "normdiff":
        result = (A - B) / B.replace(0, np.nan)
    elif op == "average":
        result = (A + B) / 2
    else:
        return "Invalid operation", 400

    df_out = pd.DataFrame({"Well": wells, "Result": result.values}).round(5)
    return dataframe_to_html(df_out)

# =====================================================
# DEBUG VALIDATION
# =====================================================
@app.route("/debug_validate")
def debug_validate():
    import numpy as np
    import colour

    try:
        wavelengths = np.arange(380, 781, 5)
        trans = np.ones_like(wavelengths, float)

        shape = colour.SpectralShape(380, 780, 5)
        illum = colour.SDS_ILLUMINANTS["D65"].copy().align(shape)

        sample_sd = colour.SpectralDistribution(trans, illum.domain)
        XYZ = colour.sd_to_XYZ(sample_sd, illuminant=illum)


        perfect_trans = np.ones_like(illum.domain, float)
        perfect_sd    = colour.SpectralDistribution(perfect_trans, illum.domain)
        XYZ_white     = colour.sd_to_XYZ(perfect_sd, illuminant=illum)
        Y_max         = max(float(XYZ_white[1]), 1e-8)


        XYZ_norm = XYZ / Y_max
        wp = colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"]
        Lab = colour.XYZ_to_Lab(XYZ_norm, wp)

        delta_e = float(colour.delta_E([100, 0, 0], Lab, method="CIE 2000"))

        return jsonify(
            XYZ_raw=XYZ.tolist(),
            XYZ_norm=XYZ_norm.tolist(),
            Lab=Lab.tolist(),
            deltaE=delta_e,
        )
    except Exception as e:
        return jsonify(error=str(e))

# =====================================================
# MAIN
# =====================================================
if __name__ == "__main__":
    app.run(debug=True)
