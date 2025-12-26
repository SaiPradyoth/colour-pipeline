"""
hyperspectral_ingest.py

Stateful drag-and-drop hyperspectral ingestion with automatic cleanup.
Single-file, zero coupling to other codebases.
"""

import shutil
from pathlib import Path
from fastapi import FastAPI, UploadFile
from fastapi.responses import JSONResponse, HTMLResponse

# ---------------- CONFIG ----------------

MAX_UPLOAD_MB = 500
BASE_DIR = Path("/tmp/hyperspectral_ingest")
WORKSPACE = BASE_DIR / "current"

# ----------------------------------------

app = FastAPI(title="Hyperspectral Ingest")

FILE_MEANINGS = {
    "capture": "Raw hyperspectral capture (uncalibrated sensor data)",
    "darkref": "Dark reference (sensor noise baseline)",
    "whiteref": "White reference (illumination normalization)",
    "reflectance": "Calibrated reflectance cube",
    "metadata": "Instrument / acquisition metadata",
    "preview": "RGB or grayscale preview image",
    "settings": "Acquisition or processing configuration",
    "unknown": "Unclassified file"
}

EXTENSION_TYPES = {
    ".hdr": "ENVI header (describes binary hyperspectral data)",
    ".raw": "Raw binary hyperspectral cube",
    ".dat": "Binary hyperspectral cube",
    ".xml": "Structured metadata",
    ".xsl": "XML stylesheet (presentation only)",
    ".json": "Settings or configuration",
    ".png": "Preview image",
    ".jpg": "Preview image",
    ".jpeg": "Preview image"
}

# ----------------------------------------

def reset_workspace():
    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)
    WORKSPACE.mkdir(parents=True, exist_ok=True)


def classify_file(path: Path):
    name = path.name.lower()
    suffix = path.suffix.lower()

    if "darkref" in name:
        role = "darkref"
    elif "whiteref" in name:
        role = "whiteref"
    elif "reflectance" in name:
        role = "reflectance"
    elif suffix in {".raw", ".dat"}:
        role = "capture"
    elif suffix in {".xml", ".xsl"}:
        role = "metadata"
    elif suffix in {".png", ".jpg", ".jpeg"}:
        role = "preview"
    elif suffix == ".json":
        role = "settings"
    else:
        role = "unknown"

    return {
        "path": str(path.relative_to(WORKSPACE)),
        "extension": suffix,
        "type": role,
        "meaning": FILE_MEANINGS[role],
        "details": EXTENSION_TYPES.get(suffix, "Unrecognized file type")
    }


def scan_workspace():
    files = []
    for f in WORKSPACE.rglob("*"):
        if f.is_file():
            files.append(classify_file(f))

    summary = {}
    for f in files:
        summary.setdefault(f["type"], 0)
        summary[f["type"]] += 1

    return {
        "workspace": str(WORKSPACE),
        "file_count": len(files),
        "summary": summary,
        "files": files
    }

# ----------------------------------------

@app.post("/upload-folder")
async def upload_folder(files: list[UploadFile]):
    reset_workspace()

    total_size = 0
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024

    for f in files:
        dest = WORKSPACE / f.filename
        dest.parent.mkdir(parents=True, exist_ok=True)

        with open(dest, "wb") as out:
            while True:
                chunk = await f.read(1024 * 1024)
                if not chunk:
                    break

                total_size += len(chunk)
                if total_size > max_bytes:
                    reset_workspace()
                    return JSONResponse(
                        status_code=413,
                        content={"error": "Upload exceeds 500 MB limit"}
                    )

                out.write(chunk)

    result = scan_workspace()
    result["status"] = "ingested"
    result["total_mb"] = round(total_size / (1024 * 1024), 2)

    return JSONResponse(content=result)


@app.get("/status")
def status():
    if not WORKSPACE.exists() or not any(WORKSPACE.iterdir()):
        return {"status": "empty"}
    return scan_workspace()


