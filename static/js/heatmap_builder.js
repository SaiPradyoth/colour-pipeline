/*********************************************************
 HEATMAP BUILDER + COLOR / TEXTURE LOGIC
 Click-driven, no hover
*********************************************************/

/* =============================
   GLOBAL MAPS
============================= */
// NOTE: always read live map from window
function getHyperspectralMap() {
  return window.HYPERSPECTRAL_MAP || {};
}

/*********************************************************
 BUILD HEATMAP GRID
*********************************************************/
function buildHeatmap() {
  const grid = document.getElementById("heatmap-grid");
  if (!grid) return;

  const table = document.querySelector("#results-table table");
  if (!table) return;

  const headCells = [...table.querySelector("thead").querySelectorAll("th")];
  const rows = [...table.querySelector("tbody").querySelectorAll("tr")];

  const idxWell = headCells.findIndex(c =>
    c.textContent.trim().toLowerCase() === "well"
  );
  const idxDelta = headCells.findIndex(c =>
    /δe|Δe|delta/i.test(c.textContent)
  );
  if (idxWell === -1 || idxDelta === -1) return;

  /* -----------------------------
     Build ΔE lookup
  ----------------------------- */
  const deltaMap = {};
  rows.forEach(r => {
    const c = r.querySelectorAll("td");
    if (!c.length) return;
    const w = c[idxWell].textContent.trim();
    const d = parseFloat(c[idxDelta].textContent.trim());
    if (Number.isFinite(d)) deltaMap[w] = d;
  });

  /* -----------------------------
     Plate layout
  ----------------------------- */
  let rowLabels = [], colLabels = [];
  if (PLATE_TYPE === "48") {
    rowLabels = "ABCDEF".split("");
    colLabels = [...Array(8)].map((_, i) => i + 1);
  } else if (PLATE_TYPE === "384") {
    rowLabels = "ABCDEFGHIJKLMNOP".split("");
    colLabels = [...Array(24)].map((_, i) => i + 1);
  } else {
    rowLabels = "ABCDEFGH".split("");
    colLabels = [...Array(12)].map((_, i) => i + 1);
  }

  grid.style.gridTemplateColumns = `40px repeat(${colLabels.length}, 1fr)`;
  grid.innerHTML = "";

  /* -----------------------------
     Column headers
  ----------------------------- */
  grid.innerHTML += `<div class="heatmap-cell fw-semibold"></div>`;
  colLabels.forEach(c => {
    const h = document.createElement("div");
    h.className = "heatmap-cell fw-semibold";
    h.textContent = c;
    grid.appendChild(h);
  });

  /* -----------------------------
     Cells
  ----------------------------- */
  rowLabels.forEach(r => {
    const label = document.createElement("div");
    label.className = "heatmap-cell fw-semibold";
    label.textContent = r;
    grid.appendChild(label);

    colLabels.forEach(c => {
      const well = `${r}${c}`;
      const d = deltaMap[well];
      const cell = document.createElement("div");

      cell.className = "heatmap-cell";
      cell.dataset.well = well;

      if (Number.isFinite(d)) {
        cell.classList.add("filled");
        cell.dataset.delta = d;
        cell.dataset.baseValue = d.toFixed(1);          // 🔒 store original value
        cell.innerHTML = `<span class="cell-label">${cell.dataset.baseValue}</span>`;
        cell.onclick = () => showWellMetadata(well);
      } else {
        cell.textContent = "–";
      }

      grid.appendChild(cell);
    });
  });

  colorHeatmap();
  updateHeatmapLegend();
  applyMetadataFilters();
}

/*********************************************************
 ΔE2000 → blue palette
*********************************************************/
function deltaEBlueColor(t) {
  t = Math.min(Math.max(t, 0), 1);
  const hue = 210;
  const sat = 40 + t * 40;
  const light = 95 - t * 55;
  return `hsl(${hue}, ${sat}%, ${light}%)`;
}

/*********************************************************
 HYPERSPECTRAL → green → red palette
*********************************************************/
function hyperspectralCVColor(t) {
  t = Math.min(Math.max(t, 0), 1);
  const hue = 120 - t * 120;   // green → red
  const sat = 55;
  const light = 92 - t * 50;
  return `hsl(${hue}, ${sat}%, ${light}%)`;
}

