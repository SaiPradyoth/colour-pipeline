/*********************************************************
 CANVAS EXPORT (solid background)
*********************************************************/
function getCanvasWithBackground(chartCanvas) {
  const htmlEl = document.documentElement;
  const theme = htmlEl.getAttribute("data-theme");
  const bg = theme === "dark" ? "#020617" : "#ffffff";

  const exportCanvas = document.createElement("canvas");
  exportCanvas.width = chartCanvas.width;
  exportCanvas.height = chartCanvas.height;

  const ctx = exportCanvas.getContext("2d");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, exportCanvas.width, exportCanvas.height);

  ctx.drawImage(chartCanvas, 0, 0);
  return exportCanvas;
}
