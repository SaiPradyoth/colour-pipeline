# ================================
# app.py
# Spectral → Color → ΔE Analyzer
# Stateless results (in-memory), temp files for downloads
# ================================

import os
import uuid
import base64
import tempfile
import shutil
import sys
import socket
import subprocess

def is_port_open(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False
    

def start_hyperspectral_server():
    """
    Starts the hyperspectral FastAPI server on port 8001
    only if it is not already running.
    """
    HYPER_PORT = 8001

    if is_port_open(HYPER_PORT):
        print(f"ℹ Hyperspectral server already running on port {HYPER_PORT}")
        return

    print("🚀 Starting hyperspectral server on port 8001...")

    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "Hyperspectral.hyperspectral_ingest",
        ],
    )

import pandas as pd
import numpy as np

from flask import Flask, render_template, request, send_file, jsonify

from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# Pipeline imports
from pipeline import (
    process_plate,
    get_wells_spectra,
    get_raw_matrix,
)

# --------------------------------
# Flask + basic config
# --------------------------------
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 600 * 1024 * 1024
os.makedirs("uploads", exist_ok=True)

# =======================================
# Default LAB presets
# =======================================
LAB_PRESETS = {
    "Buffer":    (100.0, 0.0, 0.0),
    "WhiteTile": (95.0, -1.0, 1.0),
    "Black":     (0.0, 0.0, 0.0),
}

# =======================================
# Template filters + basic helpers
# =======================================
@app.template_filter("b64encode")
def b64encode_filter(s):
    if s is None:
        return ""
    return base64.b64encode(s.encode("utf-8")).decode("utf-8")


def make_token():
    return uuid.uuid4().hex


def normalize_plate_type(pt: str) -> str:
    if not pt:
        return "96"
    pt = str(pt).strip()
    if "48" in pt:
        return "48"
    if "384" in pt:
        return "384"
    return "96"


def get_plate_layout(pt: str):
    pt = normalize_plate_type(pt)
    if pt == "48":
        return list("ABCDEF"), range(1, 9)
    if pt == "384":
        return list("ABCDEFGHIJKLMNOP"), range(1, 25)
    return list("ABCDEFGH"), range(1, 13)


def compute_missing_wells(detected, pt: str):
    detected = detected or []
    detected_set = set(detected)
    rows, cols = get_plate_layout(pt)
    full = [f"{r}{c}" for r in rows for c in cols]
    return [w for w in full if w not in detected_set]


def dataframe_to_html(df: pd.DataFrame) -> str:
    return df.to_html(
        classes="table table-sm table-striped table-hover align-middle",
        index=False,
        float_format="%.4f",
        border=0,
    )


def safe_str(v):
    if v is None:
        return ""
    if isinstance(v, float) and np.isnan(v):
        return ""
    return str(v)


# =======================================
# Metadata loader + merger
# =======================================
def load_metadata_df(path: str) -> pd.DataFrame:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)

    if "Well" not in df.columns:
        raise ValueError("Metadata file must contain column 'Well'.")
    return df


def build_well_metadata(meta_path: str, source_name: str = None):
    """
    Returns (well_metadata_dict, source_display_name).

    well_metadata_dict[well] = {
        Well, Row, Column, Sample, AuNP, Contents, Category, MetadataSource
    }
    """
    if not meta_path or not os.path.exists(meta_path):
        return None, None

    df = load_metadata_df(meta_path)
    src = source_name or os.path.basename(meta_path)

    out = {}
    for _, row in df.iterrows():
        w = safe_str(row.get("Well", "")).strip()
        if not w:
            continue
        out[w] = {
            "Well": w,
            "Row": safe_str(row.get("Row", "")),
            "Column": safe_str(row.get("Column", "")),
            "Sample": safe_str(row.get("Sample", "")),
            "AuNP": safe_str(row.get("AuNP", row.get("Gold Nanoparticle Added", ""))),
            "Contents": safe_str(row.get("Contents", row.get("Well contents", ""))),
            "Category": safe_str(row.get("Category", "")),
            "MetadataSource": src,
        }
    return out, src


def merge_results_with_metadata(df_results: pd.DataFrame, well_metadata: dict):
    """
    Add ALL metadata fields into the exported dataframe for CSV/PDF.
    """
    if not well_metadata:
        return df_results

    meta_df = pd.DataFrame(well_metadata).T

    cols = ["Well", "Sample", "AuNP", "Contents", "Category", "Row", "Column", "MetadataSource"]
    existing = [c for c in cols if c in meta_df.columns]

    merged = df_results.merge(meta_df[existing], on="Well", how="left")
    for c in existing:
        merged[c] = merged[c].fillna("")
    return merged


