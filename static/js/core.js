/*********************************************************
 PAGE NAVIGATION
*********************************************************/
const navLinks = document.querySelectorAll(".nav-link");
const pages = {
  dashboard: document.getElementById("page-dashboard"),
  heatmap: document.getElementById("page-heatmap"),
  spectral: document.getElementById("page-spectral"),
  image_hsv: document.getElementById("page-image_hsv"),
  ratios: document.getElementById("page-ratios"),
  scientist: document.getElementById("page-scientist"),
  validate: document.getElementById("page-validate"),
  about: document.getElementById("page-about")
};

navLinks.forEach(btn => {
  btn.addEventListener("click", () => {
    if (btn.disabled) return;
    navLinks.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    const target = btn.dataset.page;

    Object.entries(pages).forEach(([key, sec]) => {
      if (!sec) return;
      sec.classList.toggle("active", key === target);
    });
  });
});
