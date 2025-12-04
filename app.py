# ================================
# app.py
# Flask front-end for Spectral → Color → ΔE Analyzer
# ================================

import os
import uuid
import pandas as pd
import numpy as np  # <--- FIXED: Added this
from flask import Flask, render_template, request, send_file, jsonify

from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

from pipeline import (
    process_plate,
    get_well_spectrum,
    get_wells_spectra,
    get_raw_matrix,
)

app = Flask(__name__)

# Ensure folders exist
os.makedirs("uploads", exist_ok=True)
os.makedirs("results", exist_ok=True)

# --------------------------------
# Helpers
# --------------------------------
def make_token() -> str:
    return uuid.uuid4().hex

def token_to_path(token: str) -> str:
    base = os.path.join("uploads", token)
    return base + ".bin" 

def normalize_plate_type(plate_type: str) -> str:
    if not plate_type: return "96"
    pt = str(plate_type).strip().lower()
    if "48" in pt: return "48"
    if "96" in pt: return "96"
    if "384" in pt: return "384"
    return "96"

def get_plate_layout(plate_type: str):
    pt = normalize_plate_type(plate_type)
    if pt == "48": return list("ABCDEF"), range(1, 9)
    if pt == "384": return list("ABCDEFGHIJKLMNOP"), range(1, 25)
    return list("ABCDEFGH"), range(1, 13)

def compute_missing_wells(detected, plate_type: str):
    detected = detected or []
    detected_set = set(detected)
    rows, cols = get_plate_layout(plate_type)
    full = [f"{r}{c}" for r in rows for c in cols]
    return [w for w in full if w not in detected_set]

def dataframe_to_html(df: pd.DataFrame) -> str:
    return df.to_html(
        classes="table table-sm table-striped table-hover align-middle",
        index=False,
        float_format=lambda x: f"{x:.4f}",
        border=0,
    )

# --------------------------------
# PDF Generation Helper
# --------------------------------
def generate_pdf(df, title="Results"):
    filename = f"results/{uuid.uuid4().hex}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=landscape(letter))
    elements = []
    
    styles = getSampleStyleSheet()
    elements.append(Paragraph(title, styles['Title']))

    # Convert DataFrame to list of lists
    data = [df.columns.to_list()] + df.values.tolist()
    
    # Round floats for display in PDF
    clean_data = []
    for row in data:
        new_row = []
        for item in row:
            if isinstance(item, float):
                new_row.append(f"{item:.4f}")
            else:
                new_row.append(str(item))
        clean_data.append(new_row)

    table = Table(clean_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))
    
    elements.append(table)
    doc.build(elements)
    return filename

# =====================================================
# ROUTES
# =====================================================
@app.route("/", methods=["GET", "POST"])
def index():
    plate_type = "96"
    illuminant_key = "D65"
    observer_angle = "2"
    
    table_html = None
    raw_matrix_html = None
    error = None
    detected_wells = None
    missing_wells = None
    reference_well = None
    file_token = None
    uploaded_filename = None
    wavelength_list = []

    if request.method == "POST":
        plate_type = request.form.get("plate_type", plate_type)
        illuminant_key = request.form.get("illuminant_key", illuminant_key)
        observer_angle = request.form.get("observer_angle", observer_angle)
        
        uploaded = request.files.get("dataset")
        
        if not uploaded or uploaded.filename == "":
            error = "Please choose a valid file (.xlsx, .xls, .csv)."
        else:
            try:
                uploaded_filename = uploaded.filename
                token = make_token()
                ext = os.path.splitext(uploaded_filename)[1]
                filepath = os.path.join("uploads", token + ext) 
                uploaded.save(filepath)

                plate_type_norm = normalize_plate_type(plate_type)
                
                # Run Pipeline
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

                # Get Raw Matrix
                df_raw, _ = get_raw_matrix(filepath)
                raw_matrix_html = dataframe_to_html(df_raw)
                wavelength_list = df_raw["Wavelength"].astype(float).tolist()
                
                plate_type = plate_type_norm

            except Exception as e:
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
        file_token=file_token,
        uploaded_filename=uploaded_filename,
        plate_type=plate_type,
        illuminant_key=illuminant_key,
        observer_angle=observer_angle,
        plate_rows=plate_rows,
        plate_cols=plate_cols,
        wavelength_list=wavelength_list,
    )

@app.route("/recalculate", methods=["POST"])
def recalculate():
    file_token = request.form.get("file_token")
    reference_well = request.form.get("reference_well") or None
    plate_type = request.form.get("plate_type", "96")
    illuminant_key = request.form.get("illuminant_key", "D65")
    observer_angle = request.form.get("observer_angle", "2")
    uploaded_filename = request.form.get("uploaded_filename") or None

    if not file_token: return "Missing file token.", 400

    filepath = None
    for f in os.listdir("uploads"):
        if f.startswith(file_token):
            filepath = os.path.join("uploads", f)
            break
            
    if not filepath or not os.path.exists(filepath):
        return "File missing on server. Please re-upload.", 400

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
            wavelength_list=df_raw["Wavelength"].astype(float).tolist(),
        )
    except Exception as e:
        return f"Error recalculating: {e}", 500

