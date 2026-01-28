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
      const lightingResp = await fetch("/get_lighting_map");
      window.LIGHTING_MAP = await lightingResp.json();

      // 3. Recolor heatmap
      if (typeof colorHeatmap === "function") {
        colorHeatmap();
      }

      // 4. Load lighting diagnostics
      const lightingTableResp = await fetch("/get_lighting_results");
      const lightingHtml = await lightingTableResp.text();
      const lightingTarget = document.getElementById("lighting-results");
      if (lightingTarget) lightingTarget.innerHTML = lightingHtml;

    } catch (err) {
      alert(err.message);
    } finally {
      loadingOverlay.classList.remove("active");
    }
  });
}
/*********************************************************
 HYPERSPECTRAL EXCEL UPLOAD (AJAX, no page reload)
*********************************************************/
const hyperspectralForm = document.getElementById("hyperspectral-upload-form");

if (hyperspectralForm) {
  hyperspectralForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const formData = new FormData(hyperspectralForm);
    loadingOverlay.classList.add("active");

    try {
      const resp = await fetch("/upload_hyperspectral_excel", {
        method: "POST",
        body: formData
      });

      const json = await resp.json();
      if (!resp.ok) throw new Error(json.error || "Hyperspectral upload failed");

      // ✅ Refresh hyperspectral map
      const mapResp = await fetch("/get_hyperspectral_map");
      window.HYPERSPECTRAL_MAP = await mapResp.json();

      // ✅ Recolor heatmap
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