# =======================================
# File token → file paths
# =======================================
def find_paths_for_token(token: str):
    """
    Returns (dataset_path, metadata_path) for a given token.
    Dataset: token + ext
    Metadata: token + "_meta" + ext
    """
    dataset = None
    meta = None
    prefix_meta = f"{token}_meta"

    for fname in os.listdir("uploads"):
        full = os.path.join("uploads", fname)
        if fname.startswith(prefix_meta):
            meta = full
        elif fname.startswith(token) and not fname.startswith(prefix_meta):
            dataset = full

    return dataset, meta


# =======================================
# PDF generator — dark header
# =======================================
def generate_pdf(df: pd.DataFrame, title="Plate Results") -> str:
    """
    Landscape PDF with zebra rows and ΔE color coding.
    Uses a temp file (stateless).
    """
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from datetime import datetime
    import colorsys

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    outpath = tmp.name
    tmp.close()

    doc = SimpleDocTemplate(
        outpath,
        pagesize=landscape(letter),
        leftMargin=35,
        rightMargin=35,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    normal_style = styles["Normal"]
    normal_style.fontSize = 8
    normal_style.leading = 10

    logo_path = "static/img/logo.png"
    header_logo = Image(logo_path, width=0.9 * inch, height=0.9 * inch) if os.path.exists(logo_path) else None

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    meta_summary = f"Generated on {timestamp}"

    elements = []
    if header_logo:
        elements.append(header_logo)
    elements.append(Paragraph(f"<b>{title}</b><br/>{meta_summary}", styles["Title"]))
    elements.append(Spacer(1, 18))

    columns = list(df.columns)
    table_data = [columns]

    delta_col = None
    for c in columns:
        if str(c).lower().startswith("deltae"):
            delta_col = c
            break

    for _, row in df.iterrows():
        row_cells = []
        for col in columns:
            row_cells.append(Paragraph(str(row[col]), normal_style))
        table_data.append(row_cells)

    delta_values = df[delta_col].astype(float).tolist() if delta_col else []
    if delta_values:
        d_min, d_max = min(delta_values), max(delta_values)
        if d_max == d_min:
            d_max = d_min + 1e-6
    else:
        d_min = d_max = 0.0

    max_total_width = 760
    num_cols = len(columns)
    base_width = max_total_width / max(1, num_cols)
    col_widths = [base_width] * num_cols

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)

    zebra_colors = [colors.whitesmoke, colors.white]
    base_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]

    for r in range(1, len(table_data)):
        base_style.append(("BACKGROUND", (0, r), (-1, r), zebra_colors[r % 2]))

    if delta_col:
        idx = columns.index(delta_col)
        for r_idx, val in enumerate(delta_values, start=1):
            t = (val - d_min) / (d_max - d_min)
            hue = 220 - 220 * t
            sat = 0.65
            light = (85 - 30 * t) / 100
            rr, gg, bb = colorsys.hls_to_rgb(hue / 360, light, sat)
            base_style.append(("BACKGROUND", (idx, r_idx), (idx, r_idx), colors.Color(rr, gg, bb)))

    tbl.setStyle(TableStyle(base_style))

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        page = canvas.getPageNumber()
        canvas.drawString(doc_.width + doc_.leftMargin - 40, 15, f"Page {page}")
        canvas.restoreState()

    doc.build(elements + [tbl], onFirstPage=footer, onLaterPages=footer)
    return outpath

# =====================================================
# HYPERSPECTRAL PAGE ROUTE
# =====================================================
@app.route("/hyperspectral")
def hyperspectral_page():
    return render_template(
        "index.html",
        table_html=None,
        raw_matrix_html=None,
        error=None,
        detected_wells=[],
        missing_wells=[],
        reference_well=None,
        reference_label="",
        file_token=None,
        uploaded_filename=None,
        plate_type="96",
        illuminant_key="D65",
        observer_angle="2",
        plate_rows=list("ABCDEFGH"),
        plate_cols=list(range(1, 13)),
        wavelength_list=[],
        blank_input="",
        used_blanks=[],
        ref_target_preset="Buffer",
        custom_L=None,
        custom_a=None,
        custom_b=None,
        target_display="",
        reference_mode="lab",
        lambda_map={},
        hsv_map=app.config.get("HSV_MAP") or {},
        hyperspectral_map=app.config.get("HYPERSPECTRAL_MAP") or {},
        well_metadata={},
        metadata_filename=None,
    )

