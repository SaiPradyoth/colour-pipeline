# ================================
# app.py
# Flask front-end for Spectral → Color → ΔE Analyzer
# ================================

import os
import uuid
import pandas as pd
from flask import Flask, render_template, request, send_file, jsonify

from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import letter, landscape

from pipeline import (
    process_plate,
    get_well_spectrum,
    get_wells_spectra,
    get_raw_matrix,
)

app = Flask(__name__)

# --------------------------------
# Ensure folders exist on startup
# --------------------------------
os.makedirs("uploads", exist_ok=True)
os.makedirs("results", exist_ok=True)


# --------------------------------
# Token <-> path helpers
# --------------------------------
def make_token() -> str:
    """Generate a secure random token to decouple filenames from disk paths."""
    return uuid.uuid4().hex


def token_to_path(token: str) -> str:
    """Convert a token string into a safe path inside ./uploads."""
    return os.path.join("uploads", f"{token}.bin")


# --------------------------------
# Plate layout helpers
# --------------------------------
PLATE_LAYOUTS = {
    "48": ("ABCDEF", range(1, 9)),              # A–F, 1–8    (6 x 8)
    "96": ("ABCDEFGH", range(1, 13)),           # A–H, 1–12   (8 x 12)
    "384": ("ABCDEFGHIJKLMNOP", range(1, 25)),  # A–P, 1–24   (16 x 24)
}


def normalize_plate_type(plate_type: str) -> str:
    """
    Normalize user / form input to canonical strings: "48", "96", "384".
    """
    if not plate_type:
        return "96"
    pt = str(plate_type).strip().lower()
    if pt in {"48", "48-well", "48 well"}:
        return "48"
    if pt in {"96", "96-well", "96 well"}:
        return "96"
    if pt in {"384", "384-well", "384 well"}:
        return "384"
    raise ValueError(f"Unsupported plate type: {plate_type}")


def get_plate_layout(plate_type: str):
    """
    Return (rows, cols) for a given canonical plate type ("48", "96", "384").
    """
    pt = normalize_plate_type(plate_type)
    try:
        rows, cols = PLATE_LAYOUTS[pt]
    except KeyError:
        raise ValueError(f"Unsupported plate type: {plate_type}")
    return list(rows), list(cols)


def compute_missing_wells(detected, plate_type: str):
    """
    Given a list of detected wells, compute which plate locations are missing.
    """
    detected = detected or []
    detected_set = set(detected)
    rows, cols = get_plate_layout(plate_type)
    full = [f"{r}{c}" for r in rows for c in cols]
    return [w for w in full if w not in detected_set]


# --------------------------------
# Table HTML helpers
# --------------------------------
def dataframe_to_html(df: pd.DataFrame) -> str:
    """
    Convert a DataFrame into HTML suitable for our UI.
    """
    return df.to_html(
        classes="table table-sm table-striped table-hover align-middle",
        index=False,
        float_format=lambda x: f"{x:.4f}",
        border=0,
    )


# =====================================================
# MAIN PAGE (UPLOAD + DASHBOARD)
# =====================================================
@app.route("/", methods=["GET", "POST"])
def index():
    """
    Dashboard page: upload, parameter selection, results, scientist mode.
    """

    # Defaults for dropdowns
    plate_type = "96"
    illuminant_key = "D65"
    observer_angle = "2"  # keep as string for Jinja

    # Outputs
    table_html = None
    raw_matrix_html = None
    error = None
    detected_wells = None
    missing_wells = None
    reference_well = None
    file_token = None
    uploaded_filename = None

    if request.method == "POST":
        # Read current UI selections from the form
        plate_type = request.form.get("plate_type", plate_type)
        illuminant_key = request.form.get("illuminant_key", illuminant_key)
        observer_angle = request.form.get("observer_angle", observer_angle)

        uploaded = request.files.get("dataset")

        if not uploaded or uploaded.filename == "":
            error = "Please choose an .xlsx file first."
        else:
            try:
                uploaded_filename = uploaded.filename

                # Save uploaded file under a random token
                token = make_token()
                filepath = token_to_path(token)
                uploaded.save(filepath)

                plate_type_norm = normalize_plate_type(plate_type)

                # Run full pipeline (ΔE2000 inside)
                df_results, detected_wells, reference_well = process_plate(
                    excel_file=filepath,
                    reference_well=None,
                    plate_type=plate_type_norm,
                    illuminant_key=illuminant_key,
                    observer_angle_deg=float(observer_angle),
                )

                file_token = token
                missing_wells = compute_missing_wells(detected_wells, plate_type_norm)

                table_html = dataframe_to_html(df_results)

                # Raw absorbance matrix (Scientist Mode)
                df_raw, _ = get_raw_matrix(filepath)
                raw_matrix_html = dataframe_to_html(df_raw)

                plate_type = plate_type_norm

            except Exception as e:
                error = f"Error processing file: {e}"

    # Plate layout for future use
    try:
        plate_rows, plate_cols = get_plate_layout(plate_type)
    except Exception:
        plate_rows, plate_cols = get_plate_layout("96")

    return render_template(
        "index.html",
        table_html=table_html,
        raw_matrix_html=raw_matrix_html,
        error=error,
        detected_wells=detected_wells,
        missing_wells=missing_wells,
        reference_well=reference_well,
        file_token=file_token,
        uploaded_filename=uploaded_filename,
        plate_type=plate_type,
        illuminant_key=illuminant_key,
        observer_angle=observer_angle,
        plate_rows=plate_rows,
        plate_cols=plate_cols,
    )


