/* ======================================================
   CYF ADMIN SHELL
   Shared by every admin / registration-team page:
   - fills the top-bar profile chip from the login info
   - profile dropdown
   - Settings link → account modal (admin dashboard)
   - closes the mobile sidebar after choosing a link
   Pages keep their own toggleSidebar / toggleEventMenu.
====================================================== */

(function () {
  function readStorage(key) {
    try {
      return localStorage.getItem(key) || "";
    } catch (error) {
      return "";
    }
  }

  function initials(name) {
    const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return "?";
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  const ROLE_LABELS = {
    Admin: "Administrator",
    "Registration Team": "Registration Team",
  };

  /* --------------------------------------------------
     PROFILE CHIP
     Public so the dashboard can refresh it with the
     name returned by /dashboard_overview.
  -------------------------------------------------- */

  window.cyfSetUser = function (fullname, role) {
    const name = fullname || readStorage("cyf_fullname") || readStorage("cyf_username") || "Signed in";
    const roleKey = role || readStorage("cyf_role");
    const roleLabel = ROLE_LABELS[roleKey] || roleKey || "";

    document.querySelectorAll("[data-cyf-name]").forEach(function (el) {
      el.textContent = name;
    });
    document.querySelectorAll("[data-cyf-role]").forEach(function (el) {
      el.textContent = roleLabel;
    });
    document.querySelectorAll("[data-cyf-initials]").forEach(function (el) {
      el.textContent = initials(name);
    });
  };

  function setupUserMenu() {
    document.querySelectorAll("[data-cyf-user]").forEach(function (wrap) {
      const button = wrap.querySelector(".cyf-user-btn");
      const menu = wrap.querySelector(".cyf-user-menu");
      if (!button || !menu) return;

      button.addEventListener("click", function (event) {
        event.stopPropagation();
        const open = menu.hidden;
        document.querySelectorAll(".cyf-user-menu, .cyf-popover").forEach(function (other) {
          other.hidden = true;
        });
        menu.hidden = !open;
        button.setAttribute("aria-expanded", String(open));
      });
    });

    document.addEventListener("click", function (event) {
      if (event.target.closest(".cyf-user-menu")) return;
      document.querySelectorAll(".cyf-user-menu").forEach(function (menu) {
        menu.hidden = true;
      });
      document.querySelectorAll(".cyf-user-btn").forEach(function (button) {
        button.setAttribute("aria-expanded", "false");
      });
    });

    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") return;
      document.querySelectorAll(".cyf-user-menu").forEach(function (menu) {
        menu.hidden = true;
      });
    });
  }

  /* --------------------------------------------------
     SETTINGS → ACCOUNT MODAL
  -------------------------------------------------- */

  function setupSettings() {
    document.addEventListener("click", function (event) {
      const link = event.target.closest("[data-cyf-settings]");
      if (!link || typeof window.openAdminAccountModal !== "function") return;
      event.preventDefault();
      document.querySelectorAll(".cyf-user-menu").forEach(function (menu) {
        menu.hidden = true;
      });
      window.openAdminAccountModal();
    });

    if (location.hash === "#account" && typeof window.openAdminAccountModal === "function") {
      window.openAdminAccountModal();
      history.replaceState(null, "", location.pathname + location.search);
    }
  }

  /* --------------------------------------------------
     MOBILE SIDEBAR
  -------------------------------------------------- */

  function setupSidebar() {
    const sidebar = document.getElementById("sidebar");
    if (!sidebar) return;

    sidebar.addEventListener("click", function (event) {
      const link = event.target.closest("a[href]");
      if (link && window.matchMedia("(max-width: 1100px)").matches) {
        sidebar.classList.remove("open");
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    window.cyfSetUser();
    setupUserMenu();
    setupSettings();
    setupSidebar();
  });
})();
