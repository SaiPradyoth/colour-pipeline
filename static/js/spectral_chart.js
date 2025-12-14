/*********************************************************
 SPECTRAL CHART
*********************************************************/
function pastelColor(i){
  return [
    "#60a5fa","#f472b6","#34d399","#fcd34d",
    "#a78bfa","#f87171","#4ade80","#38bdf8","#fbbf24"
  ][i%9];
}

function drawSpectralChart(series,wavelengths){
  const canvas = document.getElementById("spectral-chart");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  if (spectralChart) spectralChart.destroy();

  const theme = htmlEl.getAttribute("data-theme");
  const textColor = theme==="dark" ? "#e5e7eb" : "#0f172a";
  const gridColor = theme === "dark"
      ? "rgba(148,163,184,0.35)"
      : "rgba(148,163,184,0.50)";

  spectralChart = new Chart(ctx,{
    type:"line",
    data:{
      labels:wavelengths,
      datasets:series
    },
    options:{
      responsive:true,
      maintainAspectRatio:false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins:{
        legend:{labels:{color:textColor}},
        tooltip:{
          callbacks:{
            label:(ctx) => {
              const y = ctx.parsed.y;
              if (y == null || isNaN(y)) return "";
              return `${ctx.dataset.label}: ${y.toFixed(4)}`;
            }
          }
        }
      },
      scales:{
        x:{
          title:{display:true,text:"Wavelength (nm)",color:textColor},
          ticks:{color:textColor},
          grid:{color:gridColor}
        },
        y:{
          title:{display:true,text:"Absorbance",color:textColor},
          ticks:{color:textColor},
          grid:{color:gridColor}
        }
      }
    }
  });
}

function updateChartTheme() {
  if (!spectralChart) return;
  const theme = htmlEl.getAttribute("data-theme");
  const textColor = theme==="dark" ? "#e5e7eb" : "#0f172a";
  const gridColor = theme === "dark"
      ? "rgba(148,163,184,0.35)"
      : "rgba(148,163,184,0.50)";

  const chart = spectralChart;
  chart.options.scales.x.title.color = textColor;
  chart.options.scales.y.title.color = textColor;
  chart.options.scales.x.ticks.color = textColor;
  chart.options.scales.y.ticks.color = textColor;
  chart.options.scales.x.grid.color = gridColor;
  chart.options.scales.y.grid.color = gridColor;
  chart.options.plugins.legend.labels.color = textColor;
  chart.update("none");
}
