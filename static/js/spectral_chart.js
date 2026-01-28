/*********************************************************
 SPECTRAL CHART
*********************************************************/

/* Explicit globals */
let spectralChart = null;
const htmlEl = document.documentElement;

/* Pastel color palette */
function pastelColor(i) {
  return [
    "#60a5fa", "#f472b6", "#34d399", "#fcd34d",
    "#a78bfa", "#f87171", "#4ade80", "#38bdf8", "#fbbf24"
  ][i % 9];
}

/* Draw chart */
function drawSpectralChart(series, wavelengths) {
  const canvas = document.getElementById("spectral-chart");
  if (!canvas || typeof Chart === "undefined") {
    console.log("Chart:", typeof Chart);
    console.warn("[SPECTRAL] Chart.js not available or canvas missing");
    return;
  }

  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  if (spectralChart) {
    spectralChart.destroy();
    spectralChart = null;
  }

  const theme = htmlEl.getAttribute("data-theme");
  const textColor = theme === "dark" ? "#e5e7eb" : "#0f172a";
  const gridColor =
    theme === "dark"
      ? "rgba(148,163,184,0.35)"
      : "rgba(148,163,184,0.50)";

  spectralChart = new Chart(ctx, {
  type: "line",
  data: {
    datasets: series
  },
  options: {
    parsing: false,
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: "index",
      intersect: false
    },
    plugins: {
      legend: {
        labels: { color: textColor }
      },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const y = ctx.parsed?.y;
            return Number.isFinite(y)
              ? `${ctx.dataset.label}: ${y.toFixed(4)}`
              : "";
          }
        }
      }
    },
    scales: {
      x: {
        type: "linear",
        title: { display: true, text: "Wavelength (nm)", color: textColor },
        ticks: { color: textColor },
        grid: { color: gridColor }
      },
      y: {
        title: { display: true, text: "Absorbance", color: textColor },
        ticks: { color: textColor },
        grid: { color: gridColor }
      }
    }
  }
});

}

/* Theme update */
function updateChartTheme() {
  if (!spectralChart) return;

  const theme = htmlEl.getAttribute("data-theme");
  const textColor = theme === "dark" ? "#e5e7eb" : "#0f172a";
  const gridColor =
    theme === "dark"
      ? "rgba(148,163,184,0.35)"
      : "rgba(148,163,184,0.50)";

  const o = spectralChart.options;
  if (!o?.scales) return;

  o.scales.x.title.color = textColor;
  o.scales.y.title.color = textColor;
  o.scales.x.ticks.color = textColor;
  o.scales.y.ticks.color = textColor;
  o.scales.x.grid.color = gridColor;
  o.scales.y.grid.color = gridColor;
  o.plugins.legend.labels.color = textColor;

  spectralChart.update("none");
}
