/*********************************************************
 λ_max COLOR MAP
 Yellow → Red → Blue → Purple
*********************************************************/
function lambdaColor(lambda) {
  // < 520 nm → Yellow
  if (lambda < 520) {
    return "rgb(255,240,0)";
  }
  // 520–540 nm → Yellow → Red
  if (lambda < 540) {
    let t = (lambda - 520) / 20;
    return `rgb(${255}, ${240*(1-t)}, 0)`;
  }
  // 540–580 nm → Red → Blue
  if (lambda < 580) {
    let t = (lambda - 540) / 40;
    return `rgb(${255*(1-t)}, 0, ${255*t})`;
  }
  // 580–650 nm → Blue → Purple
  if (lambda < 650) {
    let t = (lambda - 580) / 70;
    return `rgb(${0*(1-t) + 128*t}, 0, ${255*(1-t) + 128*t})`;
  }
  // > 650 nm → Purple
  return "rgb(128,0,128)";
}