# =====================================================
# RECALCULATE WITH NEW SETTINGS (NO NEW UPLOAD)
# =====================================================
@app.route("/recalculate", methods=["POST"])
def recalculate():
    """
    Re-run the color pipeline using:
      - existing uploaded file (via token)
      - possibly new reference well / parameters
    """

    file_token = request.form.get("file_token")
    reference_well = request.form.get("reference_well") or None
    plate_type = request.form.get("plate_type", "96")
    illuminant_key = request.form.get("illuminant_key", "D65")
    observer_angle = request.form.get("observer_angle", "2")
    uploaded_filename = request.form.get("uploaded_filename") or None

    if not file_token:
        return "Missing file token. Upload a dataset again.", 400

    filepath = token_to_path(file_token)
    if not os.path.exists(filepath):
        return "File missing on server. Please re-upload the dataset.", 400

    try:
        plate_type_norm = normalize_plate_type(plate_type)

        df_results, detected_wells, reference_well = process_plate(
            excel_file=filepath,
            reference_well=reference_well,
            plate_type=plate_type_norm,
            illuminant_key=illuminant_key,
            observer_angle_deg=float(observer_angle),
        )

        missing_wells = compute_missing_wells(detected_wells, plate_type_norm)
        table_html = dataframe_to_html(df_results)

        # Raw matrix again
        df_raw, _ = get_raw_matrix(filepath)
        raw_matrix_html = dataframe_to_html(df_raw)

        plate_rows, plate_cols = get_plate_layout(plate_type_norm)

        return render_template(
            "index.html",
            table_html=table_html,
            raw_matrix_html=raw_matrix_html,
            error=None,
            detected_wells=detected_wells,
            missing_wells=missing_wells,
            reference_well=reference_well,
            file_token=file_token,
            uploaded_filename=uploaded_filename,
            plate_type=plate_type_norm,
            illuminant_key=illuminant_key,
            observer_angle=observer_angle,
            plate_rows=plate_rows,
            plate_cols=plate_cols,
        )

    except Exception as e:
        return f"Error recalculating: {e}", 500


