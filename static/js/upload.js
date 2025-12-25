/*********************************************************
 UPLOAD + LOADING OVERLAY
*********************************************************/
const dropzone = document.getElementById("upload-dropzone");
const fileInput = document.getElementById("dataset");
const uploadStatus = document.getElementById("upload-status");
const loadingOverlay = document.getElementById("loading-overlay");

if (dropzone && fileInput) {
  dropzone.onclick = () => fileInput.click();

  dropzone.addEventListener("dragover", e => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
  ["dragleave","dragend","drop"].forEach(ev => {
    dropzone.addEventListener(ev, () => dropzone.classList.remove("dragover"));
  });
  dropzone.addEventListener("drop", e => {
    e.preventDefault();
    if (!e.dataTransfer.files || !e.dataTransfer.files.length) return;
    fileInput.files = e.dataTransfer.files;
    uploadStatus.textContent = "Uploaded spectra: " + e.dataTransfer.files[0].name;
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files.length) {
      uploadStatus.textContent = "Uploaded spectra: " + fileInput.files[0].name;
    }
  });
}

document.getElementById("upload-form")?.addEventListener("submit", () => {
  loadingOverlay.classList.add("active");
});

document.getElementById("recalc-form")?.addEventListener("submit", () => {
  loadingOverlay.classList.add("active");
});

/*********************************************************
 HSV IMAGE UPLOAD (AJAX, no page reload)
*********************************************************/
const hsvForm = document.getElementById("hsv-upload-form");

if (hsvForm) {
  hsvForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const formData = new FormData(hsvForm);
    loadingOverlay.classList.add("active");

    try {
      const resp = await fetch("/upload_hsv_images", {
        method: "POST",
        body: formData
      });

      if (!resp.ok) throw new Error("HSV upload failed");

      // 1. Update HSV results table
      const tableResp = await fetch("/get_hsv_results");
      const html = await tableResp.text();
      const target = document.getElementById("hsv-results-container");
      if (target) target.innerHTML = html;

      // 2. Refresh HSV_MAP
      const mapResp = await fetch("/get_hsv_map");
      window.HSV_MAP = await mapResp.json();

      // 3. Recolor heatmap
      if (typeof colorHeatmap === "function") {
        colorHeatmap();
      }

    } catch (err) {
      alert(err.message);
    } finally {
      loadingOverlay.classList.remove("active");
    }
  });
}
