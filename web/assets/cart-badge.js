/* CYF cart badge: shows the saved cart count on the navbar cart icon of EVERY page.
   Cart data lives in localStorage ("cyf_store_cart"), shared by all pages on the site. */
(function () {
  const KEY = "cyf_store_cart";
  function count() {
    try {
      const c = JSON.parse(localStorage.getItem(KEY) || "[]");
      return Array.isArray(c)
        ? c.reduce((t, i) => t + (Number(i.quantity) || 0), 0)
        : 0;
    } catch (e) {
      return 0;
    }
  }
  function render() {
    const n = count();
    document.querySelectorAll(".nav-cart").forEach((btn) => {
      let b = btn.querySelector(".cart-count");
      if (!b) {
        b = document.createElement("span");
        b.className = "cart-count";
        btn.appendChild(b);
        btn.style.position = btn.style.position || "relative";
        if (getComputedStyle(b).position !== "absolute") {
          Object.assign(b.style, {
            position: "absolute",
            top: "-6px",
            right: "-6px",
            minWidth: "19px",
            height: "19px",
            padding: "0 5px",
            borderRadius: "999px",
            background: "#e8b923",
            color: "#3d2b00",
            fontSize: "11px",
            fontWeight: "800",
            display: "grid",
            placeItems: "center",
          });
        }
      }
      b.textContent = n;
      b.style.display = n > 0 ? "" : "none";
      /* on pages other than the store, the icon opens the cart drawer in the store */
      if (btn.tagName === "A" && !/store\.html/.test(location.pathname))
        btn.setAttribute("href", "store.html?cart=1");
    });
  }
  document.addEventListener("DOMContentLoaded", render);
  window.addEventListener("storage", (e) => {
    if (e.key === KEY) render();
  }); /* other tabs */
  window.addEventListener("pageshow", render); /* back/forward cache */
  window.addEventListener("cyf-cart-updated", render);
})();
