/*********************************************************
 THEME TOGGLE
*********************************************************/
(function () {
  const rootEl = document.documentElement;

  function applyTheme(theme) {
    rootEl.setAttribute("data-theme", theme);
    localStorage.setItem("colour-pipeline-theme", theme);

    const btn = document.getElementById("theme-toggle");
    if (!btn) return;

    const thumb = btn.querySelector(".theme-toggle-thumb");
    const label = btn.querySelector(".theme-toggle-label");

    if (thumb) thumb.textContent = theme === "dark" ? "🌙" : "☀️";
    if (label) label.textContent = theme === "dark" ? "Dark mode" : "Light mode";

    // SAFE cross-module hooks
    if (typeof colorHeatmap === "function") colorHeatmap();
    if (typeof updateChartTheme === "function") updateChartTheme();
  }

  document.addEventListener("DOMContentLoaded", () => {
    const saved =
      localStorage.getItem("colour-pipeline-theme") === "dark"
        ? "dark"
        : "light";

    applyTheme(saved);

    const btn = document.getElementById("theme-toggle");
    if (!btn) {
      console.warn("[THEME] theme-toggle button not found");
      return;
    }

    btn.addEventListener("click", () => {
      const next =
        rootEl.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(next);
    });
  });
})();