# =======================================
# In-memory fusion helper (no CSVs)
# =======================================
def build_fusion_table_from_dfs(spec_df: pd.DataFrame, hsv_df: pd.DataFrame):
    """
    Stateless fusion using in-memory dataframes.
    Adds basic QC flags + a simple fusion score.
    Returns (merged_df, stats_dict).
    """
    spec = spec_df.copy()
    hsv = hsv_df.copy()

    # identify DeltaE column
    delta_col = None
    for c in spec.columns:
        if str(c).lower().startswith("deltae"):
            delta_col = c
            break

    # merge
    merged = pd.merge(spec, hsv, on="Well", how="left")

    # numeric coercion
    for c in ["texture_score", "mean_saturation", "pixel_count"]:
        if c in merged.columns:
            merged[c] = pd.to_numeric(merged[c], errors="coerce")

    # QC flags (same thresholds you had; tweak anytime)
    texture_hi = 18.0
    sat_lo = 40.0
    sat_hi = 120.0
    pix_lo = 8000

    merged["qc_low_pixels"] = merged["pixel_count"].fillna(0) < pix_lo
    merged["qc_high_texture"] = merged["texture_score"] > texture_hi
    merged["qc_sat_low"] = merged["mean_saturation"] < sat_lo
    merged["qc_sat_high"] = merged["mean_saturation"] > sat_hi
    merged["qc_imaging_bad"] = (
        merged["qc_low_pixels"]
        | merged["qc_high_texture"]
        | merged["qc_sat_low"]
        | merged["qc_sat_high"]
    )

    def suggest(row):
        if pd.isna(row.get("texture_score")) and pd.isna(row.get("mean_saturation")):
            return "No image for this well."
        notes = []
        if bool(row.get("qc_low_pixels")):
            notes.append("ROI too small → reframe/closer.")
        if bool(row.get("qc_high_texture")):
            notes.append("High texture → glare/blur; use diffuser.")
        if bool(row.get("qc_sat_low")):
            notes.append("Low saturation → increase exposure.")
        if bool(row.get("qc_sat_high")):
            notes.append("High saturation → reduce exposure / lock WB.")
        return " ".join(notes) if notes else "Imaging looks stable."

    merged["imaging_suggestion"] = merged.apply(suggest, axis=1)

    # fusion score
    if delta_col and merged[delta_col].notna().any():
        d = pd.to_numeric(merged[delta_col], errors="coerce")
        denom = (float(d.max()) - float(d.min())) or 1.0
        merged["deltaE_norm"] = (d - float(d.min())) / denom
        stable = np.where(merged["qc_imaging_bad"].fillna(True), 0.4, 1.0)
        merged["fusion_score"] = np.clip(merged["deltaE_norm"].fillna(0) * stable, 0, 1)
    else:
        merged["deltaE_norm"] = np.nan
        merged["fusion_score"] = np.nan

    # diagnostics correlations (optional)
    stats = {}
    if delta_col:
        try:
            stats["corr_deltaE_texture"] = float(pd.to_numeric(merged[delta_col], errors="coerce").corr(merged["texture_score"]))
        except Exception:
            stats["corr_deltaE_texture"] = float("nan")
        try:
            stats["corr_deltaE_sat"] = float(pd.to_numeric(merged[delta_col], errors="coerce").corr(merged["mean_saturation"]))
        except Exception:
            stats["corr_deltaE_sat"] = float("nan")

    return merged, stats
