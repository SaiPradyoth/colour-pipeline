/*********************************************************
 METADATA PANEL + FILTERS
 Click-driven, no hover
*********************************************************/

/*********************************************************
 OVERALL QC LOGIC
*********************************************************/
function computeOverallQC({ deltaE, texture, pixels, sat }) {
  const reasons = [];

  /* ======================
     HARD FAIL CONDITIONS
  ====================== */
  if (texture === "very bad") {
    reasons.push("Texture");
  }

  if (Number.isFinite(pixels) && pixels < 25000) {
    reasons.push("Pixels");
  }

  if (Number.isFinite(sat) && sat < 40) {
    reasons.push("Saturation");
  }

  if (reasons.length) {
    return {
      status: "FAIL",
      reasons: reasons.map(r => `FAIL – ${r}`)
    };
  }

  /* ======================
     REVIEW CONDITIONS
  ====================== */
  const reviewFlags = [];

  if (texture === "bad") {
    reviewFlags.push("Texture");
  }

  if (Number.isFinite(pixels) && pixels >= 25000 && pixels < 40000) {
    reviewFlags.push("Pixels");
  }

  if (Number.isFinite(sat) && sat >= 40 && sat < 60) {
    reviewFlags.push("Saturation");
  }

  if (reviewFlags.length >= 1) {
    return {
      status: "REVIEW",
      reasons: reviewFlags.map(r => `REVIEW – ${r}`)
    };
  }

  /* ======================
     PASS
  ====================== */
  return {
    status: "PASS",
    reasons: ["All QC checks passed"]
  };
}

/*********************************************************
 QC BADGE RENDERER
*********************************************************/
function renderQCBadge(status) {
  const map = {
    PASS:   { cls: "bg-success", text: "PASS" },
    REVIEW: { cls: "bg-warning text-dark", text: "REVIEW" },
    FAIL:   { cls: "bg-danger", text: "FAIL" }
  };
  const b = map[status] || map.REVIEW;
  return `<span class="badge ${b.cls}">${b.text}</span>`;
}

/*********************************************************
 SAFE HSV TEXTURE CLASSIFIER (fallback)
*********************************************************/
function classifyTextureFallback(v) {
  v = Number(v);
  if (!Number.isFinite(v)) return "unknown";
  if (v < 0.3) return "smooth";
  if (v < 0.6) return "moderate";
  if (v < 0.85) return "bad";
  return "very bad";
}

