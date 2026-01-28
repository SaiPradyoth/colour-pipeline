# 🎨 Spectral → Color → ΔE + λmax Pipeline

A technical but readable **web-based analysis pipeline** for converting **plate-reader absorbance spectra** into **per-well color metrics, quality control signals, and visual diagnostics**.

This tool is designed for scientists and engineers who work with **96-well spectral assays** and want a **clear, auditable bridge** between raw spectra and human-interpretable color + QC results.

---

## 🧠 What this project actually does

At its core, the app takes **absorbance vs wavelength data** and answers three practical questions:

1. **What color does each well correspond to (in a standard color space)?**  
2. **How different is each well from a reference or target (ΔE)?**  
3. **Are there visual or physical issues that spectra alone might miss?**

It does this by combining **color science**, **spectral analysis**, and **optional image-based QC** into a single, interactive workflow.

---

## 🔬 Core Outputs (per well)

### Spectral → Color
- **CIE XYZ** tristimulus values  
- **CIE Lab (L\*, a\*, b\*)** perceptual color coordinates
- **ΔE2000 color difference**
  - vs a **reference well** *or*
  - vs a **target Lab color** (preset or custom)

### Spectral Shape
- **λmax (peak wavelength)**
  - computed from **raw absorbance** (before blank subtraction)
  - preferentially restricted to the **visible range (~400–700 nm)**

### Visualization
- Plate-style **heatmaps** (ΔE, λmax, intensity-style views)
- **Interactive spectra plots** (single well or multi-well overlays)

---

## 🧪 Optional Image-Based QC (HSV)

If you upload well images (e.g. plate photos or cropped well images), the app can compute:

- Mean **HSV saturation**  
- **Texture score** (spatial variability proxy)  
- **Pixel count / fill consistency**

These image-derived metrics are then merged with spectral outputs to generate a:

### 🔗 Fusion QC Table
- Normalized spectral + image metrics
- QC flags
- A single **fusion score per well**

This helps catch cases where spectra look fine but wells are:
- partially filled
- visually inconsistent
- contaminated or uneven

---

## 🚀 Quick Start

### 1) Install dependencies
```bash
pip install -r requirements.txt
```
### 2) Run the app
python app.py
Open your browser at:

http://127.0.0.1:5000
No database is required. Results are stored in memory per session.

## 🔁 High-Level Pipeline Flow

1. Upload a **plate-reader spectral file** (`.csv`, `.xls`, `.xlsx`)
2. The loader:
   - auto-detects the wavelength column
   - identifies well columns (`A1–H12`)
3. *(Optional)* Blank wells are averaged and subtracted
4. Absorbance is converted to transmittance:

   **T = 10⁻ᴬ**

5. `colour-science` converts spectra → **XYZ → Lab**
6. **ΔE2000** is computed against:
   - a reference well, or
   - a target Lab color
7. **λmax** is detected from raw absorbance
8. Heatmaps, tables, and plots are generated
9. *(Optional)* HSV image QC and Fusion scoring are applied
10. Results are exported as **CSV or PDF**

---

## 📦 Input File Expectations

### Spectral file (required)
- Formats: `.csv`, `.xls`, `.xlsx`
- Must contain:
  - one wavelength column (e.g. `Wavelength`)
  - well columns named like `A1, A2, …, H12`

The loader automatically scans early rows to locate the true header, so instrument exports with metadata rows are supported.

### Metadata file (optional)
- Used to annotate wells with sample names, groups, concentrations, etc.
- Must contain a clear **well identifier column** (e.g. `Well = A1`)

---

## 🎛 Key Analysis Modes

### ΔE Reference Modes
- **Target Lab**: compare all wells to a fixed **L\*, a\*, b\*** target
- **Reference well**: compare all wells to a selected physical well

### Blank Subtraction
- User-specified blank wells are averaged per wavelength
- Subtracted from all wells
- Negative values are clipped to zero

### Ratio Engine
- Per-well wavelength math:
  - division
  - subtraction
  - normalized difference
- Useful for ratiometric assays or fast screening metrics

---

## 📄 Exports

You can download:
- **Spectral results** (CSV / PDF)
- **HSV image results** (CSV / PDF)
- **Fusion QC results** (CSV / PDF)

Reports are designed to be:
- lab-notebook friendly
- auditable
- easy to share

---

## 🛠 Technology Stack

- **Flask** – web application framework  
- **pandas / numpy** – data handling and numerics  
- **colour-science** – spectral colorimetry and ΔE2000  
- **OpenCV (headless)** – HSV and texture analysis  
- **matplotlib / Chart.js** – visualization  
- **ReportLab** – PDF generation  

---

## 🧩 Design Decisions (Intentional)

- **λmax is computed from raw absorbance** to preserve physical peak behavior
- Blank subtraction is optional and never affects λmax
- HSV image uploads overwrite previous image sets per session
- No persistent database by default (keeps the app lightweight and inspectable)

---

## 🧯 Common Issues

### No wells detected
- Ensure well columns follow standard naming (`A1`, `B12`, etc.)

### Invalid Lab target
- **L\***, **a\***, **b\*** must be numeric

### PDF export errors
- Ensure all spectral values are numeric
- Remove stray text from input files

---

## 🌱 Possible Extensions

- Spectral smoothing / derivatives
- Batch plate processing
- Multi-reference ΔE similarity matrices
- Persistent run history
- Headless API mode

---

## 🙌 Closing Note

This project exists to make **color change measurable, visible, and trustworthy**.

If an assay changes color, this pipeline helps you:
- quantify it
- visualize it
- and explain it with confidence.