# =====================================================
# MAIN INDEX ROUTE (UPLOAD + INITIAL RUN)
# =====================================================
@app.route("/", methods=["GET", "POST"])
def index():
    plate_type = "96"
    illuminant_key = "D65"
    observer_angle = "2"

    table_html = None
    raw_matrix_html = None
    error = None
    detected_wells = []
    missing_wells = []

    reference_well = None
    reference_label = "Buffer"

    file_token = None
    uploaded_filename = None
    metadata_filename = None
    wavelength_list = []

    blank_input = ""
    used_blanks = []
    ref_target_preset = "Buffer"
    custom_L = custom_a = custom_b = None
    reference_mode = "lab"

    target_lab_default = LAB_PRESETS["Buffer"]
    target_display = (
        f"L*={target_lab_default[0]:.2f}, "
        f"a*={target_lab_default[1]:.2f}, "
        f"b*={target_lab_default[2]:.2f}"
    )

    well_metadata = None
    df_results = None
    lambda_map = {}

    if request.method == "POST":
        # NEW RUN: clear old in-memory analysis outputs
        app.config.pop("LAST_RESULTS_DF", None)
        app.config.pop("LAST_HSV_DF", None)
        app.config.pop("LAST_FUSION_DF", None)
        # NEW RUN: clear old in-memory analysis outputs
        app.config.pop("LAST_LIGHTING_DF", None)
        app.config.pop("LIGHTING_MAP", None)

        plate_type = request.form.get("plate_type", plate_type)
        illuminant_key = request.form.get("illuminant_key", illuminant_key)
        observer_angle = request.form.get("observer_angle", observer_angle)

        reference_mode = request.form.get("reference_mode", "lab")
        reference_well = (request.form.get("reference_well") or "").strip() or None

        ref_target_preset = request.form.get("ref_target_preset", "Buffer")
        custom_L = request.form.get("custom_L")
        custom_a = request.form.get("custom_a")
        custom_b = request.form.get("custom_b")

        blank_input = request.form.get("blank_wells", "") or ""
        blank_list = [b.strip() for b in blank_input.split(",") if b.strip()]

        if reference_mode == "lab":
            if ref_target_preset == "Custom":
                try:
                    lab_target = (float(custom_L or 0), float(custom_a or 0), float(custom_b or 0))
                except Exception:
                    error = "Invalid custom L*a*b* values."
                    lab_target = None
            else:
                lab_target = LAB_PRESETS.get(ref_target_preset)
                if lab_target is None:
                    error = "Invalid Lab preset."
        else:
            lab_target = (100.0, 0.0, 0.0)

        uploaded = request.files.get("dataset")
        metadata_file = request.files.get("metadata_file")

        if (not uploaded or uploaded.filename == "") and not error:
            error = "Please upload a dataset (.xlsx, .xls, .csv)."

        if not error and uploaded and uploaded.filename:
            try:
                uploaded_filename = uploaded.filename
                token = make_token()
                ext = os.path.splitext(uploaded_filename)[1]
                data_path = os.path.join("uploads", token + ext)
                uploaded.save(data_path)
                file_token = token

                meta_path = None
                if metadata_file and metadata_file.filename:
                    meta_ext = os.path.splitext(metadata_file.filename)[1]
                    meta_path = os.path.join("uploads", f"{token}_meta{meta_ext}")
                    metadata_file.save(meta_path)
                    well_metadata, metadata_filename = build_well_metadata(meta_path, metadata_file.filename)

                pt = normalize_plate_type(plate_type)
                (
                    df_results,
                    detected_wells,
                    ref_well_used,
                    used_blanks,
                    delta_col,
                ) = process_plate(
                    excel_file=data_path,
                    reference_well=reference_well,
                    plate_type=pt,
                    illuminant_key=illuminant_key,
                    observer_angle_deg=float(observer_angle),
                    blank_wells=blank_list,
                    lab_target=lab_target,
                    reference_mode=reference_mode,
                )

                df_export = merge_results_with_metadata(df_results.copy(), well_metadata)
                app.config["LAST_RESULTS_DF"] = df_export

                table_html = dataframe_to_html(df_results)
                missing_wells = compute_missing_wells(detected_wells, pt)
                plate_type = pt

                df_raw, _ = get_raw_matrix(data_path)
                raw_matrix_html = dataframe_to_html(df_raw)
                wavelength_list = df_raw["Wavelength"].astype(float).tolist()

                if reference_mode == "lab":
                    reference_label = ref_target_preset
                    target_display = f"L*={lab_target[0]:.2f}, a*={lab_target[1]:.2f}, b*={lab_target[2]:.2f}"
                    reference_well = ref_well_used
                else:
                    reference_label = ref_well_used
                    target_display = f"Reference well: {ref_well_used}"
                    reference_well = ref_well_used

                try:
                    lambda_map = df_results.set_index("Well")["LambdaMax"].to_dict()
                except Exception:
                    lambda_map = {}

            except Exception as e:
                print("UPLOAD/PROCESS ERROR:", e)
                error = f"Error processing file: {str(e)}"

    plate_rows, plate_cols = get_plate_layout(plate_type)

    return render_template(
        "index.html",
        table_html=table_html,
        raw_matrix_html=raw_matrix_html,
        error=error,
        detected_wells=detected_wells or [],
        missing_wells=missing_wells or [],
        reference_well=reference_well,
        reference_label=reference_label,
        file_token=file_token,
        uploaded_filename=uploaded_filename,
        plate_type=plate_type,
        illuminant_key=illuminant_key,
        observer_angle=observer_angle,
        plate_rows=plate_rows or [],
        plate_cols=plate_cols or [],
        wavelength_list=wavelength_list or [],
        blank_input=blank_input,
        used_blanks=used_blanks or [],
        ref_target_preset=ref_target_preset,
        custom_L=custom_L,
        custom_a=custom_a,
        custom_b=custom_b,
        target_display=target_display,
        reference_mode=reference_mode,
        lambda_map=lambda_map or {},
        hsv_map=app.config.get("HSV_MAP") or {},
        hyperspectral_map=app.config.get("HYPERSPECTRAL_MAP") or {},
        well_metadata=well_metadata or {},
        metadata_filename=metadata_filename,
    )


