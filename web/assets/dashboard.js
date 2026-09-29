/* ======================================================
   CYF DASHBOARD
   Shared by admin_dashboard.html (data-variant="admin")
   and registration_dashboard.html (data-variant="team").
   Data: GET /dashboard_overview?range=6m|month|year
====================================================== */

(function () {
  "use strict";

  const VARIANT = document.body.dataset.variant === "team" ? "team" : "admin";
  const SFX = VARIANT === "team" ? "_rt" : "";

  const PAGES = {
    events: "event_event" + SFX + ".html",
    participants: "participants" + SFX + ".html",
    staff: "staff.html",
    chaperones: "chaperone" + SFX + ".html",
    reports: "report" + SFX + ".html",
  };

  const SERIES = [
    { key: "participants", label: "Participants", color: "#c0263a" },
    { key: "staff", label: "Staff", color: "#f0a716" },
    { key: "chaperones", label: "Chaperones", color: "#1fae63" },
  ].filter(function (s) {
    return VARIANT === "admin" || s.key !== "staff";
  });

  const REFRESH_MS = 60000;

  let state = {
    range: "6m",
    data: null,
    loading: false,
  };

  /* ======================================================
     HELPERS
  ====================================================== */

  const $ = function (id) {
    return document.getElementById(id);
  };

  function esc(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  const ICON_PATHS = {
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.2a6.5 6.5 0 0 1 3.5 5.8"/>',
    team: '<circle cx="12" cy="7" r="3.2"/><circle cx="5" cy="9" r="2.4"/><circle cx="19" cy="9" r="2.4"/><path d="M6.5 20a5.5 5.5 0 0 1 11 0M1.5 18.5a3.8 3.8 0 0 1 5-3.5M22.5 18.5a3.8 3.8 0 0 0-5-3.5"/>',
    shield: '<path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.4 7.5 9.5 4.3-1.1 7.5-4.9 7.5-9.5V6z"/><path d="m9 12 2 2 4-4"/>',
    calendar: '<rect x="3" y="4.5" width="18" height="16.5" rx="2.5"/><path d="M3 9.5h18M8 2.5v4M16 2.5v4M8 14h2M14 14h2M8 17.5h2"/>',
    arrowRight: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    chevronRight: '<path d="m9 6 6 6-6 6"/>',
    trendUp: '<path d="M12 5 20 19H4z"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    card: '<rect x="2.5" y="5" width="19" height="14" rx="2.5"/><path d="M2.5 10h19M6.5 15h4"/>',
    heart: '<path d="M12 20.5s-7.5-4.4-7.5-10.1A4.4 4.4 0 0 1 12 7.6a4.4 4.4 0 0 1 7.5 2.8c0 5.7-7.5 10.1-7.5 10.1z"/>',
    chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    dots: '<circle cx="12" cy="5" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="12" cy="19" r="1.6"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  };

  function icon(name) {
    return (
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      ICON_PATHS[name] +
      "</svg>"
    );
  }

  function parseTime(value) {
    if (!value) return null;
    // Server timestamps are naive local times ("2026-08-27T11:47:24.9").
    const date = new Date(String(value).replace(" ", "T"));
    return isNaN(date) ? null : date;
  }

  function formatDateTime(value) {
    const date = parseTime(value);
    if (!date) return "—";
    const day = date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    const time = date.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
    return day + " • " + time;
  }

  function relativeTime(value, nowValue) {
    const date = parseTime(value);
    const now = parseTime(nowValue) || new Date();
    if (!date) return "";
    const seconds = Math.max(0, Math.round((now - date) / 1000));
    if (seconds < 60) return "just now";
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) return minutes + (minutes === 1 ? " minute ago" : " minutes ago");
    const hours = Math.round(minutes / 60);
    if (hours < 24) return hours + (hours === 1 ? " hour ago" : " hours ago");
    const days = Math.round(hours / 24);
    if (days < 7) return days + (days === 1 ? " day ago" : " days ago");
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }

  function initials(name) {
    const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return "?";
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  function tonedPill(text, tone) {
    return '<span class="pill ' + tone + '">' + esc(text) + "</span>";
  }

  const EVENT_TONES = ["rose", "amber", "blue", "violet", "green"];

  function eventTone(name) {
    let hash = 0;
    String(name || "").split("").forEach(function (ch) {
      hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
    });
    return EVENT_TONES[hash % EVENT_TONES.length];
  }

  function statusTone(status) {
    const value = String(status || "").toLowerCase();
    if (["active", "confirmed", "completed", "paid"].includes(value)) return "green";
    if (["pending", "partial"].includes(value)) return "amber";
    return "blue";
  }

  /* ======================================================
     DATA
  ====================================================== */

  async function load(range) {
    if (state.loading) return;
    state.loading = true;
    $("liveButton").classList.add("is-loading");

    try {
      const response = await fetch("/dashboard_overview?range=" + encodeURIComponent(range), {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
        cache: "no-store",
      });

      if (response.status === 401) {
        showAlert(
          'Your session has ended. <a href="/login.html?next=' +
            encodeURIComponent(location.pathname) +
            '">Log in again</a> to see live data.'
        );
        renderErrors("Log in to see this data.");
        return;
      }

      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }

      state.data = await response.json();
      state.range = state.data.range || range;
      hideAlert();
      render();
    } catch (error) {
      console.error("Dashboard error:", error);
      if (!state.data) {
        renderErrors("Unable to load this section. Please try again.");
      }
      showAlert("Couldn't refresh the dashboard. Check that the server is running, then try again.");
    } finally {
      state.loading = false;
      $("liveButton").classList.remove("is-loading");
    }
  }

  function showAlert(html) {
    const alert = $("dashAlert");
    alert.innerHTML = html;
    alert.classList.add("show");
  }

  function hideAlert() {
    $("dashAlert").classList.remove("show");
  }

  function renderErrors(message) {
    const html = '<div class="panel-state error">' + esc(message) + "</div>";
    ["chartWrap", "recentBody", "activityList"].forEach(function (id) {
      const el = $(id);
      if (!el) return;
      if (id === "recentBody") {
        el.innerHTML = '<tr><td colspan="7">' + html + "</td></tr>";
      } else {
        el.innerHTML = html;
      }
    });
  }

  /* ======================================================
     RENDER
  ====================================================== */

  function render() {
    const data = state.data;
    renderWelcome(data.user);
    renderCards(data.cards);
    renderLegend();
    renderChart(data.series);
    renderTotals(data.totals);
    renderRecent(data.recent_registrations, data.now);
    renderActivity($("activityList"), data.activity, data.now);
    renderNotifications(data.activity, data.now);
    $("rangeSelect").value = state.range;
  }

  function renderWelcome(user) {
    const fullname = (user && user.fullname) || "";
    let name = VARIANT === "admin" ? "Administrator" : "Team";
    if (fullname && !/administrator/i.test(fullname)) {
      name = fullname.split(/\s+/)[0];
    }
    $("welcomeName").textContent = name + "!";

    if (typeof window.cyfSetUser === "function" && user) {
      window.cyfSetUser(user.fullname, user.role);
    }
  }

  function renderCards(cards) {
    function set(key, trendText) {
      const card = cards[key];
      const root = document.querySelector('[data-card="' + key + '"]');
      if (!root || !card) return;
      root.querySelector(".stat-value").textContent = Number(card.total || 0).toLocaleString();
      const trend = root.querySelector(".stat-trend");
      const count = trendText(card);
      trend.classList.toggle("is-flat", count.value === 0);
      trend.innerHTML = (count.value > 0 ? icon("trendUp") : "") + "<span>" + esc(count.text) + "</span>";
    }

    ["participants", "staff", "chaperones"].forEach(function (key) {
      set(key, function (card) {
        return {
          value: card.this_week,
          text: card.this_week > 0 ? "+" + card.this_week + " this week" : "No new this week",
        };
      });
    });

    set("events", function (card) {
      return {
        value: card.upcoming,
        text: card.upcoming > 0 ? "+" + card.upcoming + " upcoming" : "None upcoming",
      };
    });
  }

  function renderLegend() {
    $("chartLegend").innerHTML = SERIES.map(function (s) {
      return '<span><i style="--dot:' + s.color + '"></i>' + esc(s.label) + "</span>";
    }).join("");
  }

  function renderTotals(totals) {
    $("totalValue").textContent = Number(totals.total || 0).toLocaleString();

    const change = $("totalChange");
    change.className = "totals-change";
    if (totals.change_percent === null || totals.change_percent === undefined) {
      change.innerHTML =
        "<strong>" + Number(totals.this_month || 0).toLocaleString() + " this month</strong>no data last month";
    } else {
      const up = totals.change_percent >= 0;
      change.classList.add(up ? "up" : "down");
      change.innerHTML =
        "<strong>" + (up ? "▲ +" : "▼ ") + totals.change_percent + "%</strong>vs. last month";
    }

    $("totalRows").innerHTML = SERIES.map(function (s) {
      const row = (totals.breakdown || {})[s.key] || { count: 0, percent: 0 };
      return (
        '<div class="totals-row"><i style="--dot:' + s.color + '"></i><span>' + esc(s.label) +
        "</span><b>" + Number(row.count).toLocaleString() + "</b><span>" + row.percent + "%</span></div>"
      );
    }).join("");
  }

  function categoryInfo(type) {
    if (type === "staff") return { label: "Staff", tone: "amber", page: PAGES.staff, title: "Staff" };
    if (type === "chaperone") return { label: "Chaperone", tone: "green", page: PAGES.chaperones, title: "Chaperones" };
    return { label: "Participant", tone: "rose", page: PAGES.participants, title: "Participants" };
  }

  function renderRecent(rows) {
    const body = $("recentBody");
    if (!rows || !rows.length) {
      body.innerHTML = '<tr><td colspan="7"><div class="panel-state">No registrations yet.</div></td></tr>';
      return;
    }

    body.innerHTML = rows
      .map(function (row) {
        const cat = categoryInfo(row.type);
        const reference = row.reference ? esc(row.reference) : "ID " + esc(row.id);
        return (
          "<tr>" +
          "<td>" + reference + "</td>" +
          "<td>" + (row.event_name ? tonedPill(row.event_name, eventTone(row.event_name)) : "—") + "</td>" +
          '<td><span class="person"><span class="mini-avatar" style="--tone-soft:var(--c-' +
          cat.tone + '-soft)">' + esc(initials(row.name)) + "</span>" + esc(row.name || "—") + "</span></td>" +
          "<td>" + tonedPill(cat.label, cat.tone) + "</td>" +
          "<td>" + tonedPill(row.status, statusTone(row.status)) + "</td>" +
          "<td>" + esc(formatDateTime(row.created_at)) + "</td>" +
          '<td><a class="row-menu" href="' + cat.page + '" title="Open in ' + cat.title +
          '" aria-label="Open ' + esc(row.name) + " in " + cat.title + '">' + icon("dots") + "</a></td>" +
          "</tr>"
        );
      })
      .join("");
  }

  const ACTIVITY_ICONS = {
    participant: "plus",
    staff: "user",
    chaperone: "shield",
    event: "calendar",
    payment: "card",
    sponsor: "heart",
  };

  function renderActivity(list, items, now) {
    if (!list) return;
    if (!items || !items.length) {
      list.innerHTML = '<li class="panel-state">No recent activity.</li>';
      return;
    }

    list.innerHTML = items
      .map(function (item) {
        return (
          '<li class="activity-item">' +
          '<span class="activity-icon tone-' + esc(item.kind) + '">' + icon(ACTIVITY_ICONS[item.kind] || "plus") + "</span>" +
          "<span><strong>" + esc(item.title) + "</strong><small>" + esc(item.detail) + "</small></span>" +
          '<span class="activity-time">' + esc(relativeTime(item.at, now)) + "</span>" +
          "</li>"
        );
      })
      .join("");
  }

  function renderNotifications(items, now) {
    const nowDate = parseTime(now) || new Date();
    const recent = (items || []).filter(function (item) {
      const at = parseTime(item.at);
      return at && nowDate - at <= 24 * 3600 * 1000;
    });

    const badge = $("notifyBadge");
    badge.hidden = recent.length === 0;
    badge.textContent = recent.length > 9 ? "9+" : String(recent.length);
    $("notifyButton").setAttribute(
      "aria-label",
      recent.length ? recent.length + " new notifications" : "Notifications"
    );

    const list = $("notifyList");
    if (!recent.length) {
      list.innerHTML = '<li class="popover-empty">You’re all caught up. Nothing new in the last 24 hours.</li>';
    } else {
      renderActivity(list, recent, now);
    }
  }

  /* ======================================================
     CHART (inline SVG, monotone curves)
  ====================================================== */

  function niceMax(value) {
    if (value <= 4) return 4;
    const step = Math.pow(10, Math.floor(Math.log10(value)));
    const scaled = value / step;
    const nice = scaled <= 1 ? 1 : scaled <= 2 ? 2 : scaled <= 2.5 ? 2.5 : scaled <= 5 ? 5 : 10;
    return nice * step;
  }

  // Fritsch–Carlson monotone cubic → SVG path (no overshoot below 0).
  function smoothPath(points) {
    const n = points.length;
    if (n === 0) return "";
    if (n === 1) return "M" + points[0][0] + "," + points[0][1];

    const dx = [], dy = [], m = [], t = [];
    for (let i = 0; i < n - 1; i++) {
      dx.push(points[i + 1][0] - points[i][0]);
      dy.push(points[i + 1][1] - points[i][1]);
      m.push(dy[i] / dx[i]);
    }
    t.push(m[0]);
    for (let i = 1; i < n - 1; i++) {
      t.push(m[i - 1] * m[i] <= 0 ? 0 : (m[i - 1] + m[i]) / 2);
    }
    t.push(m[n - 2]);
    for (let i = 0; i < n - 1; i++) {
      if (m[i] === 0) {
        t[i] = 0;
        t[i + 1] = 0;
        continue;
      }
      const a = t[i] / m[i], b = t[i + 1] / m[i], s = a * a + b * b;
      if (s > 9) {
        const k = 3 / Math.sqrt(s);
        t[i] = k * a * m[i];
        t[i + 1] = k * b * m[i];
      }
    }

    let d = "M" + points[0][0].toFixed(1) + "," + points[0][1].toFixed(1);
    for (let i = 0; i < n - 1; i++) {
      const h = dx[i] / 3;
      d +=
        " C" + (points[i][0] + h).toFixed(1) + "," + (points[i][1] + t[i] * h).toFixed(1) +
        " " + (points[i + 1][0] - h).toFixed(1) + "," + (points[i + 1][1] - t[i + 1] * h).toFixed(1) +
        " " + points[i + 1][0].toFixed(1) + "," + points[i + 1][1].toFixed(1);
    }
    return d;
  }

  function renderChart(series) {
    const wrap = $("chartWrap");
    const labels = series.labels || [];
    const width = Math.max(300, wrap.clientWidth || 600);
    const height = 250;
    const pad = { top: 14, right: 18, bottom: 30, left: 40 };
    const innerW = width - pad.left - pad.right;
    const innerH = height - pad.top - pad.bottom;

    const allValues = [];
    SERIES.forEach(function (s) {
      (series[s.key] || []).forEach(function (v) {
        allValues.push(v);
      });
    });
    const max = niceMax(Math.max(0, ...allValues));
    // Prefer a tick count that keeps every axis label a whole number.
    const ticks = [4, 5, 3].find(function (t) {
      return Number.isInteger(max / t);
    }) || 4;
    const n = labels.length;
    const x = function (i) {
      return pad.left + (n <= 1 ? innerW / 2 : (innerW * i) / (n - 1));
    };
    const y = function (v) {
      return pad.top + innerH - (innerH * v) / max;
    };

    const labelEvery = n > 16 ? Math.ceil(n / 8) : 1;
    let svg =
      '<svg viewBox="0 0 ' + width + " " + height + '" role="img" aria-label="Registrations over time">' +
      "<defs>" +
      SERIES.map(function (s) {
        return (
          '<linearGradient id="grad-' + s.key + '" x1="0" y1="0" x2="0" y2="1">' +
          '<stop offset="0" stop-color="' + s.color + '" stop-opacity=".22"/>' +
          '<stop offset="1" stop-color="' + s.color + '" stop-opacity="0"/></linearGradient>'
        );
      }).join("") +
      "</defs>";

    svg += '<g class="chart-grid">';
    for (let i = 0; i <= ticks; i++) {
      const value = (max / ticks) * i;
      svg += '<line x1="' + pad.left + '" x2="' + (width - pad.right) + '" y1="' + y(value) + '" y2="' + y(value) + '"/>';
    }
    svg += "</g>";

    svg += '<g class="chart-axis">';
    for (let i = 0; i <= ticks; i++) {
      const value = (max / ticks) * i;
      svg += '<text x="' + (pad.left - 10) + '" y="' + (y(value) + 4) + '" text-anchor="end">' +
        (Number.isInteger(value) ? value : value.toFixed(1)) + "</text>";
    }
    labels.forEach(function (label, i) {
      if (i % labelEvery !== 0 && i !== n - 1) return;
      svg += '<text x="' + x(i) + '" y="' + (height - 8) + '" text-anchor="middle">' + esc(label) + "</text>";
    });
    svg += "</g>";

    const showDots = n <= 12;
    SERIES.forEach(function (s) {
      const values = series[s.key] || [];
      const points = values.map(function (v, i) {
        return [x(i), y(v)];
      });
      const line = smoothPath(points);
      if (points.length > 1) {
        svg += '<path d="' + line + " L" + x(n - 1) + "," + y(0) + " L" + x(0) + "," + y(0) +
          ' Z" fill="url(#grad-' + s.key + ')"/>';
      }
      svg += '<path d="' + line + '" fill="none" stroke="' + s.color + '" stroke-width="2.5" stroke-linecap="round"/>';
      if (showDots) {
        points.forEach(function (p) {
          svg += '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="4.5" fill="' + s.color + '" stroke="#fff" stroke-width="2"/>';
        });
      }
    });

    svg += '<g class="chart-hover" id="chartHover" style="display:none"><line y1="' + pad.top + '" y2="' + (pad.top + innerH) + '"/>';
    SERIES.forEach(function (s) {
      svg += '<circle r="5.5" fill="' + s.color + '" stroke="#fff" stroke-width="2.5" data-key="' + s.key + '"/>';
    });
    svg += "</g>";
    svg += '<rect x="' + pad.left + '" y="' + pad.top + '" width="' + innerW + '" height="' + innerH +
      '" fill="transparent" id="chartCapture"/>';
    svg += "</svg>";

    wrap.innerHTML = svg + '<div class="chart-tip" id="chartTip" hidden></div>';

    const capture = $("chartCapture");
    const hover = $("chartHover");
    const tip = $("chartTip");
    const svgEl = wrap.querySelector("svg");

    function show(clientX) {
      const box = svgEl.getBoundingClientRect();
      const scale = width / box.width;
      const px = (clientX - box.left) * scale;
      const i = n <= 1 ? 0 : Math.max(0, Math.min(n - 1, Math.round(((px - pad.left) / innerW) * (n - 1))));
      const cx = x(i);

      hover.style.display = "";
      hover.querySelector("line").setAttribute("x1", cx);
      hover.querySelector("line").setAttribute("x2", cx);
      hover.querySelectorAll("circle").forEach(function (c) {
        c.setAttribute("cx", cx);
        c.setAttribute("cy", y((series[c.dataset.key] || [])[i] || 0));
      });

      tip.innerHTML =
        "<strong>" + esc(state.range === "month" ? labelMonthDay(labels[i]) : labels[i]) + "</strong>" +
        SERIES.map(function (s) {
          return '<div><i style="--dot:' + s.color + '"></i>' + esc(s.label) + "<b>" +
            ((series[s.key] || [])[i] || 0) + "</b></div>";
        }).join("");
      tip.hidden = false;
      tip.style.left = cx / scale + "px";
      tip.style.top = pad.top / scale + "px";
    }

    function hide() {
      hover.style.display = "none";
      tip.hidden = true;
    }

    capture.addEventListener("mousemove", function (e) {
      show(e.clientX);
    });
    capture.addEventListener("mouseleave", hide);
    capture.addEventListener("touchstart", function (e) {
      show(e.touches[0].clientX);
    }, { passive: true });
  }

  function labelMonthDay(day) {
    const now = parseTime(state.data && state.data.now) || new Date();
    return now.toLocaleDateString("en-US", { month: "short" }) + " " + day;
  }

  /* ======================================================
     SEARCH (Ctrl + K)
  ====================================================== */

  function setupSearch() {
    const input = $("dashSearch");
    const panel = $("searchResults");
    let timer = null;
    let requestId = 0;
    let active = -1;

    function items() {
      return Array.from(panel.querySelectorAll(".result-item"));
    }

    function setActive(index) {
      const list = items();
      list.forEach(function (el, i) {
        el.classList.toggle("is-active", i === index);
      });
      active = index;
      if (list[index]) list[index].scrollIntoView({ block: "nearest" });
    }

    async function run(query) {
      const id = ++requestId;
      const q = query.toLowerCase();
      const events = ((state.data && state.data.events) || []).filter(function (e) {
        return String(e.event_name || "").toLowerCase().includes(q);
      }).slice(0, 4);

      let people = [];
      try {
        const response = await fetch("/registration_search_participant?keyword=" + encodeURIComponent(query), {
          headers: { Accept: "application/json" },
          cache: "no-store",
        });
        if (response.ok) {
          const data = await response.json();
          people = (Array.isArray(data) ? data : []).slice(0, 6);
        }
      } catch (error) {
        console.error("Search error:", error);
      }

      if (id !== requestId) return;

      let html = "";
      if (events.length) {
        html += '<div class="popover-title">Events</div>' + events.map(function (e) {
          return '<a class="result-item" href="' + PAGES.events + '"><span class="mini-avatar" style="--tone-soft:var(--c-blue-soft);--tone:#1f6fd1">' +
            icon("calendar") + "</span><span><strong>" + esc(e.event_name) + "</strong><small>Kick-off " +
            esc(e.kickoff_date || "TBA") + "</small></span></a>";
        }).join("");
      }
      if (people.length) {
        html += '<div class="popover-title">Participants</div>' + people.map(function (p) {
          return '<a class="result-item" href="' + PAGES.participants + '"><span class="mini-avatar">' +
            esc(initials(p.fullname)) + "</span><span><strong>" + esc(p.fullname || "Participant") +
            "</strong><small>" + esc([p.registration_number, p.event_name].filter(Boolean).join(" • ")) +
            "</small></span></a>";
        }).join("");
      }
      panel.innerHTML = html || '<div class="popover-empty">No matches for “' + esc(query) + "”.</div>";
      panel.hidden = false;
      active = -1;
    }

    input.addEventListener("input", function () {
      clearTimeout(timer);
      const query = input.value.trim();
      if (query.length < 2) {
        panel.hidden = true;
        return;
      }
      panel.innerHTML = '<div class="popover-empty">Searching…</div>';
      panel.hidden = false;
      timer = setTimeout(function () {
        run(query);
      }, 250);
    });

    input.addEventListener("keydown", function (e) {
      const list = items();
      if (e.key === "ArrowDown" && list.length) {
        e.preventDefault();
        setActive((active + 1) % list.length);
      } else if (e.key === "ArrowUp" && list.length) {
        e.preventDefault();
        setActive((active - 1 + list.length) % list.length);
      } else if (e.key === "Enter" && list[active]) {
        e.preventDefault();
        list[active].click();
      } else if (e.key === "Escape") {
        panel.hidden = true;
        input.blur();
      }
    });

    input.addEventListener("focus", function () {
      if (input.value.trim().length >= 2 && panel.innerHTML) panel.hidden = false;
    });

    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        input.focus();
        input.select();
      }
    });

    document.addEventListener("click", function (e) {
      if (!e.target.closest(".dash-search")) panel.hidden = true;
    });
  }

  /* ======================================================
     NOTIFICATIONS, SIDEBAR, LIVE REFRESH
  ====================================================== */

  function setupNotifications() {
    const button = $("notifyButton");
    const panel = $("notifyPanel");

    button.addEventListener("click", function (e) {
      e.stopPropagation();
      const open = panel.hidden;
      document.querySelectorAll(".cyf-user-menu").forEach(function (m) {
        m.hidden = true;
      });
      panel.hidden = !open;
      button.setAttribute("aria-expanded", String(open));
    });

    document.addEventListener("click", function (e) {
      if (!e.target.closest(".notify-wrap")) {
        panel.hidden = true;
        button.setAttribute("aria-expanded", "false");
      }
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") panel.hidden = true;
    });
  }

  function setupSidebarToggle() {
    const layout = document.querySelector(".layout");
    const sidebar = $("sidebar");

    $("menuButton").addEventListener("click", function () {
      if (window.matchMedia("(max-width: 1100px)").matches) {
        sidebar.classList.toggle("open");
      } else {
        layout.classList.toggle("sidebar-collapsed");
      }
    });

    $("sidebarBackdrop").addEventListener("click", function () {
      sidebar.classList.remove("open");
    });
  }

  function setupLive() {
    $("liveButton").addEventListener("click", function () {
      load(state.range);
    });

    $("rangeSelect").addEventListener("change", function (e) {
      load(e.target.value);
    });

    setInterval(function () {
      if (!document.hidden) load(state.range);
    }, REFRESH_MS);

    // Redraw the chart whenever its box changes size (window resize,
    // sidebar collapse, layout settling after fonts load).
    let lastWidth = 0;
    let resizeTimer = null;
    const redraw = function () {
      const width = $("chartWrap").clientWidth;
      if (!state.data || Math.abs(width - lastWidth) < 2) return;
      lastWidth = width;
      renderChart(state.data.series);
    };
    if ("ResizeObserver" in window) {
      new ResizeObserver(function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(redraw, 100);
      }).observe($("chartWrap"));
    } else {
      window.addEventListener("resize", function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(redraw, 150);
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupSearch();
    setupNotifications();
    setupSidebarToggle();
    setupLive();
    load(state.range);
  });
})();