/*********************************************************
 HSV TEXTURE OVERLAY (always applied if HSV exists)
*********************************************************/
function applyHSVTextureOnly(cells) {
  const textures = Object.values(window.HSV_MAP || {})
    .map(v => Number(v?.texture_score))
    .filter(Number.isFinite);

  if (!textures.length) return;

  const tMin = Math.min(...textures);
  const tMax = Math.max(...textures);

  cells.forEach(c => {
    const hsv = window.HSV_MAP?.[c.dataset.well];
    if (!hsv) return;

    const tex = Number(hsv.texture_score);
    if (!Number.isFinite(tex)) return;

    const t = (tex - tMin) / ((tMax - tMin) || 1);

    c.classList.add("hsv-textured");
    c.style.setProperty("--tex-opacity", (0.2 + t * 0.5).toFixed(2));
    c.style.setProperty("--tex-size", `${5 - t * 2.5}px`);
  });
}

/*********************************************************
 MAIN COLORING LOGIC
*********************************************************/
function colorHeatmap() {
  const mode = document.getElementById("heatmap-mode")?.value || "deltaE";
  const cells = document.querySelectorAll(".heatmap-cell.filled");
  if (!cells.length) return;

  /* FULL RESET */
  cells.forEach(c => {
    c.classList.remove("hsv-textured");
    c.style.removeProperty("--tex-opacity");
    c.style.removeProperty("--tex-size");
    c.style.background = "";
    c.style.color = "";
  });
  /* RESTORE BASE LABEL IF COMING FROM HYPERSPECTRAL */
  cells.forEach(c => {
    if (c.dataset.overlay === "hyperspectral") {
      const label = c.querySelector(".cell-label");
      if (label && c.dataset.baseValue) {
        label.textContent = c.dataset.baseValue;
      }
      delete c.dataset.overlay;
    }
  });

  /* Always apply HSV texture overlay */
  if (window.HSV_MAP && mode !== "hyperspectral") {
  applyHSVTextureOnly(cells);
  }

  /* HSV hue mode */
  if (mode === "hsv_hue" && typeof applyHSVHueHeatmap === "function") {
    applyHSVHueHeatmap(cells);
    return;
  }

  /* HYPERSPECTRAL MODE */
  if (mode === "hyperspectral") {
    const HMAP = getHyperspectralMap();

    const vals = [...cells]
      .map(c => Number(HMAP[c.dataset.well]))
      .filter(Number.isFinite);

    if (!vals.length) {
      console.warn("[HEATMAP] No hyperspectral values found");
      return;
    }

    const min = Math.min(...vals);
    const max = Math.max(...vals) || (min + 1);

    cells.forEach(c => {
      const v = Number(HMAP[c.dataset.well]);
      if (!Number.isFinite(v)) {
        c.style.background = "#e5e7eb";
        c.style.color = "#000";
        return;
      }
      const t = Math.min(v / 25, 1); // 0–25% CV mapped to green→red
      c.style.background = hyperspectralCVColor(t);
      c.style.color = t > 0.6 ? "#fff" : "#000";
      c.querySelector(".cell-label").textContent = v.toFixed(1);
      c.dataset.overlay = "hyperspectral";   // 🧠 mark as temporary
    });
    return;
  }

  /* λmax MODE */
  if (mode === "lambda") {
    cells.forEach(c => {
      const lam = LAMBDA_MAP?.[c.dataset.well];
      if (!Number.isFinite(lam)) {
        c.style.background = "#e5e7eb";
        c.style.color = "#000";
        return;
      }
      c.style.background = lambdaColor(lam);
      c.style.color = "#000";
    });
    return;
  }

  /* ΔE MODE (default) */
  const vals = [...cells].map(c => parseFloat(c.dataset.delta));
  let min = Math.min(...vals);
  let max = Math.max(...vals);
  if (max === min) max = min + 1e-6;

  cells.forEach(c => {
    const d = parseFloat(c.dataset.delta);
    const t = (d - min) / (max - min);
    c.style.background = deltaEBlueColor(t);
    c.style.color = t > 0.65 ? "#fff" : "#000";
  });
}

/* React to mode change */
document
  .getElementById("heatmap-mode")
  ?.addEventListener("change", () => {
    colorHeatmap();
    updateHeatmapLegend();
  });
function updateHeatmapLegend() {
  const mode = document.getElementById("heatmap-mode")?.value || "deltaE";
  document.querySelectorAll("#heatmap-legend .legend-block").forEach(el => {
    const m = el.dataset.mode;
    el.style.display = (!m || m === mode) ? "block" : "none";
  });
}
// 🔄 Recolor heatmap when hyperspectral data loads
function refreshHeatmapColors() {
  colorHeatmap();
  updateHeatmapLegend();
}

window.addEventListener("hyperspectral:loaded", refreshHeatmapColors);
