/*********************************************************
 λmax → biologically meaningful diverging palette
 Blue (short λ) → Neutral → Red (long λ)
*********************************************************/
function lambdaColor(lambda) {
  if (!lambda || isNaN(lambda)) return "#e5e7eb";

  // Reference point for AuNP (typical red)
  const ref = 520; // nm
  const span = 80; // sensitivity window

  // Normalize shift
  let t = (lambda - ref) / span;
  t = Math.max(-1, Math.min(1, t)); // clamp

  // Blue shift → blue, Red shift → red
  if (t < 0) {
    const k = Math.abs(t);
    return `hsl(210, ${40 + k * 40}%, ${90 - k * 40}%)`; // light → deep blue
  } else {
    return `hsl(0, ${40 + t * 40}%, ${90 - t * 40}%)`;   // light → deep red
  }
}