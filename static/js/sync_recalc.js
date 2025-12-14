/*********************************************************
 SYNC RECALC HIDDEN FIELDS (plate/illum/observer)
*********************************************************/
function syncRecalc() {
  const pt  = document.getElementById("plate_type");
  const ill = document.getElementById("illuminant_key");
  const obs = document.getElementById("observer_angle");

  const r_pt  = document.getElementById("recalc_plate_type");
  const r_ill = document.getElementById("recalc_illuminant_key");
  const r_obs = document.getElementById("recalc_observer_angle");

  if (pt && r_pt)   r_pt.value  = pt.value;
  if (ill && r_ill) r_ill.value = ill.value;
  if (obs && r_obs) r_obs.value = obs.value;
}
["plate_type","illuminant_key","observer_angle"].forEach(id => {
  document.getElementById(id)?.addEventListener("change", syncRecalc);
});
syncRecalc();
