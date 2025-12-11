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

## 🖥 Running the Project Locally

### 1. Install required packages  
```bash
pip install -r requirements.txt