@app.route("/spectra_multi", methods=["GET"])
def spectra_multi():
    token = request.args.get("token")
    wells_param = request.args.get("wells")

    if not token or not wells_param:
        return jsonify({"error": "Missing 'token' or 'wells'"}), 400

    filepath = None
    for f in os.listdir("uploads"):
        if f.startswith(token):
            filepath = os.path.join("uploads", f)
            break

    if not filepath:
        return jsonify({"error": "Dataset not found"}), 404

    wells = [w.strip() for w in wells_param.split(",") if w.strip()]
    
    try:
        wavelengths, spectra_dict = get_wells_spectra(filepath, wells)
        spectra_payload = [
            {"well": w, "absorbance": spectra_dict[w]} for w in wells if w in spectra_dict
        ]
        return jsonify({"wavelengths": wavelengths, "spectra": spectra_payload})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/compute_ratio", methods=["POST"])
def compute_ratio_route():
    file_token = request.form.get("file_token")
    wlA = request.form.get("wlA")
    wlB = request.form.get("wlB")
    operation = request.form.get("operation")

    if not file_token: return "Missing file token.", 400
    
    filepath = None
    for f in os.listdir("uploads"):
        if f.startswith(file_token):
            filepath = os.path.join("uploads", f)
            break
            
    if not filepath: return "Dataset not found.", 400

    try:
        df_raw, available_wells = get_raw_matrix(filepath)
        wlA = float(wlA)
        wlB = float(wlB)

        idx_A = (df_raw["Wavelength"] - wlA).abs().idxmin()
        idx_B = (df_raw["Wavelength"] - wlB).abs().idxmin()

        if abs(df_raw.loc[idx_A, "Wavelength"] - wlA) > 0.1:
             return f"Wavelength {wlA} nm not found in dataset.", 400
        if abs(df_raw.loc[idx_B, "Wavelength"] - wlB) > 0.1:
             return f"Wavelength {wlB} nm not found in dataset.", 400

        A = df_raw.loc[idx_A, available_wells].astype(float)
        B = df_raw.loc[idx_B, available_wells].astype(float)

        if operation == "divide":
            result = A / B.replace(0, np.nan) 
            label = f"{wlA} / {wlB}"
        elif operation == "subtract":
            result = A - B
            label = f"{wlA} – {wlB}"
        elif operation == "normdiff":
            result = (A - B) / B.replace(0, np.nan)
            label = f"({wlA} – {wlB}) / {wlB}"
        elif operation == "average":
            result = (A + B) / 2
            label = f"({wlA} + {wlB}) / 2"
        else:
            return "Unknown operation.", 400

        df_out = pd.DataFrame({
            "Well": available_wells, 
            "Result": result.values
        }).round(5)
        
        return dataframe_to_html(df_out)

    except Exception as e:
        return f"Error computing ratio: {e}", 500

@app.route("/download_csv", methods=["POST"])
def download_csv():
    table_html = request.form.get("data")
    if not table_html: return "No data", 400
    soup = BeautifulSoup(table_html, "html.parser")
    data = [[col.get_text(strip=True) for col in row.find_all(["th", "td"])] for row in soup.find_all("tr")]
    if not data: return "No data", 400
    df = pd.DataFrame(data[1:], columns=data[0])
    filename = f"results/table_{uuid.uuid4().hex[:8]}.csv"
    df.to_csv(filename, index=False)
    return send_file(filename, as_attachment=True, download_name="results.csv")

# ---------------------------------------------------
# MISSING ROUTES ADDED BELOW
# ---------------------------------------------------

@app.route("/download_pdf", methods=["POST"])
def download_pdf():
    table_html = request.form.get("data")
    if not table_html: return "No data", 400
    
    # Parse HTML to DataFrame
    soup = BeautifulSoup(table_html, "html.parser")
    rows = soup.find_all("tr")
    if not rows: return "No data found", 400
    
    data = [[ele.text.strip() for ele in row.find_all(["th", "td"])] for row in rows]
    df = pd.DataFrame(data[1:], columns=data[0])
    
    try:
        pdf_path = generate_pdf(df, title="Plate Analysis Results")
        return send_file(pdf_path, as_attachment=True, download_name="results.pdf")
    except Exception as e:
        return f"Error generating PDF: {e}", 500

@app.route("/download_raw_xlsx", methods=["POST"])
def download_raw_xlsx():
    file_token = request.form.get("file_token")
    if not file_token: return "Missing token", 400
    
    filepath = None
    for f in os.listdir("uploads"):
        if f.startswith(file_token):
            filepath = os.path.join("uploads", f)
            break
            
    if not filepath: return "File not found", 404
    
    try:
        df_raw, _ = get_raw_matrix(filepath)
        out_name = f"results/raw_{uuid.uuid4().hex[:8]}.xlsx"
        df_raw.to_excel(out_name, index=False)
        return send_file(out_name, as_attachment=True, download_name="raw_matrix.xlsx")
    except Exception as e:
        return f"Error: {e}", 500

@app.route("/download_raw_pdf", methods=["POST"])
def download_raw_pdf():
    file_token = request.form.get("file_token")
    if not file_token: return "Missing token", 400
    
    filepath = None
    for f in os.listdir("uploads"):
        if f.startswith(file_token):
            filepath = os.path.join("uploads", f)
            break
            
    if not filepath: return "File not found", 404
    
    try:
        df_raw, _ = get_raw_matrix(filepath)
        # We might want to limit rows for PDF if it's huge, but let's try standard gen
        pdf_path = generate_pdf(df_raw, title="Raw Absorbance Matrix")
        return send_file(pdf_path, as_attachment=True, download_name="raw_matrix.pdf")
    except Exception as e:
        return f"Error: {e}", 500

if __name__ == "__main__":
    app.run(debug=True)