<!--
  README.md — Spectral → Color Pipeline
  Tip: Add a banner image at /static/banner.png and uncomment the <img> tag below.
-->

<!-- <p align="center">
  <img src="static/banner.png" alt="Spectral → Color Pipeline" width="900">
</p> -->

<h1 align="center">🎨 Spectral → Color → ΔE + λmax Pipeline</h1>
<p align="center">
  <i>A friendly web app for turning plate-reader spectra into human-readable color + QC, with optional image validation.</i>
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-what-it-does">What it does</a> •
  <a href="#-how-it-works">How it works</a> •
  <a href="#-file-formats">File formats</a> •
  <a href="#-features">Features</a> •
  <a href="#-downloads--reports">Downloads</a> •
  <a href="#-troubleshooting">Troubleshooting</a>
</p>

<p align="center">
  <!-- Badges (edit as you like) -->
  <img alt="Python" src="https://img.shields.io/badge/Python-3.x-blue">
  <img alt="Flask" src="https://img.shields.io/badge/Flask-Web%20App-black">
  <img alt="colour-science" src="https://img.shields.io/badge/colour--science-Colorimetry-orange">
  <img alt="OpenCV" src="https://img.shields.io/badge/OpenCV-HSV%20Analysis-green">
  <img alt="PDF" src="https://img.shields.io/badge/ReportLab-PDF%20Export-purple">
</p>

---

## ✨ What it does

Upload a **96-well plate** spectrometer export (absorbance vs wavelength) and this app will generate:

### 🔬 Spectral → Color Metrics
- **CIE XYZ** tristimulus values  
- **CIE Lab (L\*, a\*, b\*)**
- **ΔE2000 color difference**
  - vs a **reference well** *or*
  - vs a **target Lab color** (preset or custom)
- **λmax** peak wavelength per well  
  - computed from **RAW absorbance** (intentionally un-subtracted)
  - restricted to the **visible region (≈400–700 nm)** when available

### 🧪 Optional Image Validation (HSV)
Upload well images to compute:
- **mean saturation**
- **texture score**
- **pixel count**

…and then combine imaging + spectral signals into a **Fusion QC table** with a single “fusion score” per well.

### 📊 Visualization + Export
- plate-style heatmaps (ΔE / λmax / intensity-style views)
- interactive spectra plots (single well + multi-well overlay)
- CSV + PDF exports (spectral results, HSV results, Fusion QC)

---

## 🚀 Quick Start

### 1) Install
```bash
pip install -r requirements.txt
```
2) Run the web app
```
python app.py
Open:  http://127.0.0.1:5000
```
#### 🧭 How it works (the short, readable version)
1. The pipeline in one breath:
2. You upload plate spectra
3. The app finds the wavelength header + well columns (A1–H12)
4. (Optional) blank wells are averaged and subtracted

Absorbance → transmittance via: 𝑇 = 10^−𝐴

5. colour-science converts spectra → XYZ → Lab
6. ΔE2000 is computed vs your chosen reference (well or Lab target)
7. λmax is detected from raw absorbance to track true peak behavior
8. Heatmaps + tables are generated
9. You export a clean report (CSV/PDF)
---

## 🧠 Pipeline Flow (Step-by-Step)

<details>
  <summary><b>🔍 View the full spectral → color → QC pipeline</b></summary>

<br>
A[Upload spectral file]
→ B[Detect header + wells (A1–H12)]
→ C{Blank wells provided?}

C →|Yes| D[Compute blank average per wavelength
Subtract from all wells
Clip negative values to 0]

C →|No| E[Skip blank subtraction]

D → F[Absorbance → Transmittance
T = 10^(-A)]

E → F

F → G[colour-science processing
Spectra → XYZ → Lab]

G → H{Reference mode}

H →|Target Lab| I[ΔE2000 vs Target Lab]

H →|Reference well| J[ΔE2000 vs Reference Well]

B → K[λmax detection
from RAW absorbance
(visible band if available)]

I → L[Heatmaps + tables + plots]
J → L
K → L

L → M[Export CSV / PDF]

L → N[Optional: Upload well images]

N → O[HSV analysis
Saturation + texture + pixel count]

O → P[Fusion QC table
Normalized metrics
QC flags
Combined fusion score]

P → M

</details>


