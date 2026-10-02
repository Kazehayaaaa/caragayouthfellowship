/* ======================================================
   CYF SHARED SITE SCRIPT (public pages)
   Pages may define their own toggleMenu(); this only
   provides it when a page doesn't.
   On tablets and phones it also adds the app-style
   bottom tab bar (styled in mobile.css).
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

  /* ---------------- Mobile app shell ---------------- */

  const ICONS = {
    home: '<path d="M3.5 10.5 12 3.5l8.5 7"/><path d="M5.5 9v10.5a1 1 0 0 0 1 1H10v-6h4v6h3.5a1 1 0 0 0 1-1V9"/>',
    about: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.6v.1"/>',
    contact: '<rect x="2.5" y="5" width="19" height="14" rx="2.5"/><path d="M3 6.5l9 6.5 9-6.5"/>',
    store: '<path d="M4 7.5h16l-1.2 11.6a1.5 1.5 0 0 1-1.5 1.4H6.7a1.5 1.5 0 0 1-1.5-1.4z"/><path d="M8.5 7.5V6a3.5 3.5 0 0 1 7 0v1.5"/>',
    sponsor: '<path d="M12 20.5s-7.5-4.4-7.5-10.1A4.4 4.4 0 0 1 12 7.6a4.4 4.4 0 0 1 7.5 2.8c0 5.7-7.5 10.1-7.5 10.1z"/>',
    register: '<path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>'
  };

  // The desktop menu's items, with Register in the middle of the bar.
  const TABS = [
    ["home", "home.html", "Home"],
    ["about", "home.html#about", "About"],
    ["contact", "home.html#contact", "Contact"],
    ["register", "register.html", "Register"],
    ["store", "store.html", "Store"],
    ["sponsor", "sponsor.html", "Sponsor"]
  ];

  function icon(name) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICONS[name] + "</svg>";
  }

  function currentPage() {
    const page = location.pathname.split("/").pop().replace(".html", "") || "home";
    if (page === "home" || page === "store" || page === "register") return page;
    if (page.indexOf("sponsor") !== -1) return "sponsor";
    return "";
  }

  function buildShell() {
    if (!document.querySelector(".navbar") || document.querySelector(".m-tabbar")) return;

    const page = currentPage();
    const bar = document.createElement("nav");
    bar.className = "m-tabbar";
    bar.setAttribute("aria-label", "Main");
    bar.innerHTML = TABS.map(function (t) {
      return '<a class="m-tab' + (t[0] === "register" ? " m-tab-cta" : "") + '" href="' + t[1] +
        '" data-tab="' + t[0] + '"><span class="m-tab-icon">' + icon(t[0]) + "</span><span>" + t[2] + "</span></a>";
    }).join("");
    document.body.appendChild(bar);
    document.body.classList.add("has-tabbar");

    function setActive(name) {
      bar.querySelectorAll(".m-tab").forEach(function (tab) {
        const on = tab.getAttribute("data-tab") === name;
        tab.classList.toggle("is-active", on);
        if (on) tab.setAttribute("aria-current", "page");
        else tab.removeAttribute("aria-current");
      });
    }

    // On the home page, Home / About / Contact follow the section on screen.
    const about = page === "home" && document.getElementById("about");
    const contact = page === "home" && document.getElementById("contact");
    function homeSection() {
      const line = window.innerHeight * 0.4;
      if (contact && contact.getBoundingClientRect().top < line) return "contact";
      if (about && about.getBoundingClientRect().top < line) return "about";
      return "home";
    }
    setActive(page === "home" ? homeSection() : page);

    // Header shadow once the page scrolls; tab bar slides away while
    // scrolling down and comes back on the way up.
    const navbar = document.querySelector(".navbar");
    let lastY = window.scrollY;
    let ticking = false;
    window.addEventListener("scroll", function () {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function () {
        const y = window.scrollY;
        navbar.classList.toggle("is-scrolled", y > 8);
        const nearBottom = window.innerHeight + y >= document.documentElement.scrollHeight - 40;
        if (y > lastY + 6 && y > 160 && !nearBottom) bar.classList.add("is-hidden");
        else if (y < lastY - 6 || nearBottom) bar.classList.remove("is-hidden");
        if (page === "home") setActive(homeSection());
        lastY = y;
        ticking = false;
      });
    }, { passive: true });
  }
  function revealOnScroll() {
    if (!("IntersectionObserver" in window)) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (!window.matchMedia("(max-width: 1020px)").matches) return;

    const items = document.querySelectorAll(
      ".section-head, .info-card, .countdown-card, .contact-card, .contact-info, " +
      ".participant-search-box, .about-copy, .type-card"
    );
    const observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("m-in");
          observer.unobserve(entry.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });

    items.forEach(function (el) {
      // Anything already on screen stays visible; only content below the fold animates in.
      if (el.getBoundingClientRect().top < window.innerHeight) return;
      el.classList.add("m-reveal");
      observer.observe(el);
    });
  }

  function addThemeColor() {
    if (document.querySelector('meta[name="theme-color"]')) return;
    const meta = document.createElement("meta");
    meta.name = "theme-color";
    meta.content = "#ffffff";
    document.head.appendChild(meta);
  }

  function init() {
    addThemeColor();
    buildShell();
    revealOnScroll();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
