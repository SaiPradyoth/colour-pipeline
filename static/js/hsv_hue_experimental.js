/*********************************************************
 HSV → HUE EXPERIMENTAL MODE
 Non-destructive, isolated test
*********************************************************/

// Convert HSV → RGB (H in degrees, S,V in [0,1])
function hsvToRgb(h, s, v) {
  let c = v * s;
  let x = c * (1 - Math.abs((h / 60) % 2 - 1));
  let m = v - c;
  let r = 0, g = 0, b = 0;

  if (h < 60)      [r, g, b] = [c, x, 0];
  else if (h < 120)[r, g, b] = [x, c, 0];
  else if (h < 180)[r, g, b] = [0, c, x];
  else if (h < 240)[r, g, b] = [0, x, c];
  else if (h < 300)[r, g, b] = [x, 0, c];
  else             [r, g, b] = [c, 0, x];

  return `rgb(${Math.round((r+m)*255)},${Math.round((g+m)*255)},${Math.round((b+m)*255)})`;
}


// Map HSV metrics → display hue
function hsvHueColor(hsv) {
  if (!hsv) return "#eee";

  // Map saturation → hue range (blue → red)
  const sats = Object.values(HSV_MAP).map(v => v.mean_saturation);
  const minSat = Math.min(...sats);
  const maxSat = Math.max(...sats);
  const t = (hsv.mean_saturation - minSat) / ((maxSat - minSat) || 1);

  const hue = 220 - 220 * t;   // blue → red
  const s = 0.85;
  const v = 0.95;

  return hsvToRgb(hue, s, v);
}


// Entry point called from heatmap builder
function applyHSVHueHeatmap(cells) {
  const textures = Object.values(HSV_MAP).map(v => v.texture_score);
  const tMin = Math.min(...textures);
  const tMax = Math.max(...textures);

  cells.forEach(c => {
    const well = c.dataset.well;
    const hsv = HSV_MAP?.[well];
    if (!hsv) return;

    // Base HSV hue color
    c.style.background = hsvHueColor(hsv);

    // Relative texture strength (within plate)
    const t = (hsv.texture_score - tMin) / ((tMax - tMin) || 1);

    // Tooltip hooks
    c.onmouseenter = (e) => showHSVTooltip(e, hsv, well);
    c.onmousemove  = (e) => showHSVTooltip(e, hsv, well);
    c.onmouseleave = hideHSVTooltip;

    // Texture tuning (elegant + subtle)
    c.style.setProperty("--tex-opacity", (0.08 + t * 0.18).toFixed(2));
    c.style.setProperty("--tex-size", `${6 - t * 3}px`);

    c.classList.add("hsv-textured");
  });
}
let hsvTooltip = null;

function classifySaturation(sat) {
  if (sat >= 80) return "excellent";
  if (sat >= 65) return "good";
  if (sat >= 50) return "moderate";
  if (sat >= 35) return "bad";
  return "very bad";
}

function classifyTexture(tex) {
  if (tex <= 6) return "excellent";
  if (tex <= 10) return "good";
  if (tex <= 16) return "moderate";
  if (tex <= 25) return "bad";
  return "very bad";
}

function classifyPixels(px) {
  if (px >= 90000) return "excellent";
  if (px >= 80000) return "good";
  if (px >= 65000) return "moderate";
  if (px >= 50000) return "bad";
  return "very bad";
}

function showHSVTooltip(e, hsv, well) {
  if (!hsv) return;

  if (!hsvTooltip) {
    hsvTooltip = document.createElement("div");
    hsvTooltip.className = "hsv-tooltip";
    document.body.appendChild(hsvTooltip);
  }
const satStatus = classifySaturation(hsv.mean_saturation);
const texStatus = classifyTexture(hsv.texture_score);
const pixStatus = classifyPixels(hsv.pixel_count);

  hsvTooltip.innerHTML = `
  <div class="metric-row">
    <span class="metric-label">Sat</span>
    <span class="metric-value">${hsv.mean_saturation.toFixed(1)}</span>
    <span class="metric-status">(${satStatus})</span>
  </div>
  <div class="metric-row">
    <span class="metric-label">Texture</span>
    <span class="metric-value">${hsv.texture_score.toFixed(1)}</span>
    <span class="metric-status">(${texStatus})</span>
  </div>
  <div class="metric-row">
    <span class="metric-label">Pixels</span>
    <span class="metric-value">${hsv.pixel_count.toLocaleString()}</span>
    <span class="metric-status">(${pixStatus})</span>
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
