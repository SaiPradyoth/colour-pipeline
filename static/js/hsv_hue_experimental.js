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

    // Texture tuning (elegant + subtle)
    c.style.setProperty("--tex-opacity", (0.08 + t * 0.18).toFixed(2));
    c.style.setProperty("--tex-size", `${6 - t * 3}px`);

    c.classList.add("hsv-textured");
  });
}
