/*********************************************************
 CUSTOM LAB INPUTS (SHOW/HIDE)
*********************************************************/
function toggleCustomLabInputs() {
  const selectMain = document.getElementById("ref_target_preset");
  const divMain = document.getElementById("custom_lab_inputs");

  const selectRecalc = document.getElementById("ref_target_preset_recalc");
  const divRecalc = document.getElementById("custom_lab_inputs_recalc");

  if (divMain && selectMain) {
    divMain.style.display = selectMain.value === "Custom" ? "flex" : "none";
  }
  if (divRecalc && selectRecalc) {
    divRecalc.style.display = selectRecalc.value === "Custom" ? "flex" : "none";
  }

  const selector = selectRecalc || selectMain;
  const loadingMessage = document.getElementById('loading-target-message');
  if (loadingMessage && selector) {
    loadingMessage.textContent = `Target: ${selector.options[selector.selectedIndex].text.split('(')[0].trim()}`;
  }
}

toggleCustomLabInputs();
document.getElementById("ref_target_preset")?.addEventListener("change", toggleCustomLabInputs);
document.getElementById("ref_target_preset_recalc")?.addEventListener("change", toggleCustomLabInputs);