/* ============================
   WELL DATA TILE RENDERER
============================ */
function showWellMetadata(wellId) {
  const bioTile   = document.getElementById("tile-biological");
  const specTile  = document.getElementById("tile-spectral");
  const hsvTile   = document.getElementById("tile-hsv");
  const hyperTile = document.getElementById("tile-hyperspectral");

  if (!bioTile || !specTile || !hsvTile || !hyperTile) return;

  const meta     = WELL_METADATA?.[wellId] || {};
  const spectral = window.SPECTRAL_MAP?.[wellId] || {};
  const hsv      = window.HSV_MAP?.[wellId] || {};
  const hyperVal = window.HYPERSPECTRAL_MAP?.[wellId];

  // Pull ΔE from heatmap cell (authoritative)
  const cell  = document.querySelector(`.heatmap-cell[data-well="${wellId}"]`);
  const delta = cell?.dataset?.delta ? Number(cell.dataset.delta) : null;
  const lam   = LAMBDA_MAP?.[wellId];

  const qc = computeOverallQC({
    deltaE: delta,
    texture: classifyTexture(hsv.texture_score),
    pixels: hsv.pixel_count || 0,
    sat: hsv.mean_saturation
  });

  /* ---------- BIOLOGICAL + QC ---------- */
  bioTile.innerHTML = `
    <div class="fw-semibold mb-1 d-flex justify-content-between align-items-center">
      Biological
      ${renderQCBadge(qc.status)}
    </div>
    <div class="small text-muted mb-2">
      ${qc.reasons.length ? qc.reasons.join(", ") : "All checks passed"}
    </div>

    <div><strong>Well:</strong> ${wellId}</div>
    <div><strong>Sample:</strong> ${meta.Sample || "—"}</div>
    <div><strong>Category:</strong> ${meta.Category || "—"}</div>
    <div><strong>Contents:</strong> ${meta.Contents || "—"}</div>
    <div><strong>AuNP:</strong> ${meta.AuNP || "—"}</div>
    <div class="small text-muted mt-1">${meta.MetadataSource || ""}</div>
  `;

  /* ---------- SPECTRAL ---------- */
  specTile.innerHTML = `
    <div class="fw-semibold mb-1">Spectral</div>
    <div>
      <strong>ΔE2000:</strong>
      ${Number.isFinite(delta) ? delta.toFixed(2) : "—"}
      <span class="text-muted">
        ${Number.isFinite(delta) ? "(" + classifyDelta(delta) + ")" : ""}
      </span>
    </div>
    <div>
      <strong>λmax:</strong>
      ${Number.isFinite(lam) ? lam + " nm" : "—"}
      <span class="text-muted">
        ${Number.isFinite(lam) ? classifyLambda(lam) : ""}
      </span>
    </div>
  `;

  /* ---------- HSV IMAGING ---------- */
  hsvTile.innerHTML = `
    <div class="fw-semibold mb-1">HSV Imaging</div>
    <div>
      <strong>Saturation:</strong>
      ${Number.isFinite(hsv.mean_saturation) ? hsv.mean_saturation.toFixed(1) : "—"}
    </div>
    <div>
      <strong>Texture:</strong>
      ${Number.isFinite(hsv.texture_score) ? classifyTexture(hsv.texture_score) : "—"}
    </div>
    <div>
      <strong>Pixels:</strong>
      ${Number.isFinite(hsv.pixel_count) ? hsv.pixel_count.toLocaleString() : "—"}
    </div>
  `;

  /* ---------- HYPERSPECTRAL ---------- */
  const hyperStatus =
    Number.isFinite(hyperVal)
      ? (hyperVal < 10 ? "Stable"
        : hyperVal < 20 ? "Moderate"
        : "Unstable")
      : null;

  hyperTile.innerHTML = `
    <div class="fw-semibold mb-1">Hyperspectral</div>
    <div>
      <strong>Mean CV%:</strong>
      ${Number.isFinite(hyperVal) ? hyperVal.toFixed(1) + "%" : "—"}
    </div>
    <div>
      <strong>Status:</strong>
      ${
        hyperStatus
          ? `<span class="${
              hyperStatus === "Stable"
                ? "text-success"
                : hyperStatus === "Moderate"
                ? "text-warning"
                : "text-danger"
            }">${hyperStatus}</span>`
          : "—"
      }
    </div>
  `;
}

/* ============================
   METADATA FILTERS
============================ */
function initMetadataFilters() {
  if (!WELL_METADATA) return;

  const allMeta = Object.values(WELL_METADATA);
  if (!allMeta.length) return;

  const fields = ["Category", "Sample", "AuNP", "Contents", "Row"];
  const valuesByField = {};
  fields.forEach(f => valuesByField[f] = new Set());

  allMeta.forEach(m => {
    fields.forEach(f => {
      const v = (m[f] ?? "").toString().trim();
      if (v) valuesByField[f].add(v);
    });
  });

  document.querySelectorAll(".meta-filter").forEach(sel => {
    const field = sel.dataset.field;
    if (!field || !valuesByField[field]) return;

    sel.innerHTML = `<option value="">All</option>`;
    Array.from(valuesByField[field]).sort().forEach(v => {
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = v;
      sel.appendChild(opt);
    });

    sel.addEventListener("change", applyMetadataFilters);
  });

  const clearBtn = document.getElementById("meta-filters-clear");
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      document.querySelectorAll(".meta-filter").forEach(sel => sel.value = "");
      applyMetadataFilters();
    });
  }
}

function applyMetadataFilters() {
  const cells = document.querySelectorAll(".heatmap-cell.filled");
  if (!cells.length) return;

  const filters = Array.from(document.querySelectorAll(".meta-filter"))
    .map(sel => ({
      field: sel.dataset.field,
      value: sel.value
    }));

  const anyActive = filters.some(f => f.value);

  cells.forEach(c => {
    const well = c.dataset.well;
    const meta = WELL_METADATA ? WELL_METADATA[well] : null;

    if (!anyActive) {
      c.style.opacity = "1";
      return;
    }

    // If filters are active and this well has no metadata → fade
    if (!meta) {
      c.style.opacity = "0.25";
      return;
    }

    const ok = matchesFilters(meta, filters);
    c.style.opacity = ok ? "1" : "0.25";
  });

}

function matchesFilters(meta, filters) {
  if (!meta && filters.some(f => f.value !== "")) return false;
  if (!meta) return true;

  for (const f of filters) {
    if (!f.value) continue;
    if ((meta[f.field] ?? "").toString() !== f.value) return false;
  }
  return true;
}

/* ============================
   CLASSIFIERS (TEXTUAL)
============================ */
function classifyDelta(d) {
  if (!Number.isFinite(d)) return "—";
  if (d < 2) return "negligible";
  if (d < 10) return "minor";
  if (d < 25) return "moderate";
  return "strong";
}

function classifyLambda(lam) {
  if (lam < 520) return "yellow shift";
  if (lam < 560) return "red shift";
  if (lam < 620) return "blue shift";
  return "deep blue";
}

/* ============================
   INIT
============================ */
document.addEventListener("DOMContentLoaded", () => {
  initMetadataFilters();
  if (typeof buildHeatmap === "function") {
    buildHeatmap();
  }
});
