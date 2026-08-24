/**
 * CronPilot Redesign — Confirm Modal & Generic Modal
 * ====================================================
 * CpConfirm.show({ title, body, confirmText, cancelText, danger, onConfirm }) → Promise<bool>
 * CpModal({ title, bodyHtml, confirmText, cancelText, confirmClass, danger, onConfirm(overlay,close) }) → overlay el
 */
(function() {
  'use strict';

  var active = null;
  var escHandler = null;

  function dismissActive(result) {
    if (!active) return;
    var item = active;
    active = null;
    if (escHandler) {
      document.removeEventListener('keydown', escHandler);
      escHandler = null;
    }
    if (item.overlay.parentNode) {
      item.overlay.parentNode.removeChild(item.overlay);
    }
    item.resolve(result);
  }

  window.CpConfirm = {
    show: function(opts) {
      opts = opts || {};
      var title = opts.title || '确认';
      var body = opts.body || '';
      var confirmText = opts.confirmText || '确认';
      var cancelText = opts.cancelText || '取消';
      var danger = !!opts.danger;
      var onConfirm = opts.onConfirm;

      if (active) {
        dismissActive(false);
      }

      return new Promise(function(resolve) {
        var overlay = document.createElement('div');
        overlay.className = 'cp-modal-overlay';

        var confirmBtnClass = danger ? 'btn-c btn-danger-c' : 'btn-c btn-accent';

        overlay.innerHTML =
          '<div class="cp-modal" role="dialog" aria-modal="true">' +
            '<div class="cp-modal-header">' +
              '<h2></h2>' +
            '</div>' +
            '<div class="cp-modal-body"></div>' +
            '<div class="cp-modal-footer">' +
              '<button type="button" class="btn-c btn-line cp-modal-cancel"></button>' +
              '<button type="button" class="' + confirmBtnClass + ' cp-modal-confirm"></button>' +
            '</div>' +
          '</div>';

        overlay.querySelector('h2').textContent = title;
        overlay.querySelector('.cp-modal-body').textContent = body;
        overlay.querySelector('.cp-modal-cancel').textContent = cancelText;
        overlay.querySelector('.cp-modal-confirm').textContent = confirmText;

        var modal = overlay.querySelector('.cp-modal');

        function doConfirm() {
          if (typeof onConfirm === 'function') {
            onConfirm();
          }
          dismissActive(true);
        }

        function doCancel() {
          dismissActive(false);
        }

        overlay.querySelector('.cp-modal-cancel').addEventListener('click', doCancel);
        overlay.querySelector('.cp-modal-confirm').addEventListener('click', doConfirm);

        overlay.addEventListener('click', function(e) {
          if (e.target === overlay) {
            doCancel();
          }
        });

        modal.addEventListener('click', function(e) {
          e.stopPropagation();
        });

        escHandler = function(e) {
          if (e.key === 'Escape') {
            doCancel();
          }
        };
        document.addEventListener('keydown', escHandler);

        document.body.appendChild(overlay);
        overlay.style.display = 'flex';
        active = { overlay: overlay, resolve: resolve };

        overlay.querySelector('.cp-modal-confirm').focus();
      });
    }
  };

  /* ── Generic HTML-body modal (window.CpModal) ── */
  window.CpModal = function(opts) {
    /* opts: title, bodyHtml, confirmText, cancelText, confirmClass, danger, onConfirm(overlay, close) */
    var overlay = document.createElement('div');
    overlay.className = 'cp-modal-overlay';
    var confirmCls = opts.confirmClass || ('btn-c ' + (opts.danger ? 'btn-danger-c' : 'btn-accent'));

    overlay.innerHTML =
      '<div class="cp-modal" role="dialog" aria-modal="true">' +
        '<div class="cp-modal-header"><h2></h2></div>' +
        '<div class="cp-modal-body"></div>' +
        '<div class="cp-modal-footer"></div>' +
      '</div>';

    overlay.querySelector('h2').textContent = opts.title || '';
    overlay.querySelector('.cp-modal-body').innerHTML = opts.bodyHtml || '';

    var footerEl = overlay.querySelector('.cp-modal-footer');
    if (opts.cancelText) {
      var cancelEl = document.createElement('button');
      cancelEl.type = 'button';
      cancelEl.className = 'btn-c btn-line cp-modal-cancel-btn';
      cancelEl.textContent = opts.cancelText;
      footerEl.appendChild(cancelEl);
    }
    if (opts.confirmText) {
      var confirmEl = document.createElement('button');
      confirmEl.type = 'button';
      confirmEl.className = confirmCls + ' cp-modal-confirm-btn';
      confirmEl.textContent = opts.confirmText;
      footerEl.appendChild(confirmEl);
    }

    function close() {
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
      document.removeEventListener('keydown', escFn);
    }

    var cancelBtn = overlay.querySelector('.cp-modal-cancel-btn');
    var confirmBtn = overlay.querySelector('.cp-modal-confirm-btn');

    if (cancelBtn) cancelBtn.addEventListener('click', close);
    if (confirmBtn) {
      confirmBtn.addEventListener('click', function() {
        if (typeof opts.onConfirm === 'function') {
          opts.onConfirm(overlay, close);
        } else {
          close();
        }
      });
    }

    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) close();
    });

    var escFn = function(e) {
      if (e.key === 'Escape') close();
    };
    document.addEventListener('keydown', escFn);

    document.body.appendChild(overlay);
    return overlay;
  };

})();
