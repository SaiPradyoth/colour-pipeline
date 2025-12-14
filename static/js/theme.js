
/*********************************************************
 THEME TOGGLE
*********************************************************/
const htmlEl = document.documentElement;
const themeToggleBtn = document.getElementById('theme-toggle');
const themeThumb = themeToggleBtn.querySelector('.theme-toggle-thumb');
const themeLabel = themeToggleBtn.querySelector('.theme-toggle-label');

function applyTheme(theme) {
  htmlEl.setAttribute('data-theme', theme);
  localStorage.setItem('colour-pipeline-theme', theme);
  themeThumb.textContent = theme === 'dark' ? '🌙' : '☀️';
  themeLabel.textContent = theme === 'dark' ? 'Dark mode' : 'Light mode';
  colorHeatmap();
  updateChartTheme();
}

applyTheme(localStorage.getItem('colour-pipeline-theme') === 'dark' ? 'dark' : 'light');

themeToggleBtn.addEventListener('click', () => {
  applyTheme(htmlEl.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
});