# =====================================================
# RECALCULATE (NO NEW UPLOAD NEEDED)
# =====================================================
@app.route("/recalculate", methods=["POST"])
def recalculate():
    file_token = request.form.get("file_token")
    plate_type = request.form.get("plate_type", "96")
    illuminant_key = request.form.get("illuminant_key", "D65")
    observer_angle = request.form.get("observer_angle", "2")

    reference_mode = request.form.get("reference_mode", "lab")
    reference_well = (request.form.get("reference_well") or "").strip() or None

    ref_target_preset = request.form.get("ref_target_preset", "Buffer")
    custom_L = request.form.get("custom_L")
    custom_a = request.form.get("custom_a")
    custom_b = request.form.get("custom_b")

    uploaded_filename = request.form.get("uploaded_filename", "")

    if not file_token:
        return "Missing file token", 400

    dataset_path, meta_path = find_paths_for_token(file_token)
    if not dataset_path:
        return "Dataset missing", 404

    if reference_mode == "lab":
        if ref_target_preset == "Custom":
            try:
                lab_target = (float(custom_L or 0), float(custom_a or 0), float(custom_b or 0))
            except Exception:
                return "Invalid custom LAB", 400
        else:
            lab_target = LAB_PRESETS.get(ref_target_preset)
            if lab_target is None:
                return "Invalid reference target", 400
    else:
        lab_target = (100.0, 0.0, 0.0)

    blank_input = request.form.get("blank_wells", "") or ""
    blank_list = [b.strip() for b in blank_input.split(",") if b.strip()]

    pt = normalize_plate_type(plate_type)
    (
        df_results,
        detected_wells,
        ref_well_used,
        used_blanks,
        delta_col,
    ) = process_plate(
        excel_file=dataset_path,
        reference_well=reference_well,
        plate_type=pt,
        illuminant_key=illuminant_key,
        observer_angle_deg=float(observer_angle),
        blank_wells=blank_list,
        lab_target=lab_target,
        reference_mode=reference_mode,
    )

    well_metadata, metadata_filename = build_well_metadata(meta_path) if meta_path else (None, None)

    df_export = merge_results_with_metadata(df_results.copy(), well_metadata)
    app.config["LAST_RESULTS_DF"] = df_export
    # recalc invalidates downstream unless recomputed
    app.config.pop("LAST_FUSION_DF", None)

    table_html = dataframe_to_html(df_results)

    df_raw, _ = get_raw_matrix(dataset_path)
    raw_matrix_html = dataframe_to_html(df_raw)
    wavelength_list = df_raw["Wavelength"].astype(float).tolist()

    missing_wells = compute_missing_wells(detected_wells, pt)

    if reference_mode == "lab":
        reference_label = ref_target_preset
        target_display = f"L*={lab_target[0]:.2f}, a*={lab_target[1]:.2f}, b*={lab_target[2]:.2f}"
        reference_well = ref_well_used
    else:
        reference_label = ref_well_used
        target_display = f"Reference well: {ref_well_used}"
        reference_well = ref_well_used

    plate_rows, plate_cols = get_plate_layout(pt)

    lambda_map = {}
    try:
        lambda_map = df_results.set_index("Well")["LambdaMax"].to_dict()
    except Exception:
        lambda_map = {}

    return render_template(
        "index.html",
        table_html=table_html,
        raw_matrix_html=raw_matrix_html,
        error=None,
        detected_wells=detected_wells or [],
        missing_wells=missing_wells or [],
        reference_well=reference_well,
        reference_label=reference_label,
        file_token=file_token,
        uploaded_filename=uploaded_filename,
        plate_type=plate_type,
        illuminant_key=illuminant_key,
        observer_angle=observer_angle,
        plate_rows=plate_rows or [],
        plate_cols=plate_cols or [],
        wavelength_list=wavelength_list or [],
        blank_input=blank_input,
        used_blanks=used_blanks or [],
        ref_target_preset=ref_target_preset,
        custom_L=custom_L,
        custom_a=custom_a,
        custom_b=custom_b,
        target_display=target_display,
        reference_mode=reference_mode,
        lambda_map=lambda_map or {},
        hsv_map=app.config.get("HSV_MAP") or {},
        hyperspectral_map=app.config.get("HYPERSPECTRAL_MAP") or {},
        well_metadata=well_metadata or {},
        metadata_filename=metadata_filename,
    )

