/*********************************************************
 FULLSCREEN RAW MATRIX
*********************************************************/
document.getElementById("fullscreen-raw-btn")?.addEventListener("click",()=>{
  const modal=document.getElementById("raw-fullscreen-modal");
  const content=document.getElementById("raw-fullscreen-content");
  const table=document.querySelector("#page-scientist table");
  if(table){
    content.innerHTML=table.outerHTML;
    modal.style.display="block";
  }
});

document.getElementById("raw-fullscreen-close")?.addEventListener("click",()=>{
  document.getElementById("raw-fullscreen-modal").style.display="none";
});