# =====================================================
# SPECTRAL CURVE JSON API (SINGLE WELL)
# =====================================================
@app.route("/spectra", methods=["GET"])
def spectra():
    """Return JSON (wavelengths, absorbance) for a single well in the uploaded file."""

    well = request.args.get("well")
    token = request.args.get("token")

    if not well or not token:
        return jsonify({"error": "Missing 'well' or 'token'"}), 400

    filepath = token_to_path(token)
    if not os.path.exists(filepath):
        return jsonify({"error": "Dataset not found"}), 404

    try:
        wavelengths, absorbance = get_well_spectrum(filepath, well)
        return jsonify(
            {
                "well": well,
                "wavelengths": wavelengths,
                "absorbance": absorbance,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =====================================================
# SPECTRAL CURVE JSON API (MULTI-WELL OVERLAY)
# =====================================================
@app.route("/spectra_multi", methods=["GET"])
def spectra_multi():
    """
    Return JSON spectra for multiple wells in a single call.

    Query params:
      - token: file token
      - wells: comma-separated list, e.g. "A1,B3,C7"
    """

    token = request.args.get("token")
    wells_param = request.args.get("wells")

    if not token or not wells_param:
        return jsonify({"error": "Missing 'token' or 'wells'"}), 400

    wells = [w.strip() for w in wells_param.split(",") if w.strip()]
    if not wells:
        return jsonify({"error": "No valid well IDs provided."}), 400

    filepath = token_to_path(token)
    if not os.path.exists(filepath):
        return jsonify({"error": "Dataset not found"}), 404

    try:
        wavelengths, spectra_dict = get_wells_spectra(filepath, wells)
        spectra_payload = [
            {"well": w, "absorbance": spectra_dict[w]} for w in wells if w in spectra_dict
        ]

        if not spectra_payload:
            return jsonify(
                {"error": "No spectra could be loaded for the requested wells."}
            ), 400

        return jsonify(
            {
                "wavelengths": wavelengths,
                "spectra": spectra_payload,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =====================================================
# DOWNLOAD: COLOUR RESULTS TABLE AS LANDSCAPE PDF
# =====================================================
@app.route("/download_pdf", methods=["POST"])
def download_pdf():
    """Generate a PDF from the color results table HTML (landscape page)."""

    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch

    table_html = request.form.get("data")
    soup = BeautifulSoup(table_html, "html.parser")
    rows = soup.find_all("tr")

    data = [
        [col.get_text(strip=True) for col in row.find_all(["th", "td"])]
        for row in rows
    ]

    if not data:
        return "No data provided for PDF export.", 400

    filename = f"results/deltaE_{uuid.uuid4().hex[:8]}.pdf"
    pdf = SimpleDocTemplate(filename, pagesize=landscape(letter))

    num_cols = len(data[0])
    max_width = 10.0 * inch
    col_width = max_width / max(num_cols, 1)
    col_widths = [col_width] * num_cols

    from reportlab.platypus import Table

    table = Table(data, colWidths=col_widths, repeatRows=1)

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#000000")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTSIZE", (0, 1), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    pdf.build([table])
    return send_file(filename, as_attachment=True)


# =====================================================
# DOWNLOAD: COLOUR RESULTS TABLE AS CSV
# =====================================================
@app.route("/download_csv", methods=["POST"])
def download_csv():
    """Download the color results table as CSV."""

    table_html = request.form.get("data")
    soup = BeautifulSoup(table_html, "html.parser")
    rows = soup.find_all("tr")

    data = [
        [col.get_text(strip=True) for col in row.find_all(["th", "td"])]
        for row in rows
    ]

    if not data:
        return "No data provided for CSV export.", 400

    df = pd.DataFrame(data[1:], columns=data[0])
    filename = f"results/table_{uuid.uuid4().hex[:8]}.csv"
    df.to_csv(filename, index=False)

    return send_file(filename, as_attachment=True, download_name="results.csv")


# =====================================================
# DOWNLOAD: RAW ABSORBANCE MATRIX (XLSX)
# =====================================================
@app.route("/download_raw_xlsx", methods=["POST"])
def download_raw_xlsx():
    """Download raw absorbance matrix (Scientist Mode) as XLSX."""

    file_token = request.form.get("file_token")
    if not file_token:
        return "Missing file token.", 400

    filepath = token_to_path(file_token)
    if not os.path.exists(filepath):
        return "File missing on server. Please re-upload.", 400

    df_raw, _ = get_raw_matrix(filepath)
    filename = f"results/raw_{uuid.uuid4().hex[:8]}.xlsx"
    df_raw.to_excel(filename, index=False)

    return send_file(filename, as_attachment=True, download_name="raw_matrix.xlsx")


# =====================================================
# DOWNLOAD: RAW ABSORBANCE MATRIX (LANDSCAPE PDF)
# =====================================================
@app.route("/download_raw_pdf", methods=["POST"])
def download_raw_pdf():
    """Download raw absorbance matrix (Scientist Mode) as landscape PDF."""

    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch

    file_token = request.form.get("file_token")
    if not file_token:
        return "Missing file token.", 400

    filepath = token_to_path(file_token)
    if not os.path.exists(filepath):
        return "File missing on server. Please re-upload.", 400

    df_raw, _ = get_raw_matrix(filepath)

    data = [list(df_raw.columns)] + df_raw.values.tolist()
    if not data:
        return "No raw matrix data available.", 400

    filename = f"results/raw_{uuid.uuid4().hex[:8]}.pdf"
    pdf = SimpleDocTemplate(filename, pagesize=landscape(letter))

    num_cols = len(data[0])
    max_width = 10.0 * inch
    col_width = max_width / max(num_cols, 1)
    col_widths = [col_width] * num_cols

    table = Table(data, colWidths=col_widths, repeatRows=1)

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#000000")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTSIZE", (0, 1), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    pdf.build([table])
    return send_file(filename, as_attachment=True, download_name="raw_matrix.pdf")


# =====================================================
# START APP (dev only)
# =====================================================
if __name__ == "__main__":
    app.run(debug=True)