# =====================================================
# MULTI-WELL SPECTRA API
# =====================================================
@app.route("/spectra_multi")
def spectra_multi():
    token = request.args.get("token")
    wells_raw = request.args.get("wells")

    if not token or not wells_raw:
        return jsonify({"error": "Missing parameters"}), 400

    dataset_path, _ = find_paths_for_token(token)
    if not dataset_path:
        return jsonify({"error": "Dataset not found"}), 404

    wells = [w.strip() for w in wells_raw.split(",") if w.strip()]

    try:
        wavelengths, spectra = get_wells_spectra(dataset_path, wells)

        # Ensure JSON-serializable output
        wavelengths = [float(w) for w in wavelengths]

        formatted = []
        for w, arr in spectra.items():
            formatted.append({
                "well": w,
                "absorbance": [float(v) for v in arr]
            })

        return jsonify({
            "wavelengths": wavelengths,
            "spectra": formatted
        })

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

    try:
        wlA = float(request.form.get("wlA"))
        wlB = float(request.form.get("wlB"))
    except (TypeError, ValueError):
        return "Invalid wavelengths", 400

    op = request.form.get("operation")

    dataset_path, _ = find_paths_for_token(file_token)
    if not dataset_path:
        return "Dataset missing on server", 404

    df_raw, wells = get_raw_matrix(dataset_path)

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
# CSV / PDF EXPORTS (temp files only)
# =====================================================
@app.route("/download_csv", methods=["POST"])
def download_csv():
    df = app.config.get("LAST_RESULTS_DF")
    if df is None:
        return "No results to export", 400

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    df.to_csv(tmp.name, index=False)
    tmp.close()

    return send_file(
        tmp.name,
        as_attachment=True,
        download_name="plate_results.csv",
        mimetype="text/csv",
    )


@app.route("/download_pdf", methods=["POST"])
def download_pdf():
    df = app.config.get("LAST_RESULTS_DF")
    if df is None:
        return "No results to export", 400

    pdf_path = generate_pdf(df, title="Plate Results")
    return send_file(
        pdf_path,
        as_attachment=True,
        download_name="plate_results.pdf",
        mimetype="application/pdf",
    )


# =====================================================
# DEBUG VALIDATION (XYZ → Lab → ΔE self-check)
# =====================================================
@app.route("/debug_validate")
def debug_validate():
    import colour

    try:
        wavelengths = np.arange(380, 781, 5)
        trans = np.ones_like(wavelengths)

        illum = colour.SDS_ILLUMINANTS["D65"].copy().align(colour.SpectralShape(380, 780, 5))
        sample_sd = colour.SpectralDistribution(trans, illum.domain)

        XYZ_sample = colour.sd_to_XYZ(sample_sd, illuminant=illum)
        XYZ_white = colour.sd_to_XYZ(illum)
        Y_white = XYZ_white[1]
        XYZ_norm = (XYZ_sample / Y_white) * 100

        wp = colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"]
        Lab = colour.XYZ_to_Lab(XYZ_norm, wp)

        delta = float(colour.delta_E([100, 0, 0], Lab, method="CIE 2000"))
        status = "ok" if abs(delta) < 0.5 else "error"

        return jsonify(status=status, XYZ_raw=XYZ_sample.tolist(), XYZ_norm=XYZ_norm.tolist(), Lab=Lab.tolist(), deltaE=delta)
    except Exception as e:
        return jsonify(status="error", error=str(e))


# =====================================================
# HSV: show last HSV dataframe (in-memory only)
# =====================================================
@app.route("/get_hsv_results")
def get_hsv_results():
    df = app.config.get("LAST_HSV_DF")
    if df is None:
        return "<p class='text-muted small'>No HSV results.</p>"
    return df.to_html(classes="table table-sm table-striped", index=False, float_format="%.4f")
