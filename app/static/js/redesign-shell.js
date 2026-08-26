/**
 * CronPilot Redesign — Shell Interactions
 * =========================================
 * OPT-P1-16 Phase 1 + R3 Functional Completion
 *
 * Handles: sidebar collapse, user dropdown, mobile menu,
 * Command Palette (open/close/search/navigate).
 */
(function() {
  'use strict';

  /* ====== Sidebar Collapse (Desktop) ====== */
  var shell = document.querySelector('.cp-shell');
  var sidebar = document.getElementById('cp-sidebar');

  function toggleSidebar() {
    if (!shell) return;
    shell.classList.toggle('collapsed');
    var collapsed = shell.classList.contains('collapsed') ? '1' : '0';
    document.cookie = 'cp_sidebar_collapsed=' + collapsed + ';path=/;max-age=31536000;samesite=lax';
  }

  /* ====== Mobile Sidebar ====== */
  function openMobileSidebar() {
    if (!sidebar) return;
    sidebar.classList.add('mobile-open');
    document.body.classList.add('cp-mobile-overlay-active');
  }

  function closeMobileSidebar() {
    if (!sidebar) return;
    sidebar.classList.remove('mobile-open');
    document.body.classList.remove('cp-mobile-overlay-active');
  }

  document.addEventListener('click', function(e) {
    if (document.body.classList.contains('cp-mobile-overlay-active')) {
      if (!sidebar.contains(e.target) && !e.target.closest('#cp-mobile-toggle')) {
        closeMobileSidebar();
      }
    }
  });

  /* ====== User Dropdown ====== */
  var userTrigger = document.getElementById('cp-user-menu-trigger');
  var userDropdown = document.getElementById('cp-user-dropdown');

  if (userTrigger && userDropdown) {
    userTrigger.addEventListener('click', function(e) {
      e.stopPropagation();
      userDropdown.classList.toggle('open');
    });

    document.addEventListener('click', function() {
      userDropdown.classList.remove('open');
    });

    userDropdown.addEventListener('click', function(e) {
      e.stopPropagation();
    });
  }

  /* ====== Command Palette ====== */
  var cmdOverlay = document.getElementById('cp-cmd-overlay');
  var cmdTrigger = document.getElementById('cp-cmd-trigger');
  var cmdInput = document.getElementById('cp-cmd-input');
  var cmdResults = document.getElementById('cp-cmd-results');
  var activeIdx = -1;
  var registry = [];

  function buildRegistry() {
    registry = [];
    var navItems = document.querySelectorAll('#cp-sidebar .cp-nav-item');
    for (var i = 0; i < navItems.length; i++) {
      var el = navItems[i];
      var textEl = el.querySelector('span');
      if (!textEl) continue;
      var label = textEl.textContent.trim();
      var href = el.getAttribute('href');
      if (!label || !href) continue;
      var section = '';
      var sectionEl = el.closest('.cp-nav-section');
      if (sectionEl) {
        var sectionLabel = sectionEl.querySelector('.cp-nav-section-label');
        if (sectionLabel) section = sectionLabel.textContent.trim();
      }
      registry.push({ label: label, href: href, section: section, keywords: label + ' ' + section });
    }
  }

  function renderResults(items) {
    if (!cmdResults) return;
    if (items.length === 0) {
      cmdResults.innerHTML = '<div class="cp-cmd-empty">无匹配结果</div>';
      activeIdx = -1;
      return;
    }
    var html = '';
    for (var i = 0; i < items.length; i++) {
      html += '<a class="cp-cmd-item' + (i === 0 ? ' active' : '') + '" href="' + items[i].href + '">' +
        '<span class="cp-cmd-item-label">' + escHtml(items[i].label) + '</span>' +
        '<span class="cp-cmd-item-section">' + escHtml(items[i].section) + '</span>' +
        '</a>';
    }
    cmdResults.innerHTML = html;
    activeIdx = 0;
  }

  function escHtml(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function filterRegistry(query) {
    if (!query) return registry.slice(0, 10);
    var q = query.toLowerCase();
    var matched = [];
    for (var i = 0; i < registry.length; i++) {
      if (registry[i].keywords.toLowerCase().indexOf(q) !== -1) {
        matched.push(registry[i]);
      }
    }
    return matched;
  }

  function setActive(idx) {
    if (!cmdResults) return;
    var items = cmdResults.querySelectorAll('.cp-cmd-item');
    if (items.length === 0) return;
    if (idx < 0) idx = items.length - 1;
    if (idx >= items.length) idx = 0;
    for (var i = 0; i < items.length; i++) {
      items[i].classList.toggle('active', i === idx);
    }
    activeIdx = idx;
    items[idx].scrollIntoView({ block: 'nearest' });
  }

  function openPalette() {
    if (!cmdOverlay) return;
    buildRegistry();
    cmdOverlay.classList.add('open');
    if (cmdInput) {
      cmdInput.value = '';
      cmdInput.focus();
    }
    renderResults(registry.slice(0, 10));
  }

  function closePalette() {
    if (!cmdOverlay) return;
    cmdOverlay.classList.remove('open');
    if (cmdResults) cmdResults.innerHTML = '';
    activeIdx = -1;
  }

  if (cmdTrigger) {
    cmdTrigger.addEventListener('click', openPalette);
  }

  if (cmdOverlay) {
    cmdOverlay.addEventListener('click', function(e) {
      if (e.target === cmdOverlay) closePalette();
    });
  }

  if (cmdInput) {
    cmdInput.addEventListener('input', function() {
      var results = filterRegistry(cmdInput.value.trim());
      renderResults(results);
    });

    cmdInput.addEventListener('keydown', function(e) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActive(activeIdx + 1);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActive(activeIdx - 1);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        var items = cmdResults ? cmdResults.querySelectorAll('.cp-cmd-item') : [];
        if (items.length > 0 && activeIdx >= 0 && activeIdx < items.length) {
          window.location.href = items[activeIdx].getAttribute('href');
        }
      }
    });
  }

  document.addEventListener('keydown', function(e) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      if (cmdOverlay && cmdOverlay.classList.contains('open')) {
        closePalette();
      } else {
        openPalette();
      }
    }
    if (e.key === 'Escape' && cmdOverlay && cmdOverlay.classList.contains('open')) {
      e.preventDefault();
      e.stopPropagation();
      closePalette();
    }
  });

  /* ====== Logout (POST) ====== */
  var logoutBtn = document.getElementById('cp-logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', function(e) {
      e.preventDefault();
      var form = document.getElementById('cp-logout-form');
      if (form) form.submit();
    });
  }

  /* ====== Public API ====== */
  window.CpShell = {
    toggleSidebar: toggleSidebar,
    openMobileSidebar: openMobileSidebar,
    closeMobileSidebar: closeMobileSidebar,
    openPalette: openPalette,
    closePalette: closePalette
  };

})();
