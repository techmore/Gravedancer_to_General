/* Gravedancer to General — client-side behavior.
 * No frameworks, no tracking. Vanilla JS, ~3KB.
 * Handles: theme toggle, episode day navigation, archive filters,
 * read-tracking via localStorage, glossary search, mark-as-read.
 */

(function () {
  "use strict";

  var STORAGE = {
    theme: "gd-theme",
    read: "gd-read-episodes"  // JSON array of slugs
  };

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function readList() {
    try { return JSON.parse(localStorage.getItem(STORAGE.read)) || []; }
    catch (e) { return []; }
  }
  function setReadList(list) {
    try { localStorage.setItem(STORAGE.read, JSON.stringify(list)); } catch (e) {}
  }
  function isRead(slug) { return readList().indexOf(slug) !== -1; }
  function markRead(slug) {
    var list = readList();
    if (list.indexOf(slug) === -1) { list.push(slug); setReadList(list); }
  }

  /* ── Theme toggle ─────────────────────────────────── */
  function initTheme() {
    var btn = $("#theme-toggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var current = document.documentElement.getAttribute("data-theme") || "dark";
      var next = current === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem(STORAGE.theme, next); } catch (e) {}
    });
  }

  /* ── Archive: filters ─────────────────────────────── */
  function initArchiveFilters() {
    var list = $("#episode-list");
    if (!list) return;
    var cards = $all(".episode-card", list);
    var empty = $("#archive-empty");

    // Populate jedi + setting dropdowns from data attributes
    ["jedi", "setting"].forEach(function (key) {
      var select = $("#filter-" + key);
      if (!select) return;
      var values = [];
      cards.forEach(function (c) {
        var v = c.getAttribute("data-" + (key === "jedi" ? "jedi" : "setting"));
        if (v && values.indexOf(v) === -1) values.push(v);
      });
      values.sort().forEach(function (v) {
        var opt = document.createElement("option");
        opt.value = v; opt.textContent = v;
        select.appendChild(opt);
      });
    });

    function applyFilters() {
      var s = $("#filter-status").value;
      var j = $("#filter-jedi").value;
      var st = $("#filter-setting").value;
      var visible = 0;
      cards.forEach(function (c) {
        var okS = s === "all" || c.getAttribute("data-status") === s;
        var okJ = j === "all" || c.getAttribute("data-jedi") === j;
        var okSt = st === "all" || c.getAttribute("data-setting") === st;
        if (okS && okJ && okSt) { c.style.display = ""; visible++; }
        else { c.style.display = "none"; }
      });
      if (empty) empty.hidden = visible !== 0;
    }

    $all(".filters select").forEach(function (sel) {
      sel.addEventListener("change", applyFilters);
    });

    // Reflect read state on cards
    cards.forEach(function (c) {
      var m = $(".read-marker", c);
      if (m && isRead(m.getAttribute("data-read-slug"))) {
        c.classList.add("is-read");
        m.classList.add("is-read");
      }
    });
  }

  /* ── Episode reader: day navigation ───────────────── */
  function initReader() {
    var article = $("#episode");
    if (!article) return;
    var slug = article.getAttribute("data-episode-slug");
    var days = $all(".day", article);
    var total = days.length;
    if (total === 0) return;

    var select = $("#day-select");
    var prev = $("#day-prev");
    var next = $("#day-next");
    var progress = $("#day-progress");
    var markBtn = $("#mark-read");

    function showDay(n, push) {
      n = Math.max(1, Math.min(total, n));
      days.forEach(function (d) {
        d.classList.toggle("is-hidden", parseInt(d.getAttribute("data-day"), 10) !== n);
      });
      if (select) select.value = String(n);
      if (progress) progress.textContent = "Day " + n + " of " + total;
      if (prev) prev.disabled = (n === 1);
      if (next) next.disabled = (n === total);
      if (push && history.replaceState) {
        history.replaceState(null, "", "#day-" + n);
      }
      // Auto-mark read when reaching the final day
      if (n === total && slug) {
        markRead(slug);
        reflectMarkBtn();
        reflectArchiveCard();
      }
      // Scroll to top of prose on day change (but not on initial hash load)
      if (push) {
        var prose = $("#prose");
        if (prose) prose.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }

    function currentDay() {
      var m = location.hash.match(/day-(\d+)/);
      if (m) return Math.max(1, Math.min(total, parseInt(m[1], 10)));
      return 1;
    }

    if (select) select.addEventListener("change", function () {
      showDay(parseInt(select.value, 10), true);
    });
    if (prev) prev.addEventListener("click", function () {
      showDay(currentDay() - 1, true);
    });
    if (next) next.addEventListener("click", function () {
      showDay(currentDay() + 1, true);
    });
    window.addEventListener("hashchange", function () { showDay(currentDay(), false); });

    function reflectMarkBtn() {
      if (!markBtn) return;
      if (isRead(slug)) {
        markBtn.classList.add("is-active");
        markBtn.textContent = "✓ Read";
      } else {
        markBtn.classList.remove("is-active");
        markBtn.textContent = "Mark episode as read";
      }
    }
    function reflectArchiveCard() {
      var marker = $('.read-marker[data-read-slug="' + slug + '"]');
      if (marker && isRead(slug)) {
        marker.classList.add("is-read");
        var card = marker.closest(".episode-card");
        if (card) card.classList.add("is-read");
      }
    }
    if (markBtn) markBtn.addEventListener("click", function () {
      markRead(slug);
      reflectMarkBtn();
      reflectArchiveCard();
    });

    // Keyboard nav: left/right between days
    document.addEventListener("keydown", function (e) {
      if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT" || e.target.tagName === "TEXTAREA") return;
      if (e.key === "ArrowLeft") showDay(currentDay() - 1, true);
      else if (e.key === "ArrowRight") showDay(currentDay() + 1, true);
    });

    showDay(currentDay(), false);
    reflectMarkBtn();
  }

  /* ── Glossary search ──────────────────────────────── */
  function initGlossarySearch() {
    var input = $("#glossary-search");
    if (!input) return;
    var entries = $all(".glossary-entry");
    var empty = $("#glossary-empty");
    input.addEventListener("input", function () {
      var q = input.value.trim().toLowerCase();
      var visible = 0;
      entries.forEach(function (e) {
        var match = e.getAttribute("data-term").indexOf(q) !== -1;
        e.classList.toggle("is-hidden", !match);
        if (match) visible++;
      });
      if (empty) empty.hidden = visible !== 0;
    });
  }

  /* ── Boot ─────────────────────────────────────────── */
  document.addEventListener("DOMContentLoaded", function () {
    initTheme();
    initArchiveFilters();
    initReader();
    initGlossarySearch();
  });
})();
