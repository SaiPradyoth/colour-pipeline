/*********************************************************
 HSV → HUE EXPERIMENTAL MODE
 Non-destructive, isolated test (CORRECTED)
 Assumes backend uses:
 - circular ROI
 - percentile filtering inside ROI
 - OpenCV saturation scale (0–255)
*********************************************************/

/**
 * Convert HSV → RGB
 * h in degrees [0,360), s,v in [0,1]
 */
function hsvToRgb(h, s, v) {
  let c = v * s;
  let x = c * (1 - Math.abs((h / 60) % 2 - 1));
  let m = v - c;
  let r = 0, g = 0, b = 0;

  if (h < 60) [r, g, b] = [c, x, 0];
  else if (h < 120) [r, g, b] = [x, c, 0];
  else if (h < 180) [r, g, b] = [0, c, x];
  else if (h < 240) [r, g, b] = [0, x, c];
  else if (h < 300) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];

  return `rgb(${Math.round((r + m) * 255)},${Math.round(
    (g + m) * 255
  )},${Math.round((b + m) * 255)})`;
}

/**
 * Safe numeric helper
 */
function asNumber(x, fallback = NaN) {
  const n = Number(x);
  return Number.isFinite(n) ? n : fallback;
}

/**
 * Map HSV metrics → display hue
 * Plate-relative normalization of mean_saturation (OpenCV scale)
 */
function hsvHueColor(hsv) {
  if (!hsv || !window.HSV_MAP) return "#eee";

  const sats = Object.values(window.HSV_MAP)
    .map(v => asNumber(v?.mean_saturation))
    .filter(Number.isFinite);

  if (!sats.length) return "#eee";

  const minSat = Math.min(...sats);
  const maxSat = Math.max(...sats);

  const sat = asNumber(hsv.mean_saturation, minSat);
  const t = (sat - minSat) / ((maxSat - minSat) || 1);

  const hue = 220 - 220 * t; // blue → red
  return hsvToRgb(hue, 0.85, 0.95);
}

 /**
  * Entry point called from heatmap builder
  */
 function applyHSVHueHeatmap(cells) {
   if (!cells || !cells.length || !window.HSV_MAP) return;

   const textures = Object.values(window.HSV_MAP)
     .map(v => asNumber(v?.texture_score))
     .filter(Number.isFinite);

   const tMin = textures.length ? Math.min(...textures) : 0;
   const tMax = textures.length ? Math.max(...textures) : 1;

   cells.forEach(c => {
   const well = c.dataset.well;
   const hsv = window.HSV_MAP?.[well];
   if (!hsv) return;

   // QC-based background (binary, honest)
   const texClass = classifyTexture(hsv.texture_score);
   if (texClass === "bad" || texClass === "very bad") {
     c.style.background = "rgba(239,68,68,0.25)";   // red = unreliable
   } else {
     c.style.background = "rgba(34,197,94,0.20)";   // green = stable
   }

   const tex = asNumber(hsv.texture_score, tMin);
   const t = (tex - tMin) / ((tMax - tMin) || 1);

   c.onmouseenter = e => showHSVTooltip(e, hsv, well);
   c.onmousemove  = e => showHSVTooltip(e, hsv, well);
   c.onmouseleave = hideHSVTooltip;

   // Stronger, clearer texture visibility
   c.style.setProperty("--tex-opacity", (0.25 + t * 0.45).toFixed(2));
   c.style.setProperty("--tex-size", `${Math.max(2, 4.5 - t * 2.5)}px`);

   c.classList.add("hsv-textured");
 });
}

let hsvTooltip = null;

/**
 * Thresholds now match *your real data*
 * (OpenCV saturation scale, circular ROI)
 */
function classifySaturation(sat) {
  sat = asNumber(sat, 0);
  if (sat >= 180) return "excellent";
  if (sat >= 140) return "good";
  if (sat >= 100) return "moderate";
  if (sat >= 60)  return "bad";
  return "very bad";
}

function classifyTexture(tex) {
  tex = asNumber(tex, 0);
  if (tex <= 5)  return "excellent";
  if (tex <= 8)  return "good";
  if (tex <= 12) return "moderate";
  if (tex <= 20) return "bad";
  return "very bad";
}

function classifyPixels(px) {
  px = asNumber(px, 0);
  if (px >= 90000) return "excellent";
  if (px >= 60000) return "good";
  if (px >= 30000) return "moderate";
  if (px >= 15000) return "bad";
  return "very bad";
}

function showHSVTooltip(e, hsv, well) {
  if (!hsv) return;

  if (!hsvTooltip) {
    hsvTooltip = document.createElement("div");
    hsvTooltip.className = "hsv-tooltip";
    document.body.appendChild(hsvTooltip);
  }

  const sat = asNumber(hsv.mean_saturation, NaN);
  const tex = asNumber(hsv.texture_score, NaN);
  const px  = asNumber(hsv.pixel_count, NaN);

  hsvTooltip.innerHTML = `
    <div class="metric-row">
      <span class="metric-label">Sat</span>
      <span class="metric-value">${Number.isFinite(sat) ? sat.toFixed(1) : "n/a"}</span>
      <span class="metric-status">(${classifySaturation(sat)})</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Texture</span>
      <span class="metric-value">${Number.isFinite(tex) ? tex.toFixed(2) : "n/a"}</span>
      <span class="metric-status">(${classifyTexture(tex)})</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Pixels</span>
      <span class="metric-value">${Number.isFinite(px) ? px.toLocaleString() : "n/a"}</span>
      <span class="metric-status">(${classifyPixels(px)})</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Well</span>
      <span class="metric-value">${well}</span>
    </div>
  `;

  hsvTooltip.style.left = e.clientX + 12 + "px";
  hsvTooltip.style.top  = e.clientY + 12 + "px";
}

function hideHSVTooltip() {
  if (hsvTooltip) {
    hsvTooltip.remove();
    hsvTooltip = null;
  }
}
