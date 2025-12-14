/*********************************************************
 WELL LIST HELPERS (for blank + reference dropdowns)
*********************************************************/
function getWellListForDropdowns() {
  if (Array.isArray(DETECTED_WELLS) && DETECTED_WELLS.length) {
    return DETECTED_WELLS.slice();
  }
  if (Array.isArray(PLATE_ROWS) && Array.isArray(PLATE_COLS) &&
      PLATE_ROWS.length && PLATE_COLS.length) {
    const wells = [];
    PLATE_ROWS.forEach(r => {
      PLATE_COLS.forEach(c => {
        wells.push(`${r}${c}`);
      });
    });
    return wells;
  }
  return [];
}

function populateMultiSelect(selectEl, wells, selectedList) {
  if (!selectEl) return;
  selectEl.innerHTML = "";
  wells.forEach(w => {
    const opt = document.createElement("option");
    opt.value = w;
    opt.textContent = w;
    if (selectedList && selectedList.includes(w)) {
      opt.selected = true;
    }
    selectEl.appendChild(opt);
  });
}

function populateSingleSelect(selectEl, wells, selectedValue) {
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
    if (selectedValue && selectedValue === w) {
      opt.selected = true;
    }
    selectEl.appendChild(opt);
  });
}

function parseBlankString(str) {
  if (!str) return [];
  return str.split(",").map(s => s.trim()).filter(Boolean);
}

function initWellDropdowns() {
  const wells = getWellListForDropdowns();

  const existingBlank = parseBlankString(BLANK_INPUT);
  const blankUpload = document.getElementById("blank_wells_select_upload");
  const blankRecalc = document.getElementById("blank_wells_select_recalc");
  const blankUploadHidden = document.getElementById("blank_wells_input_upload");
  const blankRecalcHidden = document.getElementById("blank_wells_input_recalc");

  populateMultiSelect(blankUpload, wells, existingBlank);
  populateMultiSelect(blankRecalc, wells, existingBlank);

  function syncBlank(selectEl, hiddenInput) {
    if (!selectEl || !hiddenInput) return;
    const vals = Array.from(selectEl.selectedOptions).map(o => o.value);
    hiddenInput.value = vals.join(", ");
  }

  if (blankUpload && blankUploadHidden) {
    blankUpload.addEventListener("change", () => syncBlank(blankUpload, blankUploadHidden));
    syncBlank(blankUpload, blankUploadHidden);
  }
  if (blankRecalc && blankRecalcHidden) {
    blankRecalc.addEventListener("change", () => syncBlank(blankRecalc, blankRecalcHidden));
    syncBlank(blankRecalc, blankRecalcHidden);
  }

  // Reference well selects
  const refUpload = document.getElementById("reference_well_select_upload");
  const refRecalc = document.getElementById("reference_well_select_recalc");

  const refUploadSel = refUpload?.getAttribute("data-selected-reference") || "";
  const refRecalcSel = refRecalc?.getAttribute("data-selected-reference") || "";

  populateSingleSelect(refUpload, wells, refUploadSel);
  populateSingleSelect(refRecalc, wells, refRecalcSel);
}

initWellDropdowns();
