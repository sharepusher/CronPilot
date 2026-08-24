/**
 * CronPilot Redesign — Toast Notifications
 * ===========================================
 * Global API: window.CpToast.success(msg) / .error(msg) / .warning(msg)
 */
(function() {
  'use strict';

  var DEFAULT_DURATION = 4000;

  var ICONS = {
    success: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="var(--cp-success)" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M9 12l2 2 4-4"/></svg>',
    error: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="var(--cp-danger)" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M15 9l-6 6M9 9l6 6"/></svg>',
    warning: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="var(--cp-warn)" stroke-width="2"><path d="M12 8v4M12 16h.01"/><circle cx="12" cy="12" r="9"/></svg>'
  };

  function getContainer() {
    var el = document.getElementById('cp-toast-container');
    if (!el) {
      el = document.createElement('div');
      el.id = 'cp-toast-container';
      el.className = 'toast-container';
      document.body.appendChild(el);
    }
    return el;
  }

  function dismissToast(toastEl) {
    if (toastEl._dismissTimer) {
      clearTimeout(toastEl._dismissTimer);
      toastEl._dismissTimer = null;
    }
    if (toastEl._dismissing) return;
    toastEl._dismissing = true;
    toastEl.classList.add('toast-exit');
    toastEl.addEventListener('animationend', function() {
      if (toastEl.parentNode) {
        toastEl.parentNode.removeChild(toastEl);
      }
    }, { once: true });
  }

  function show(type, message, duration) {
    if (typeof duration === 'undefined') {
      duration = DEFAULT_DURATION;
    }
    var container = getContainer();
    var toast = document.createElement('div');
    toast.className = 'toast ' + type;
    toast.innerHTML = ICONS[type] +
      '<span class="toast-msg"></span>' +
      '<span class="toast-close" role="button" tabindex="0" aria-label="关闭">&times;</span>';
    toast.querySelector('.toast-msg').textContent = message;

    toast.querySelector('.toast-close').addEventListener('click', function() {
      dismissToast(toast);
    });

    container.appendChild(toast);

    if (duration > 0) {
      toast._dismissTimer = setTimeout(function() {
        dismissToast(toast);
      }, duration);
    }

    return toast;
  }

  window.CpToast = {
    success: function(message, duration) {
      return show('success', message, duration);
    },
    error: function(message, duration) {
      return show('error', message, duration);
    },
    warning: function(message, duration) {
      return show('warning', message, duration);
    }
  };
})();
