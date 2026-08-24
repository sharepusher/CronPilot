/**
 * CronPilot Redesign — Theme Toggle
 * ====================================
 * OPT-P1-16 Phase 1
 *
 * Light/Dark theme switching with Cookie persistence.
 * Works alongside the existing cp_theme cookie mechanism.
 */
(function() {
  'use strict';

  var lightBtn = document.getElementById('cp-theme-light');
  var darkBtn = document.getElementById('cp-theme-dark');

  function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    document.cookie = 'cp_theme=' + theme + ';path=/;max-age=31536000;samesite=lax';

    if (lightBtn && darkBtn) {
      lightBtn.classList.toggle('on', theme === 'light');
      darkBtn.classList.toggle('on', theme === 'dark');
    }
  }

  if (lightBtn) {
    lightBtn.addEventListener('click', function() { setTheme('light'); });
  }
  if (darkBtn) {
    darkBtn.addEventListener('click', function() { setTheme('dark'); });
  }

  // Expose for programmatic use
  window.CpTheme = { set: setTheme };

})();
