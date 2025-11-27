# Spectral → Color → ΔE Analysis Pipeline  

A complete web-based system for converting **96-well plate spectrometer data** into **CIE XYZ**, **CIE Lab**, and **ΔE color difference metrics** — with a clean UI, downloadable reports, and automatic well detection.

---

## 🚀 Live Web Application  

Easily process any 96-well spectrometer `.xlsx` file online:

👉 **https://colour-pipeline.onrender.com**

No login required — anyone can upload a dataset and generate ΔE results instantly.

---

## 📌 What This System Does  

This project converts absorbance spectra into **software-detectable color coordinates** using the CIE colorimetric pipeline:

1. Reads full **absorbance spectra** from plate-reader `.xlsx` files  
2. Converts **Absorbance → Transmittance**  
3. Applies **CIE Illuminant D65**  
4. Computes **CIE XYZ** via spectral integration  
5. Converts XYZ → **CIE Lab**  
6. Calculates **ΔE** relative to a selected reference well  
7. Generates **downloadable reports**  
   - 📄 PDF  
   - 🧾 CSV  
8. Automatically extracts:  
   - ✔ Detected well IDs  
   - ✔ Missing/empty wells  
9. Provides UI control to **recalculate ΔE** using any reference well

This transforms high-resolution spectroscopic data into **unique color signatures** for each well.

---

## 🎯 Purpose  

This tool is designed for experiments where:

- Each sample has a *full absorbance spectrum*  
- Shifts as small as **1 nm** matter  
- Reliable and reproducible **numeric color differences** are needed  
- Visual inspection alone is insufficient  
- Batches produce many datasets that must be compared consistently  

By using CIE Lab space (a perceptually uniform color space), the system generates **stable, quantitative, software-detectable color markers**.

---

## 🧩 Features  

### 🔍 Spectral Processing  

- Auto-detects wavelength header  
- Auto-extracts valid well columns  
- Cleans noisy spreadsheets  
- Converts Absorbance → Transmittance → XYZ → Lab  

### 🎨 Color Analysis  

- Computes:  
  - X, Y, Z  
  - L*, a*, b*  
  - ΔE (via `colour-science`)  
- Lets you select any well as reference  
- Recalculates ΔE live without re-uploading  

### 🧪 96-Well Plate Support  

- Automatically detects:  
  - **Detected wells**  
  - **Missing wells**  
- Works with any subset of wells from A1–H12  

### 📥 Upload & Download  

- Upload `.xlsx` files  
- Download:  
  - **CSV results**  
  - **Professionally formatted PDF reports**  

### 🌐 Hosted Web App  

- Flask backend  
- Render.com deployment  
- Public and accessible  
- Auto-redeploy on GitHub push  

---

## 📁 Repository Structure  

```text
colour-pipeline/
│
├── app.py                # Flask web server
├── pipeline.py           # Core spectral → color → ΔE processing
├── templates/
│   └── index.html        # Front-end UI
├── uploads/              # Temporary uploaded files (runtime only)
├── results/              # Generated PDFs and CSVs (runtime only)
├── requirements.txt      # Python dependencies
├── README.md             # Documentation
└── LICENSE               # MIT License
