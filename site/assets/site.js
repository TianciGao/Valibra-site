"use strict";
// Progressive enhancement only: the full report is readable without JavaScript.
const toggle = document.querySelector("[data-toggle-cases]");
const cases = Array.from(document.querySelectorAll("details.case"));
if (toggle && cases.length) {
  toggle.hidden = false;
  const sync = () => {
    const allOpen = cases.every(item => item.open);
    toggle.textContent = allOpen ? toggle.dataset.collapse : toggle.dataset.expand;
    toggle.setAttribute("aria-expanded", String(allOpen));
  };
  toggle.addEventListener("click", () => {
    const open = !cases.every(item => item.open);
    cases.forEach(item => { item.open = open; });
    sync();
  });
  cases.forEach(item => item.addEventListener("toggle", sync));
  sync();
}
const links = Array.from(document.querySelectorAll(".sidebar nav a"));
if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver(entries => {
    const visible = entries.filter(entry => entry.isIntersecting);
    if (!visible.length) return;
    const id = visible[0].target.id;
    links.forEach(link => {
      const active = link.getAttribute("href") === `#${id}`;
      link.classList.toggle("active", active);
      if (active) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    });
  }, { rootMargin: "-100px 0px -55% 0px", threshold: 0 });
  document.querySelectorAll("main section[id]").forEach(section => observer.observe(section));
}
let printState = [];
window.addEventListener("beforeprint", () => {
  printState = cases.map(item => item.open);
  cases.forEach(item => { item.open = true; });
});
window.addEventListener("afterprint", () => {
  cases.forEach((item, index) => { item.open = printState[index] ?? false; });
});
