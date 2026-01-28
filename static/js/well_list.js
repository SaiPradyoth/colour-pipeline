/*********************************************************
 WELL LIST HELPERS (for blank + reference dropdowns)
 Safe against missing globals + DOM timing
*********************************************************/

function getWellListForDropdowns() {
  // 1️⃣ Prefer plate layout (works before and after run)
  if (
    Array.isArray(window.PLATE_ROWS) &&
    Array.isArray(window.PLATE_COLS) &&
    window.PLATE_ROWS.length &&
    window.PLATE_COLS.length
  ) {
    const wells = [];
    window.PLATE_ROWS.forEach(r => {
      window.PLATE_COLS.forEach(c => {
        wells.push(`${r}${c}`);
      });
    });
    return wells;
  }

  // 2️⃣ Fallback: detected wells (post-run safety)
  if (
    Array.isArray(window.DETECTED_WELLS) &&
    window.DETECTED_WELLS.length
  ) {
    return window.DETECTED_WELLS.slice();
  }

  // 3️⃣ Final fallback: standard 96-well plate
  const rows = "ABCDEFGH".split("");
  const cols = Array.from({ length: 12 }, (_, i) => i + 1);
  return rows.flatMap(r => cols.map(c => `${r}${c}`));
}

function populateMultiSelect(selectEl, wells, selectedList = []) {
  if (!selectEl) return;
  selectEl.innerHTML = "";

  wells.forEach(w => {
    const opt = document.createElement("option");
    opt.value = w;
    opt.textContent = w;
    if (selectedList.includes(w)) opt.selected = true;
    selectEl.appendChild(opt);
  });
}

function populateSingleSelect(selectEl, wells, selectedValue = "") {
  if (!selectEl) return;
  selectEl.innerHTML = "";

  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "None";
  selectEl.appendChild(empty);

  wells.forEach(w => {
    const opt = document.createElement("option");
    opt.value = w;
    opt.textContent = w;
    if (w === selectedValue) opt.selected = true;
    selectEl.appendChild(opt);
  });
}

function parseBlankString(str) {
  if (!str || typeof str !== "string") return [];
  return str.split(",").map(s => s.trim()).filter(Boolean);
}

function initWellDropdowns() {
  const wells = getWellListForDropdowns();
  if (!wells.length) return;

  const existingBlank = parseBlankString(window.BLANK_INPUT || "");

  const blankUpload        = document.getElementById("blank_wells_select_upload");
  const blankRecalc        = document.getElementById("blank_wells_select_recalc");
  const blankUploadHidden  = document.getElementById("blank_wells_input_upload");
  const blankRecalcHidden  = document.getElementById("blank_wells_input_recalc");

  populateMultiSelect(blankUpload, wells, existingBlank);
  populateMultiSelect(blankRecalc, wells, existingBlank);

  function syncBlank(selectEl, hiddenInput) {
    if (!selectEl || !hiddenInput) return;
    const vals = Array.from(selectEl.selectedOptions).map(o => o.value);
    hiddenInput.value = vals.join(", ");
  }

  if (blankUpload && blankUploadHidden) {
    blankUpload.addEventListener("change", () =>
      syncBlank(blankUpload, blankUploadHidden)
    );
    syncBlank(blankUpload, blankUploadHidden);
  }

  if (blankRecalc && blankRecalcHidden) {
    blankRecalc.addEventListener("change", () =>
      syncBlank(blankRecalc, blankRecalcHidden)
    );
    syncBlank(blankRecalc, blankRecalcHidden);
  }

  // Reference well selects
  const refUpload = document.getElementById("reference_well_select_upload");
  const refRecalc = document.getElementById("reference_well_select_recalc");

  const refUploadSel =
    refUpload?.getAttribute("data-selected-reference") || "";
  const refRecalcSel =
    refRecalc?.getAttribute("data-selected-reference") || "";

  populateSingleSelect(refUpload, wells, refUploadSel);
  populateSingleSelect(refRecalc, wells, refRecalcSel);
  /* ---- FORCE SYNC BLANK WELLS ON SUBMIT (UPLOAD) ---- */
  const uploadForm = document.getElementById("upload-form");
  if (uploadForm && blankUpload && blankUploadHidden) {
    uploadForm.addEventListener("submit", () => {
      const vals = Array.from(blankUpload.selectedOptions).map(o => o.value);
      blankUploadHidden.value = vals.join(", ");
    });
  }

}

/* INIT — wait for DOM */
document.addEventListener("DOMContentLoaded", initWellDropdowns);

// Rebuild wells when plate type changes (pre-run support)
document
  .getElementById("plate_type")
  ?.addEventListener("change", () => {
    setTimeout(() => {
      if (typeof initWellDropdowns === "function") {
        initWellDropdowns();
      }
    }, 50);
  });

  // Re-init dropdowns when navigating to Dashboard / Upload page
  document.addEventListener("page:changed", (e) => {
    if (e.detail?.page === "dashboard") {
      setTimeout(initWellDropdowns, 0);
    }
  });
