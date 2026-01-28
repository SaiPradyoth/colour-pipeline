/*********************************************************
 RATIO CALCULATOR
*********************************************************/
document.getElementById("ratio-run-btn")?.addEventListener("click", async () => {
  const selA = document.getElementById("ratio-wl-A");
  const selB = document.getElementById("ratio-wl-B");
  const selOp = document.getElementById("ratio-operation");
  const tokenEl = document.getElementById("fileToken");
  const resultEl = document.getElementById("ratio-result");

  if (!selA || !selB || !selOp || !tokenEl || !resultEl) {
    console.warn("[RATIO] Required elements missing");
    return;
  }

  const token = tokenEl.value;
  if (!token) {
    resultEl.innerHTML = `<div class="text-muted small">Upload a dataset first.</div>`;
    return;
  }

  const fd = new FormData();
  fd.append("file_token", token);
  fd.append("wlA", selA.value);
  fd.append("wlB", selB.value);
  fd.append("operation", selOp.value);

  try {
    const res = await fetch("/compute_ratio", { method: "POST", body: fd });

    if (!res.ok) {
      const txt = await res.text();
      resultEl.innerHTML = `<div class="text-danger small">Error: ${txt || res.status}</div>`;
      return;
    }

    resultEl.innerHTML = await res.text();
  } catch (err) {
    console.error(err);
    resultEl.innerHTML = `<div class="text-danger small">Network error.</div>`;
  }
});