# =====================================================
# Get fusion results (JSON: core + diagnostics) — in-memory only
# =====================================================
@app.route("/get_fusion_results")
def get_fusion_results():
    spec_df = app.config.get("LAST_RESULTS_DF")
    if spec_df is None:
        return jsonify({"core": "<p class='text-muted small'>Run Spectral pipeline first.</p>", "diagnostics": ""})

    hsv_df = app.config.get("LAST_HSV_DF")
    if hsv_df is None:
        return jsonify({"core": "<p class='text-muted small'>Run HSV first.</p>", "diagnostics": ""})

    df, stats = build_fusion_table_from_dfs(spec_df=spec_df, hsv_df=hsv_df)
    app.config["LAST_FUSION_DF"] = df

    # --- CORE columns (clean UI) ---
    core_cols = [
        "Well",
        "DeltaE_vs_Target",
        "deltaE_norm",
        "texture_score",
        "mean_saturation",
        "pixel_count",
        "qc_imaging_bad",
        "imaging_suggestion",
        "fusion_score",
    ]
    core_cols = [c for c in core_cols if c in df.columns]
    core_df = df[core_cols].copy()

    # --- Diagnostics header ---
    lines = []
    for k, v in (stats or {}).items():
        try:
            if v != v:  # NaN
                lines.append(f"{k}: n/a")
            else:
                lines.append(f"{k}: {float(v):.3f}")
        except Exception:
            lines.append(f"{k}: n/a")

    diag_header = ""
    if lines:
        diag_header = f"""
        <div class="small text-muted mb-2">
          <b>Diagnostics:</b> {" | ".join(lines)}
        </div>
        """

    diag_table = df.to_html(
        classes="table table-sm table-striped table-hover align-middle",
        index=False,
        float_format="%.4f",
        border=0,
    )

    core_html = core_df.to_html(
        classes="table table-sm table-striped table-hover align-middle",
        index=False,
        float_format="%.4f",
        border=0,
    )

    return jsonify({"core": core_html, "diagnostics": diag_header + diag_table})


# =====================================================
# Fusion downloads (temp files only)
# =====================================================
@app.route("/download_fusion_csv")
def download_fusion_csv():
    df = app.config.get("LAST_FUSION_DF")
    if df is None:
        return "No fusion results yet", 400

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    df.to_csv(tmp.name, index=False)
    tmp.close()

    return send_file(
        tmp.name,
        as_attachment=True,
        download_name="fusion_results.csv",
        mimetype="text/csv",
    )


@app.route("/download_fusion_pdf")
def download_fusion_pdf():
    df = app.config.get("LAST_FUSION_DF")
    if df is None:
        return "No fusion results yet", 400

    pdf_path = generate_pdf(df, title="Fusion Results")
    return send_file(
        pdf_path,
        as_attachment=True,
        download_name="fusion_results.pdf",
        mimetype="application/pdf",
    )

@app.route("/download_hsv_lighting_csv")
def download_hsv_lighting_csv():
    df_hsv = app.config.get("LAST_HSV_DF")
    df_light = app.config.get("LAST_LIGHTING_DF")

    if df_hsv is None and df_light is None:
        return "No HSV or lighting results to export", 400

    rows = []

    # ---- HSV section ----
    if df_hsv is not None:
        for metric in ["texture_score", "mean_saturation", "pixel_count"]:
            row = {"Section": "HSV Texture", "Data set": metric}
            for _, r in df_hsv.iterrows():
                row[r["Well"]] = r.get(metric)
            rows.append(row)

    # ---- Lighting section ----
    if df_light is not None:
        lighting_metrics = [
            "mean_v", "pct_dark", "pct_bright", "exposure",
            "wb_bias", "white_balance", "uniformity_ratio",
            "uniformity", "glare", "lighting_score"
        ]
        for metric in lighting_metrics:
            row = {"Section": "Lighting Diagnostics", "Data set": metric}
            for _, r in df_light.iterrows():
                row[r["Well"]] = r.get(metric)
            rows.append(row)

    df_out = pd.DataFrame(rows)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    df_out.to_csv(tmp.name, index=False)
    tmp.close()

    return send_file(
        tmp.name,
        as_attachment=True,
        download_name="hsv_lighting_diagnostics.csv",
        mimetype="text/csv",
    )


# =====================================================
# Upload HSV Images + Run Processing (stateless per run)
# =====================================================
@app.route("/upload_hsv_images", methods=["POST"])
def upload_hsv_images():
    from werkzeug.utils import secure_filename
    from analysis.run_hsv_analysis import run_hsv_analysis
    from analysis.lighting_diagnostics import run_lighting_diagnostics

    upload_dir = "uploads/hsv_images"
    os.makedirs(upload_dir, exist_ok=True)

    # IMPORTANT: clear old images so each run is isolated
    for fname in os.listdir(upload_dir):
        fp = os.path.join(upload_dir, fname)
        if os.path.isfile(fp):
            try:
                os.remove(fp)
            except Exception:
                pass

    files = request.files.getlist("images")
    if not files:
        return "No images uploaded", 400

    for f in files:
        if not f or f.filename == "":
            continue
        filename = secure_filename(f.filename)
        f.save(os.path.join(upload_dir, filename))

    try:
        df_hsv = run_hsv_analysis(upload_dir)
        df_light = run_lighting_diagnostics(upload_dir)

        app.config["LAST_HSV_DF"] = df_hsv
        app.config["LAST_LIGHTING_DF"] = df_light

        app.config.pop("LAST_FUSION_DF", None)
        hsv_map = (
            df_hsv 
            .set_index("Well")[["mean_saturation", "texture_score", "pixel_count"]] 
            .to_dict(orient="index")
        )

        app.config["HSV_MAP"] = hsv_map
        
        lighting_map = (
            df_light
            .set_index("Well")[["lighting_score", "exposure", "white_balance", "glare"]]
            .to_dict(orient="index")
        )

        app.config["LIGHTING_MAP"] = lighting_map

        return jsonify({"status": "ok", "wells": len(hsv_map)})

    except Exception as e:
        print("HSV processing error:", e)
        return "HSV processing failed", 500
    
