/*********************************************************
 HEATMAP BUILDER + METADATA
*********************************************************/
function buildHeatmap() {
  const grid = document.getElementById("heatmap-grid");
  if (!grid) return;

  const table = document.querySelector("#results-table table");
  if (!table) return;

  const headCells = [...table.querySelector("thead").querySelectorAll("th")];
  const rows = [...table.querySelector("tbody").querySelectorAll("tr")];

  const idxWell = headCells.findIndex(c => c.textContent.trim().toLowerCase() === "well");
  const idxDelta = headCells.findIndex(c =>
    c.textContent.trim().toLowerCase().startsWith("deltae")
  );
  if (idxWell === -1 || idxDelta === -1) return;

  const deltaMap = {};
  rows.forEach(r => {
    const c = r.querySelectorAll("td");
    if (!c.length) return;
    const w = c[idxWell].textContent.trim();
    const d = parseFloat(c[idxDelta].textContent.trim());
    if (!isNaN(d)) {
      deltaMap[w] = d;
    }
  });

  const plateType = PLATE_TYPE;
  let rowLabels = [], colLabels = [];

  if (plateType === "48") {
    rowLabels = "ABCDEF".split("");
    colLabels = [...Array(8)].map((_,i)=>i+1);
  } else if (plateType === "384") {
    rowLabels = "ABCDEFGHIJKLMNOP".split("");
    colLabels = [...Array(24)].map((_,i)=>i+1);
  } else {
    rowLabels = "ABCDEFGH".split("");
    colLabels = [...Array(12)].map((_,i)=>i+1);
  }

  grid.style.gridTemplateColumns = `40px repeat(${colLabels.length},1fr)`;
  grid.innerHTML = "";

  // Corner
  grid.innerHTML += `<div class="heatmap-cell fw-semibold"></div>`;
  // Column headers
  colLabels.forEach(c => {
    const h = document.createElement("div");
    h.className = "heatmap-cell fw-semibold";
    h.textContent = c;
    grid.appendChild(h);
  });

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

      if (d != null) {
        cell.classList.add("filled");
        cell.dataset.delta = d;
        cell.textContent = d.toFixed(1);
        cell.onclick = () => {
          showWellMetadata(well);
        };
      } else {
        cell.textContent = "–";
      }

      grid.appendChild(cell);
    });
  });

  colorHeatmap();
  applyMetadataFilters();
}

function colorHeatmap() {
  const mode = document.getElementById("heatmap-mode")?.value || "deltaE";
  const cells = document.querySelectorAll(".heatmap-cell.filled");
  if (!cells.length) return;

  // λ_max MODE
  if (mode === "lambda") {
    cells.forEach(c => {
      let w = c.dataset.well;
      let lam = LAMBDA_MAP[w];
      if (!lam) return;
      c.style.background = lambdaColor(lam);
      c.style.color = "#000";
    });
    return;
  }

  // ΔE2000 MODE
  const vals = [...cells].map(c => parseFloat(c.dataset.delta));
  let min = Math.min(...vals);
  let max = Math.max(...vals);
  if (max === min) max = min + 1e-6;

  cells.forEach(c => {
    const t = (parseFloat(c.dataset.delta) - min) / (max - min);
    const hue = 220 - 220*t;
    const sat = 80;
    const light = 85 - 20*t;
    c.style.background = `hsl(${hue},${sat}%,${light}%)`;
    c.style.color = light < 50 ? "#fff" : "#000";
  });
}
// STEP 3E — Change mode → recolor heatmap
document.getElementById("heatmap-mode")?.addEventListener("change", () => {
  colorHeatmap();
});
