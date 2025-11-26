# Spectral Color Analysis Pipeline

This repository contains Python tools to convert full spectroscopy absorbance data into standardized color spaces for precise, software-detectable color comparison.

## 🚀 Pipeline Overview
The full analytical pipeline implemented in this project is:


## 📌 Purpose
This project is designed for experiments where:
- Each sample produces a full absorbance spectrum (e.g., 96-well plates)
- Peaks differ by very small wavelength shifts (1 nm)
- The goal is to generate **unique color coordinates** detectable by software

By converting spectra into CIE Lab space, every sample receives a **unique numeric signature**, and ΔE allows reliable quantitative comparison.

## 📁 What This Repository Includes
- Python scripts for:
  - Loading spectrometer `.xlsx` datasets
  - Converting absorbance spectra → transmittance
  - Applying illuminant D65
  - Computing CIE XYZ from spectral distributions
  - Converting XYZ → CIE Lab
  - Calculating ΔE between wells/samples
- Simple examples to run the pipeline on one well or all 96 wells
- Instructions for extending to other datasets

## 🧪 Requirements
- Python 3.8+
- Packages:
  - `colour-science`
  - `pandas`
  - `openpyxl`
  - `numpy`

Install with:
```bash
pip install colour-science pandas openpyxl numpy
