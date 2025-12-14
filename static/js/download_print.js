/*********************************************************
 DOWNLOAD PNG / PRINT GRAPH
*********************************************************/
document.getElementById("spectral-download-btn")?.addEventListener("click", () => {
  if (!spectralChart) return;
  const exportCanvas = getCanvasWithBackground(spectralChart.canvas);
  const url = exportCanvas.toDataURL("image/png");
  const a = document.createElement("a");
  a.href = url;
  a.download = "spectral_curves.png";
  a.click();
});

document.getElementById("spectral-print-btn")?.addEventListener("click", () => {
  if (!spectralChart) return;
  const exportCanvas = getCanvasWithBackground(spectralChart.canvas);
  const url = exportCanvas.toDataURL("image/png");
  const win = window.open("", "_blank");
  if (!win) return;
  win.document.write(`
    <html><head><title>Spectral Graph</title></head>
    <body style="margin:0; background:white;">
      <img id="print-image" src="${url}" style="width:100%; max-width:100%;">
    </body></html>
  `);
  win.document.close();
  const img = win.document.getElementById("print-image");
  if (img) {
    img.onload = () => {
      win.focus();
      win.print();
    };
  } else {
    win.focus();
    win.print();
  }
});
