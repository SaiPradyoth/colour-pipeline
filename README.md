# 🎨 Spectral → Color → ΔE + λmax Analysis Pipeline  
*A simple, student-friendly tool for turning spectrometer data into color measurements.*

---

## 🌟 What This Project Does

This web app takes **96-well plate spectrometer data** (absorbance vs. wavelength) and converts it into:

- **CIE XYZ color values**
- **CIE Lab values (L*, a*, b*)**
- **ΔE2000 color differences**
- **λmax (peak wavelength) for each well**
- **Heatmaps** that show:
  - Color difference (ΔE)
  - Peak wavelength shift (λmax)
- **Downloadable PDF + CSV reports**
- **Clickable wells with metadata (sample name, AuNP amount, contents, etc.)**

It helps turn raw spectral data into **easy-to-understand visual color information.**

---

## 🧪 Why This Is Useful

Many biological and chemical samples change color when something important happens.

Example:  
**Gold nanoparticles (AuNPs) turn from red → purple → blue when they aggregate.**

This change shows up in two ways:

1. **The absorbance peak (λmax) shifts**  
2. **The color difference (ΔE) gets larger**

This tool automatically measures both and shows them on a heatmap so students and researchers can quickly understand what’s happening in each well.

---

## 🔬 How It Works (Simple Explanation)

1. You upload a spreadsheet from a plate reader  
2. The program finds the wavelength column (e.g., 350–800 nm)  
3. It reads each well’s absorbance spectrum  
4. It converts absorbance → transmittance  
5. Using the `colour-science` library, it calculates:
   - CIE XYZ
   - CIE Lab
6. It compares each well to:
   - A reference well (ΔE mode)  
   **or**
   - A reference wavelength (λmax mode)
7. It draws a heatmap showing differences between wells  
8. You can download a **PDF** or **CSV** with all results

---

## 🎛 Features

### ✔ Upload any `.xlsx`, `.xls`, or `.csv` spectral file  
The system automatically detects wells like A1, B3, H12, etc.

### ✔ Metadata support  
If you upload a metadata sheet, each well displays:

- Sample name  
- Category  
- AuNP amount  
- Contents  
- Row and column  

### ✔ Two heatmap modes  
- **ΔE2000** — how different each well’s color is  
- **λmax Shift** — how much the absorbance peak moves

### ✔ View spectra  
You can click a well and see its full absorbance curve.

### ✔ Professional PDF export  
With color-coded ΔE or λmax values.

---
🚧 Potential Future Upgrades
----------------------------

### 1️⃣ Automated λmax Trend Analysis  
- Detects shifts across rows/columns  
- Flags wells with unusual λmax patterns  
- Useful for AuNP–pathogen aggregation assays

### 2️⃣ Multi-Reference ΔE Comparison  
- Compare each well against **multiple reference wells**  
- Generate ΔE matrices (well vs. well)  
- Cluster wells based on color similarity

### 3️⃣ Machine-Learning Classification  
- Train models to classify samples based on:
  - Spectrum shape  
  - λmax  
  - ΔE fingerprints  
- Automatically detect pathogen-positive wells

### 4️⃣ Real-Time Streaming Mode  
- Accept sequential plate reads  
- Track color change over time  
- Plot kinetic λmax drift graphs

### 5️⃣ High-Resolution Spectral Smoothing  
- Add:
  - Savitzky–Golay smoothing  
  - Derivative spectrum visualization  
- Improves λmax accuracy in noisy datasets

### 6️⃣ Multi-Metadata Heatmap Layers  
- Switch heatmap view to:
  - Category  
  - Sample  
  - AuNP concentration  
  - Timepoint  
- Similar to GIS map layers but for biological plates

### 7️⃣ Smart Outlier Detection  
- Identify wells with impossible values:
  - Negative absorbance  
  - Non-physical XYZ  
  - ΔE spikes  
- Displays warnings in UI

### 8️⃣ Batch Processing Mode  
- Drop in a folder of spectrometer files  
- Automatically process all  
- Produce a combined lab-ready report

### 9️⃣ Cloud Storage & Versioning  
- Save each run with a unique ID  
- Pull up older plates for comparison  
- Great for longitudinal experiments

### 🔟 Export Raw Spectra to PDF  
- Each well gets a micro spectral plot  
- Useful for supplementary information in publications

### 1️⃣1️⃣ Enhanced Heatmap Color Scales  
- Add selectable presets:
  - “Viridis”  
  - “Inferno”  
  - “Scientific Rainbow”  
  - “Colorblind Safe”  

### 1️⃣2️⃣ Full API Mode  
- Let other software POST a dataset  
- Receive JSON containing:
  - Lab values  
  - ΔE  
  - λmax  
  - Metadata-integrated output

---
