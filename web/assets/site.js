/* ======================================================
   CYF SHARED SITE SCRIPT (public pages)
   Pages may define their own toggleMenu(); this only
   provides it when a page doesn't.
====================================================== */

(function () {
  if (typeof window.toggleMenu !== "function") {
    window.toggleMenu = function () {
      const menu = document.querySelector(".nav-links");
      const button = document.querySelector(".menu-toggle");
      if (!menu) return;
      menu.classList.toggle("open");
      if (button) {
        button.setAttribute("aria-expanded", menu.classList.contains("open"));
      }
    };
  }

  document.addEventListener("click", function (event) {
    const menu = document.querySelector(".nav-links.open");
    if (!menu) return;
    const clickedLink = event.target.closest(".nav-links a");
    const clickedInside = event.target.closest(".nav-links, .menu-toggle");
    if (clickedLink || !clickedInside) {
      menu.classList.remove("open");
    }
  });
})();
