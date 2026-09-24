"use strict";
const reportToggles = [...document.querySelectorAll(".notion-report details")];
const reportButton = document.querySelector("[data-report-toggle]");
const reportLabels = document.documentElement.lang === "ru"
  ? { expand: "Развернуть все блоки", collapse: "Свернуть все блоки" }
  : { expand: "展开全部折叠内容", collapse: "收起全部折叠内容" };
const syncReportButton = () => {
  if (!reportButton) return;
  const allOpen = reportToggles.every(item => item.open);
  reportButton.textContent = allOpen ? reportLabels.collapse : reportLabels.expand;
  reportButton.setAttribute("aria-expanded", String(allOpen));
};
if (reportButton) {
  reportButton.hidden = false;
  reportButton.addEventListener("click", () => {
    const open = !reportToggles.every(item => item.open);
    reportToggles.forEach(item => { item.open = open; });
    syncReportButton();
  });
  reportToggles.forEach(item => item.addEventListener("toggle", syncReportButton));
  syncReportButton();
}
// Anchor targets may live inside folded containers, including the evidence index.
function revealAnchor() {
  if (!location.hash) return;
  let id;
  try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
  const target = document.getElementById(id);
  if (!target) return;
  let node = target;
  while (node) {
    if (node.tagName === "DETAILS") node.open = true;
    node = node.parentElement;
  }
  target.scrollIntoView();
}
addEventListener("hashchange", revealAnchor);
revealAnchor();
let printState = [];
addEventListener("beforeprint", () => {
  printState = reportToggles.map(item => item.open);
  reportToggles.forEach(item => { item.open = true; });
});
addEventListener("afterprint", () => {
  reportToggles.forEach((item, i) => { item.open = printState[i] ?? false; });
});
