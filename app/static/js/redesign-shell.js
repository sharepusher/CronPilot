/**
 * CronPilot Redesign — Shell Interactions
 * =========================================
 * OPT-P1-16 Phase 1
 *
 * Handles: sidebar collapse, user dropdown, mobile menu,
 * Command Palette open/close.
 */
(function() {
  'use strict';

  /* ====== Sidebar Collapse ====== */
  var shell = document.querySelector('.cp-shell');
  var sidebar = document.getElementById('cp-sidebar');

  function toggleSidebar() {
    if (!shell) return;
    shell.classList.toggle('collapsed');
    var collapsed = shell.classList.contains('collapsed') ? '1' : '0';
    document.cookie = 'cp_sidebar_collapsed=' + collapsed + ';path=/;max-age=31536000;samesite=lax';
  }

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

  function openPalette() {
    if (!cmdOverlay) return;
    cmdOverlay.classList.add('open');
    if (cmdInput) {
      cmdInput.value = '';
      cmdInput.focus();
    }
  }

  function closePalette() {
    if (!cmdOverlay) return;
    cmdOverlay.classList.remove('open');
  }

  if (cmdTrigger) {
    cmdTrigger.addEventListener('click', openPalette);
  }

  if (cmdOverlay) {
    cmdOverlay.addEventListener('click', function(e) {
      if (e.target === cmdOverlay) closePalette();
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

  /* ====== Mobile Menu ====== */
  window.CpShell = {
    toggleSidebar: toggleSidebar,
    openPalette: openPalette,
    closePalette: closePalette
  };

})();