# =====================================================
# LIGHTING MAP
# =====================================================
@app.route("/get_lighting_results")
def get_lighting_results():
    df = app.config.get("LAST_LIGHTING_DF")
    if df is None:
        return "<p class='text-muted small'>No lighting analysis yet.</p>"

    return df.to_html(
        classes="table table-sm table-striped table-hover align-middle",
        index=False,
        float_format="%.3f",
        border=0,
    )

# =====================================================
# Upload Hyperspectral Plate Excel (standalone ingest)
# =====================================================
@app.route("/upload_hyperspectral_excel", methods=["POST"])
def upload_hyperspectral_excel():
    file = request.files.get("hyperspectral_excel")
    if not file or file.filename == "":
        return jsonify({"error": "No file uploaded"}), 400

    try:
        # Load hyperspectral Excel
        df = pd.read_excel(file)

        # Expect wide-format CV columns: A1_cv, A2_cv, ...
        cv_cols = [c for c in df.columns if str(c).lower().endswith("_cv")]

        if not cv_cols:
            return jsonify({
                "error": "No *_cv columns found. Expected columns like A1_cv, B3_cv, etc."
            }), 400

        hyperspectral_map = {}

        for col in cv_cols:
            well = col.replace("_cv", "").strip()
            vals = pd.to_numeric(df[col], errors="coerce")

            if vals.notna().any():
                hyperspectral_map[well] = float(vals.mean())

        if not hyperspectral_map:
            return jsonify({"error": "No valid CV data found"}), 400

        # Store for heatmap overlay
        app.config["HYPERSPECTRAL_MAP"] = hyperspectral_map

        return jsonify({
            "status": "ok",
            "wells": len(hyperspectral_map)
        })

    except Exception as e:
        print("Hyperspectral Excel upload error:", e)
        return jsonify({"error": str(e)}), 500

# =====================================================
# HSV MAP
# =====================================================
@app.route("/get_hsv_map")
def get_hsv_map():
    return jsonify(app.config.get("HSV_MAP", {}))
# =====================================================
# LIGHTING MAP
# =====================================================
@app.route("/get_lighting_map")
def get_lighting_map():
    return jsonify(app.config.get("LIGHTING_MAP", {}))

# =====================================================
# HYPERSPECTRAL MAP
# =====================================================
@app.route("/get_hyperspectral_map")
def get_hyperspectral_map():
    return jsonify(app.config.get("HYPERSPECTRAL_MAP", {}))

# =====================================================
# INTERNAL SELF-TEST ON STARTUP
# =====================================================
def run_internal_math_self_test():
    import colour

    try:
        wavelengths = np.arange(380, 781, 5)
        trans = np.ones_like(wavelengths)

        illum = colour.SDS_ILLUMINANTS["D65"].copy().align(colour.SpectralShape(380, 780, 5))
        sample_sd = colour.SpectralDistribution(trans, illum.domain)

        XYZ_raw = colour.sd_to_XYZ(sample_sd, illuminant=illum)
        XYZ_white = colour.sd_to_XYZ(illum)
        Y_white = XYZ_white[1]
        XYZ_norm = (XYZ_raw / Y_white) * 100

        wp = colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"]
        Lab = colour.XYZ_to_Lab(XYZ_norm, wp)

        delta = float(colour.delta_E(Lab, [100, 0, 0], method="CIE 2000"))
        assert abs(delta) < 0.5, f"ΔE too large: {delta}"
        print("✔ Internal math self-test passed.")
    except Exception as e:
        print("❌ Internal math self-test FAILED:", e)


# =====================================================
# MAIN ENTRY POINT
# =====================================================
if __name__ == "__main__":
    run_internal_math_self_test()
    start_hyperspectral_server()
    app.run(host="0.0.0.0", port=10000)
