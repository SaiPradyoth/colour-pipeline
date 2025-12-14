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
