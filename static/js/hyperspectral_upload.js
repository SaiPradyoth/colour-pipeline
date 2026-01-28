(() => {
  const dropzone = document.getElementById("hyperspectral-dropzone");
  const fileInput = document.getElementById("hyperspectral-input");
  const status = document.getElementById("hyperspectral-status");
  const results = document.getElementById("hyperspectral-results");

  if (!dropzone || !fileInput || !status) return;

  dropzone.addEventListener("click", () => fileInput.click());

  dropzone.addEventListener("dragover", e => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });

  dropzone.addEventListener("drop", e => {
    e.preventDefault();
    dropzone.classList.remove("dragover");

    const items = e.dataTransfer.items;
    if (!items || !items.length) return;

    const files = [];

    async function traverse(entry, prefix = "") {
      if (entry.isFile) {
        await new Promise(resolve => {
          entry.file(file => {
            file._relativePath = prefix + file.name;
            files.push(file);
            resolve();
          });
        });
      } else if (entry.isDirectory) {
        const reader = entry.createReader();
        while (true) {
          const batch = await new Promise(resolve => reader.readEntries(resolve));
          if (!batch.length) break;
          for (const child of batch) {
            await traverse(child, prefix + entry.name + "/");
          }
        }
      }
    }

    (async () => {
      for (const item of items) {
        const entry = item.webkitGetAsEntry && item.webkitGetAsEntry();
        if (entry) await traverse(entry);
      }
      handleFiles(files);
    })();
  });

  fileInput.addEventListener("change", () => {
    handleFiles(fileInput.files);
    fileInput.value = "";
  });

  async function handleFiles(fileList) {
    if (!fileList || !fileList.length) return;

    status.textContent = "Uploading hyperspectral dataset…";

    const form = new FormData();
    let totalBytes = 0;

    for (const file of fileList) {
      totalBytes += file.size;
      form.append("files", file, file.webkitRelativePath || file.name);
    }

    // --- NEW: human-readable size ---
    const sizeMB = totalBytes / (1024 * 1024);
    const sizeGB = totalBytes / (1024 * 1024 * 1024);

    const sizeLabel =
      sizeGB >= 1
        ? `${sizeGB.toFixed(2)} GB`
        : `${sizeMB.toFixed(1)} MB`;

    status.textContent = `Preparing upload: ${fileList.length} files (${sizeLabel})`;

    // --- limit check ---
    if (totalBytes > 1024 * 1024 * 1024) {
      status.textContent =
        `❌ Upload too large: ${sizeLabel} (limit is 1 GB)`;
      return;
    }

    try {
      const res = await fetch("/hyperspectral/upload-folder", {
        method: "POST",
        body: form
      });

      const text = await res.text();          // ✅ always safe
      let json = null;
      try { json = JSON.parse(text); } catch {}

      const SERVER_LIMIT_BYTES = 1024 * 1024 * 1024;
      const SERVER_LIMIT_LABEL = "1 GB";

      if (!res.ok) {
        if (res.status === 413) {
          status.textContent =
            `❌ Upload too large (server rejected). ` +
            `Current folder size = ${sizeLabel}. ` +
            `Server limit = ${SERVER_LIMIT_LABEL} (total request size).`;
        } else {
          status.textContent = "❌ Upload failed on server.";
        }
        console.error(text);
        return;
      }

      status.textContent = "✅ Upload complete — converting to plate…";
      results.style.display = "block";

      document.getElementById("hyperspectral-summary").textContent =
        `${json.file_count} files uploaded (${json.total_mb} MB)`;

      document.getElementById("hyperspectral-validation").textContent =
        json.envi_validation?.length
          ? "ENVI headers validated."
          : "No ENVI headers found.";

      document.getElementById("hyperspectral-preview").textContent =
        "Hyperspectral data uploaded. Upload the generated plate Excel to apply overlay.";

      status.textContent =
      "✅ Upload complete. ENVI validated. Download the plate Excel to continue analysis.";
      const success = document.getElementById("hyperspectral-success");
      if (success) success.style.display = "block";
      
      // 🔔 Notify heatmap that hyperspectral data is ready
      window.dispatchEvent(new Event("hyperspectral:loaded"));

    } catch (err) {
      console.error(err);
      status.textContent = "❌ Network or server error.";
    }
  }
})();