@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Hyperspectral Ingest</title>
  <style>
    body {
      font-family: system-ui, sans-serif;
      background: #0f172a;
      color: #e5e7eb;
      margin: 0;
      padding: 2rem;
    }
    .dropzone {
      border: 2px dashed #64748b;
      border-radius: 12px;
      padding: 3rem;
      text-align: center;
      cursor: pointer;
      background: #020617;
    }
    .dropzone.dragover {
      border-color: #22d3ee;
    }
    pre {
      margin-top: 2rem;
      padding: 1rem;
      background: #020617;
      border-radius: 8px;
      max-height: 50vh;
      overflow: auto;
      font-size: 0.85rem;
    }
    .status {
      margin-top: 1rem;
      color: #94a3b8;
    }
    .progress-container {
  width: 100%;
  height: 10px;
  background: #020617;
  border-radius: 6px;
  overflow: hidden;
  margin-top: 1rem;
}

.progress-bar {
  height: 100%;
  width: 0%;
  background: linear-gradient(90deg, #22d3ee, #38bdf8);
  transition: width 0.2s ease;
}

  </style>
</head>
<body>

<h2>Hyperspectral Folder Ingest</h2>

<div class="dropzone" id="dropzone">
  Drag & drop a hyperspectral folder here<br/>
  or click to select<br/>
  <small>(≤ 500 MB, replaces previous upload)</small>
</div>

<input
  type="file"
  id="fileInput"
  webkitdirectory
  directory
  multiple
  style="display:none"
/>

<div class="status" id="status"></div>

<div class="progress-container">
  <div class="progress-bar" id="progressBar"></div>
</div>

<pre id="output"></pre>


<script>
const dropzone = document.getElementById("dropzone");
const output = document.getElementById("output");
const status = document.getElementById("status");
const fileInput = document.getElementById("fileInput");

dropzone.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", async () => {
  await handleFiles(Array.from(fileInput.files));
});

async function handleFiles(fileList) {
  let totalSize = 0;
  const form = new FormData();

  const progressBar = document.getElementById("progressBar");
  progressBar.style.width = "0%";

  for (const file of fileList) {
    totalSize += file.size;
    const path = file._relativePath || file.webkitRelativePath || file.name;
    form.append("files", file, path);
  }

  if (totalSize > 500 * 1024 * 1024) {
    status.textContent = "❌ Upload exceeds 500 MB limit";
    return;
  }

  await uploadWithProgress(form);

}

dropzone.addEventListener("dragover", e => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});

dropzone.addEventListener("dragleave", () => {
  dropzone.classList.remove("dragover");
});

dropzone.addEventListener("drop", async e => {
  e.preventDefault();
  dropzone.classList.remove("dragover");

  const items = e.dataTransfer.items;
  const files = [];

  async function traverse(entry, prefix="") {
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
      const entries = await new Promise(resolve => reader.readEntries(resolve));
      for (const e of entries) {
        await traverse(e, prefix + entry.name + "/");
      }
    }
  }

  for (const item of items) {
    const entry = item.webkitGetAsEntry();
    if (entry) await traverse(entry);
  }

  await handleFiles(files);
});
function uploadWithProgress(form) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const progressBar = document.getElementById("progressBar");

    xhr.open("POST", "/upload-folder");

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const percent = Math.round((e.loaded / e.total) * 100);
        progressBar.style.width = percent + "%";
        status.textContent = `Uploading... ${percent}%`;
      } else {
        status.textContent = "Uploading...";
      }
    };

    xhr.onload = () => {
  let response = xhr.responseText;
  let json = null;

  try {
    json = response ? JSON.parse(response) : null;
  } catch (e) {
    // Non-JSON response (FastAPI error page, empty body, etc.)
  }

  if (xhr.status >= 200 && xhr.status < 300) {
    progressBar.style.width = "100%";
    output.textContent = json
      ? JSON.stringify(json, null, 2)
      : "(Upload completed, no JSON body)";
    status.textContent = "✅ Upload complete";
    resolve();
  } else {
    progressBar.style.width = "0%";
    status.textContent = `❌ Upload failed (${xhr.status})`;
    output.textContent = response || "(No response body)";
    reject(new Error("Upload failed"));
  }
};


    xhr.onerror = () => {
      progressBar.style.width = "0%";
      status.textContent = "❌ Upload failed (network)";
      reject(new Error("Network error"));
    };

    xhr.send(form);
  });
}

</script>

</body>
</html>
"""
