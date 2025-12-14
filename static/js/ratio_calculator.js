/*********************************************************
 RATIO CALCULATOR
*********************************************************/
document.getElementById("ratio-run-btn")?.addEventListener("click",async()=>{
  const wlA=document.getElementById("ratio-wl-A").value;
  const wlB=document.getElementById("ratio-wl-B").value;
  const op=document.getElementById("ratio-operation").value;
  const token=document.getElementById("fileToken").value;

  const fd=new FormData();
  fd.append("file_token",token);
  fd.append("wlA",wlA);
  fd.append("wlB",wlB);
  fd.append("operation",op);

  const res=await fetch("/compute_ratio",{method:"POST",body:fd});
  const html=await res.text();
  document.getElementById("ratio-result").innerHTML=html;
});
