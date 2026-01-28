/*********************************************************
 PIPELINE VALIDATION PAGE
 Explains WHAT is validated, WHY it matters,
 and shows the underlying color science math.
*********************************************************/

document.getElementById("run-validation")?.addEventListener("click", async () => {
  const btn = document.getElementById("run-validation");
  btn.disabled = true;
  btn.textContent = "Validating…";

  let data;
  try {
    const res = await fetch("/debug_validate");
    data = await res.json();
  } catch (err) {
    showValidationError("Could not reach validation endpoint.");
    btn.disabled = false;
    btn.textContent = "Run Validation";
    return;
  }

  const result = document.getElementById("validation-result");
  const status = document.getElementById("validation-status");
  const summary = document.getElementById("validation-summary");
  const table = document.getElementById("validation-table");
  const math = document.getElementById("validation-math");
  const raw = document.getElementById("validation-details");

  result.style.display = "block";

  // ---------- FAILURE ----------
  if (data.status !== "ok") {
    status.textContent = "❌ Validation Failed";
    status.style.color = "red";
    summary.innerHTML = `
      <p class="text-danger small">
        The internal color pipeline did not produce expected results.
        This may indicate a math or dependency error.
      </p>`;
    raw.textContent = JSON.stringify(data, null, 2);
    btn.disabled = false;
    btn.textContent = "Run Validation";
    return;
  }

  // ---------- SUCCESS ----------
  status.textContent = "✔ Math Validation Passed";
  status.style.color = "green";

  // ---------- HYPERSPECTRAL VALIDATION ----------
  let hyper;
  try {
    const hyperRes = await fetch("/validate_hyperspectral");
    hyper = await hyperRes.json();
  } catch (e) {
    hyper = null;
  }

  if (hyper && hyper.status === "ok") {
    summary.innerHTML += `
      <hr/>
      <p class="small"><b>Hyperspectral Data Validation</b></p>
      <table class="table table-sm table-bordered">
        <tbody>
          <tr>
            <td>Mean CV%</td>
            <td><b>${hyper.stats.mean_cv.toFixed(2)}%</b></td>
            <td>Overall spatial variability</td>
          </tr>
          <tr>
            <td>Stable wells</td>
            <td>${hyper.stats.stable_pct.toFixed(1)}%</td>
            <td>&lt; 10% CV</td>
          </tr>
          <tr>
            <td>Moderate wells</td>
            <td>${hyper.stats.moderate_pct.toFixed(1)}%</td>
            <td>10–20% CV</td>
          </tr>
          <tr>
            <td>Unstable wells</td>
            <td>${hyper.stats.unstable_pct.toFixed(1)}%</td>
            <td>&gt; 20% CV</td>
          </tr>
        </tbody>
      </table>
      <p class="small text-muted">
        Hyperspectral CV% reflects spatial consistency, not chemical signal.
      </p>
    `;
  }

if (hyper && hyper.status === "warn") {
  summary.innerHTML += `
    <hr/>
    <p class="small text-warning">
      ⚠ Hyperspectral validation warning: ${hyper.message}
    </p>
  `;
}

  const deltaE = data.deltaE;
  const passText =
    deltaE < 0.5
      ? "Excellent agreement (below perceptual threshold)"
      : "Acceptable but higher than expected";

  summary.innerHTML = `
    <p class="small">
      This test validates the <b>spectral → XYZ → Lab → ΔE2000</b> math
      using a <b>flat (unity) spectrum</b> under <b>D65 illumination</b>.
    </p>
    <p class="small mb-2">
      Expected output: <code>Lab ≈ [100, 0, 0]</code><br/>
      Observed ΔE2000: <b>${deltaE.toFixed(6)}</b>
      <span class="text-muted">(${passText})</span>
    </p>
  `;

  // ---------- NUMERIC RESULTS TABLE ----------
  table.innerHTML = `
    <table class="table table-sm table-bordered">
      <thead>
        <tr>
          <th>Quantity</th>
          <th>Value</th>
          <th>Meaning</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>L*</td>
          <td>${data.Lab[0].toFixed(4)}</td>
          <td>Lightness (should be ≈ 100)</td>
        </tr>
        <tr>
          <td>a*</td>
          <td>${data.Lab[1].toFixed(4)}</td>
          <td>Green ↔ Red (should be ≈ 0)</td>
        </tr>
        <tr>
          <td>b*</td>
          <td>${data.Lab[2].toFixed(4)}</td>
          <td>Blue ↔ Yellow (should be ≈ 0)</td>
        </tr>
        <tr>
          <td>ΔE2000</td>
          <td><b>${deltaE.toFixed(6)}</b></td>
          <td>Color difference vs ideal white</td>
        </tr>
      </tbody>
    </table>
  `;

  // ---------- MATH / FORMULA RENDERING ----------
  math.innerHTML = `
    <div class="small mb-2">
      <b>Color Science Math Used</b>
    </div>

    <div class="small mb-2">
      <b>1. Spectral → XYZ</b><br/>
      <code>
        X = ∫ S(λ) · I(λ) · x̄(λ) dλ<br/>
        Y = ∫ S(λ) · I(λ) · ȳ(λ) dλ<br/>
        Z = ∫ S(λ) · I(λ) · z̄(λ) dλ
      </code>
    </div>

    <div class="small mb-2">
      Where:
      <ul class="mb-2">
        <li><code>S(λ)</code> = sample transmittance (here: unity)</li>
        <li><code>I(λ)</code> = illuminant (D65)</li>
        <li><code>x̄,ȳ,z̄</code> = CIE color matching functions</li>
      </ul>
    </div>

    <div class="small mb-2">
      <b>2. XYZ Normalization</b><br/>
      <code>XYZ<sub>norm</sub> = (XYZ / Y<sub>white</sub>) × 100</code>
    </div>

    <div class="small mb-2">
      <b>3. XYZ → Lab</b><br/>
      Uses CIE 1931 2° observer and D65 white point.
    </div>

    <div class="small mb-2">
      <b>4. ΔE2000</b><br/>
      <code>ΔE<sub>00</sub>(Lab<sub>measured</sub>, Lab<sub>reference</sub>)</code>
    </div>

    <div class="small text-muted">
      This validation confirms that a perfectly white spectrum produces
      a near-ideal Lab value and near-zero color difference.
    </div>
  `;

  // ---------- RAW JSON ----------
  raw.textContent = JSON.stringify(data, null, 2);

  btn.disabled = false;
  btn.textContent = "Run Validation";
});

/* --------------------------------------- */
function showValidationError(msg) {
  const result = document.getElementById("validation-result");
  const status = document.getElementById("validation-status");
  const summary = document.getElementById("validation-summary");

  result.style.display = "block";
  status.textContent = "❌ Validation Error";
  status.style.color = "red";
  summary.innerHTML = `<p class="text-danger small">${msg}</p>`;
}