---
📦 File formats
✅ Spectral dataset (required)
-  Accepted: .csv, .xls, .xlsx
-  Expected structure: One column labeled like Wavelength
-  Well columns named like: A1, A2, …, H12

If your file has extra header rows (common with instrument exports), no worries — the loader scans early rows to find the real header.

✅ Metadata sheet (optional): You can upload a metadata file to attach labels to wells (sample names, groups, concentrations, etc.).
The app maps metadata to wells and can display it alongside results.

-  Tip: keep a column that clearly identifies the well (like Well = A1, B4, etc.)

---

## 🎛 Features

<details>
  <summary><b>🎯 Reference Modes (ΔE)</b></summary>

<br>

**1️⃣ ΔE vs Target Lab (default)**  
Pick a preset target (e.g. *Buffer*) or enter a custom **L\*, a\*, b\***.

**2️⃣ ΔE vs Reference Well**  
Choose a well like **A1** as the reference — all wells are compared against it.

✅ This is helpful when your *true baseline* is a real well, not an abstract target.

</details>

---

<details>
  <summary><b>🧼 Blank Subtraction</b></summary>
  
<br>

Provide a comma-separated list of blank wells: A1, A2, A3

The app computes:
- Blank average spectrum = mean(blank wells) at each wavelength
- Subtracts from all wells
- Clips negative values to **0** (keeps things physically sane)

✅ Great for cleaning up background absorption.

</details>

---

<details>
  <summary><b>📈 Multi-Well Spectra Overlay</b></summary>

<br>

The app supports **multi-well spectral plotting** (overlay curves) via:
- The UI
- A JSON API endpoint

Useful for:
- Sanity-checking *weird wells*
- Comparing groups quickly
- Spotting saturation or unexpected peak shapes

</details>

---

<details>
  <summary><b>➗ Ratio Engine (Wavelength Math)</b></summary>

<br>

Compute quick per-well metrics by combining two wavelengths:

- Divide
- Subtract
- Normalized difference
- Average

Example use cases:
- Ratiometric assays
- *Signal vs baseline wavelength* scoring
- Rapid screening without full curve fitting

</details>

---

<details>
  <summary><b>📷 HSV Image Analysis + Fusion QC</b></summary>

<br>

Upload well images to extract:
- Mean saturation
- Texture score
- Pixel count

The app then merges **imaging + spectral results** into a **Fusion QC table** with:
- Normalized metrics
- QC flags
- A combined **fusion score**

Exports supported:
- Fusion CSV
- Fusion PDF

✅ This is a lifesaver when spectra look *fine* but wells are messy, partially filled, or visually inconsistent.

</details>

---

## 📄 Downloads & Reports

You can export:

- **Spectral results**
  - CSV
  - PDF

- **Fusion QC results**
  - CSV
  - PDF

Reports are designed to be:

- 🧪 Lab-notebook friendly  
- 📤 Easy to share  
- 🔍 Easy to audit later  

---

## 🛠 Tech Stack

- **Flask** — web framework  
- **pandas / numpy** — data handling and numerics  
- **colour-science** — spectral colorimetry (XYZ, Lab, ΔE2000)  
- **OpenCV (headless)** — HSV + texture analysis  
- **matplotlib / Chart.js** — visualization  
- **ReportLab** — PDF export  

---

## 🧩 Design Notes

- λmax is computed from **raw absorbance** on purpose  
  (peak behavior is most physically meaningful pre-subtraction)
- HSV image uploads overwrite previous image sets per run
- Results are stored **in memory per session**
- No database is required by default

---

## 🧯 Troubleshooting

### ❌ No wells detected

- Ensure well columns follow standard naming: A1, B12, H3, etc.
- Non-standard instrument exports may require minor parsing tweaks

### ❌ Invalid Lab target

- Custom **L\*, a\*, b\*** values must be numeric
- Example:

L* = 95
a* = 0
b* = 2

### ❌ PDF export issues

- Check for empty columns
- Ensure all spectral values are numeric
- Remove stray text or symbols from the input file

---

## 🌱 Ideas Brewing

- Spectral smoothing and derivative analysis
- Multi-reference ΔE similarity matrices
- Batch plate processing
- Persistent run history & versioning
- Simple API mode (POST → JSON results)

---

## 🙌 Closing Note

This project exists to make **color change feel obvious** — to bridge raw spectra and human intuition.
If your assay changes color, this pipeline helps you *measure it, see it, and trust it*.


