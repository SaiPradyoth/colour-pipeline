# app.py
from flask import Flask, render_template, request, send_file
from pipeline import process_plate

from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import letter
import uuid
import os
import pandas as pd

app = Flask(__name__)

# Folders
os.makedirs("results", exist_ok=True)
os.makedirs("uploads", exist_ok=True)


def compute_missing_wells(detected):
    rows = "ABCDEFGH"
    cols = range(1, 13)
    full = [f"{r}{c}" for r in rows for c in cols]
    return [w for w in full if w not in detected]


# ---------------------------------------------------
# HOME / UPLOAD ROUTE
# ---------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    table_html = None
    error = None
    detected_wells = None
    missing_wells = None
    reference_well = None
    file_path = None

    if request.method == "POST":
        uploaded = request.files.get("dataset")

        if not uploaded or uploaded.filename == "":
            error = "Please choose an .xlsx file first."
        else:
            try:
                # Save uploaded file to /uploads with unique name
                unique_name = f"{uuid.uuid4().hex}_{uploaded.filename}"
                file_path = os.path.join("uploads", unique_name)
                uploaded.save(file_path)

                # Run pipeline once (no reference_well => auto choose A10 or first)
                df_results, detected_wells, reference_well = process_plate(
                    file_path,
                    reference_well=None
                )

                missing_wells = compute_missing_wells(detected_wells)

                table_html = df_results.to_html(
                    classes="table table-striped table-sm",
                    index=False,
                    float_format=lambda x: f"{x:.4f}"
                )
            except Exception as e:
                error = f"Error processing file: {e}"

    return render_template(
        "index.html",
        table_html=table_html,
        error=error,
        detected_wells=detected_wells,
        missing_wells=missing_wells,
        reference_well=reference_well,
        file_path=file_path,
    )


# ---------------------------------------------------
# RECALCULATE WITH NEW REFERENCE WELL
# ---------------------------------------------------
@app.route("/recalculate", methods=["POST"])
def recalculate():
    reference_well = request.form.get("reference_well")
    file_path = request.form.get("file_path")

    if not file_path or not os.path.exists(file_path):
        return "Original file not found. Please upload again.", 400

    try:
        df_results, detected_wells, reference_well = process_plate(
            file_path,
            reference_well=reference_well
        )

        missing_wells = compute_missing_wells(detected_wells)

        table_html = df_results.to_html(
            classes="table table-striped table-sm",
            index=False,
            float_format=lambda x: f"{x:.4f}"
        )

        return render_template(
            "index.html",
            table_html=table_html,
            error=None,
            detected_wells=detected_wells,
            missing_wells=missing_wells,
            reference_well=reference_well,
            file_path=file_path,
        )

    except Exception as e:
        return f"Error recalculating: {e}", 500


# ---------------------------------------------------
# PDF DOWNLOAD ROUTE
# ---------------------------------------------------
@app.route("/download_pdf", methods=["POST"])
def download_pdf():
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch

    table_html = request.form.get("data")
    soup = BeautifulSoup(table_html, "html.parser")
    rows = soup.find_all("tr")

    data = []
    for row in rows:
        cols = [col.get_text(strip=True) for col in row.find_all(["th", "td"])]
        data.append(cols)

    pdf_filename = f"results/deltaE_{uuid.uuid4().hex[:8]}.pdf"

    pdf = SimpleDocTemplate(pdf_filename, pagesize=letter)

    col_widths = [
        0.8 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch,
        1.0 * inch, 1.0 * inch, 1.0 * inch, 1.2 * inch
    ]

    table = Table(data, colWidths=col_widths)

    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3)
    ])

    table.setStyle(style)
    pdf.build([table])

    return send_file(pdf_filename, as_attachment=True)


# ---------------------------------------------------
# CSV DOWNLOAD ROUTE
# ---------------------------------------------------
@app.route("/download_csv", methods=["POST"])
def download_csv():
    table_html = request.form.get("data")
    soup = BeautifulSoup(table_html, "html.parser")
    rows = soup.find_all("tr")

    data = []
    for row in rows:
        cols = [col.get_text(strip=True) for col in row.find_all(["th", "td"])]
        data.append(cols)

    df = pd.DataFrame(data[1:], columns=data[0])

    csv_filename = f"results/table_{uuid.uuid4().hex[:8]}.csv"
    df.to_csv(csv_filename, index=False)

    return send_file(csv_filename, as_attachment=True, download_name="results.csv")


# ---------------------------------------------------
# START FLASK APP
# ---------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
