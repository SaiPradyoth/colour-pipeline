/*********************************************************
 LOAD + PLOT SPECTRA
*********************************************************/
async function plotSpectra(){
  const token = document.getElementById("fileToken")?.value;
  const statusEl = document.getElementById("spectral-status");
  if (!token) {
    if (statusEl) statusEl.textContent = "Upload a dataset to view spectra.";
    return;
  }

  const wells = [...document.querySelectorAll(".spectral-well")]
      .filter(cb=>cb.checked)
      .map(cb=>cb.value);

  if (!wells.length) {
    if (statusEl) statusEl.textContent = "Select at least one well.";
    return;
  }

  try {
    if (statusEl) statusEl.textContent = "Loading spectra…";

    const res = await fetch(`/spectra_multi?token=${encodeURIComponent(token)}&wells=${encodeURIComponent(wells.join(","))}`);
    const data = await res.json();
    if (!res.ok || !data || !data.wavelengths) {
      if (statusEl) statusEl.textContent = data && data.error ? data.error : "Failed to load spectra.";
      return;
    }

    const series = data.spectra.map((obj, i) => ({
      label: obj.well,
      data: obj.absorbance,
      borderColor: pastelColor(i),
      tension: 0.25,
      pointRadius: 0,
      pointHitRadius: 8,
      fill: false
    }));

    drawSpectralChart(series,data.wavelengths);
    if (statusEl) statusEl.textContent = "Showing spectra for: " + wells.join(", ");
  } catch (e) {
    console.error(e);
    if (statusEl) statusEl.textContent = "Unexpected error.";
  }
}

document.getElementById("spectral-plot-btn")?.addEventListener("click", plotSpectra);
