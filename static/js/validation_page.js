
/*********************************************************
 VALIDATION PAGE
*********************************************************/
document.getElementById("run-validation")?.addEventListener("click",async()=>{
  const btn=document.getElementById("run-validation");
  btn.disabled=true;
  btn.textContent="Validating…";

  const res=await fetch("/debug_validate");
  const data=await res.json();

  const result=document.getElementById("validation-result");
  const status=document.getElementById("validation-status");
  const details=document.getElementById("validation-details");

  result.style.display="block";

  if(data.status==="ok" || (data.XYZ_raw && data.Lab)){
    status.textContent="✔ Math Validation Passed!";
    status.style.color="green";
    details.textContent = JSON.stringify(data,null,2);
  } else {
    status.textContent="❌ Validation Failed";
    status.style.color="red";
    details.textContent="Error: "+(data.error || data.message || "Unknown");
  }

  btn.disabled=false;
  btn.textContent="Run Validation";
});
