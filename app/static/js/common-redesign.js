/**
 * CronPilot — Common Utilities
 * ======================================
 * Core JS for all pages (AJAX form handling, CSRF, anti-double-submit).
 *
 * Dependencies: jQuery (only), CpToast (redesign-toast.js)
 * Constraint: ZERO third-party plugin dependency.
 *
 * Provides:
 *  1. CSRF token global AJAX injection
 *  2. js-ajax-form submit handler
 *  3. POST form anti-double-submit guard
 *  4. getCookie / setCookie utilities
 */
;(function($) {
  'use strict';

  /* ====== 1. CSRF Token Global Injection ====== */
  $.ajaxSetup({
    beforeSend: function(xhr, settings) {
      if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type)) {
        var token = $('meta[name=csrf-token]').attr('content');
        if (token) {
          xhr.setRequestHeader('X-CSRFToken', token);
        }
      }
    }
  });

  /* ====== 2. js-ajax-form Submit Handler ====== */
  $(document).on('click', 'button.js-ajax-submit', function(e) {
    var $btn = $(this);
    var $form = $btn.closest('form.js-ajax-form');
    if (!$form.length) return;

    e.preventDefault();

    if ($btn.data('loading')) return;

    if (!$form.attr('novalidate') && $form[0].checkValidity && !$form[0].checkValidity()) {
      $form[0].reportValidity();
      return;
    }

    $btn.data('loading', true);
    var origText = $btn.text();
    $btn.text(origText + '中…').prop('disabled', true).addClass('disabled');

    var url = $btn.data('action') || $form.attr('action');

    var formData = $form.serialize();
    var csrfToken = $('meta[name=csrf-token]').attr('content');
    var csrfParam = $('meta[name=csrf-param]').attr('content') || 'csrf_token';
    if (csrfToken) {
      formData += '&' + encodeURIComponent(csrfParam) + '=' + encodeURIComponent(csrfToken);
    }

    $.ajax({
      url: url,
      type: 'POST',
      data: formData,
      dataType: 'json',
      success: function(data) {
        $btn.removeClass('disabled').prop('disabled', false).text(origText);

        if (data.errmsg && window.CpToast) {
          if (data.errcode === 0) {
            CpToast.success(data.errmsg);
          } else {
            $form.find('.tf-field-error').removeClass('tf-field-error');
            $form.find('.tf-section-error').removeClass('tf-section-error');
            $form.find('.tf-error-msg').each(function() {
              var $prev = $(this).prev('.tf-hint');
              if ($prev.length) $prev.show();
              $(this).remove();
            });

            var fk = (data.result && data.result.field) || (data.data && data.data.field);
            var inlined = false;
            if (fk) {
              var $el = $form.find('[data-field="' + fk + '"]');
              if (!$el.length) $el = $form.find('#' + fk);
              if ($el.length) {
                var isSection = $el.find('.tf-field').length > 0;
                $el.addClass(isSection ? 'tf-section-error' : 'tf-field-error');

                var $errMsg = $('<div class="tf-error-msg" role="alert"></div>').text(data.errmsg);
                if (isSection) {
                  $el.find('> .tf-label').after($errMsg);
                } else {
                  var $hint = $el.find('.tf-hint');
                  if ($hint.length) {
                    $hint.hide();
                    $hint.after($errMsg);
                  } else {
                    $el.append($errMsg);
                  }
                }

                $el[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
                inlined = true;
              }
            }
            if (!inlined) {
              CpToast.error(data.errmsg);
            }
          }
        }

        if (data.url && data.errcode === 0) {
          window.location.href = data.url;
        } else if (data.url && data.errcode !== 0) {
          setTimeout(function() { window.location.href = data.url; }, 800);
        } else if (data.errcode === 0) {
          var loc = window.location;
          loc.href = loc.pathname + loc.search;
        }
      },
      error: function(xhr) {
        $btn.removeClass('disabled').prop('disabled', false).text(origText);
        try {
          var resp = JSON.parse(xhr.responseText);
          if (window.CpToast) CpToast.error(resp.errmsg || '操作失败');
        } catch(ex) {
          if (window.CpToast) CpToast.error('网络错误，请重试');
        }
      },
      complete: function() {
        $btn.data('loading', false);
      }
    });
  });

  $(document).on('submit', 'form.js-ajax-form', function(e) {
    e.preventDefault();
  });

  /* ====== 3. POST Anti-Double-Submit Guard ====== */
  $(document).on('submit', 'form:not(.js-ajax-form)', function() {
    var $form = $(this);
    if ($form.attr('method') && $form.attr('method').toLowerCase() !== 'post') return;
    var $btn = $form.find('[type="submit"]');
    if (!$btn.length) return;
    if ($btn.data('cp-submitting')) return false;
    $btn.data('cp-submitting', true);
    var origText = $btn.is('input') ? $btn.val() : $btn.text();
    if ($btn.is('input')) {
      $btn.val(origText + '中…');
    } else {
      $btn.text(origText + '中…');
    }
    $btn.prop('disabled', true).addClass('disabled');
    setTimeout(function() {
      $btn.data('cp-submitting', false).prop('disabled', false).removeClass('disabled');
      if ($btn.is('input')) { $btn.val(origText); } else { $btn.text(origText); }
    }, 3000);
  });

  /* ====== 4. Cookie Utilities ====== */
  window.getCookie = function(name) {
    var nameEQ = name + '=';
    var ca = document.cookie.split(';');
    for (var i = 0; i < ca.length; i++) {
      var c = ca[i].replace(/^\s+/, '');
      if (c.indexOf(nameEQ) === 0) {
        return c.substring(nameEQ.length);
      }
    }
    return null;
  };

  window.setCookie = function(name, value, days) {
    var expire = new Date();
    if (!days) days = 1;
    expire.setTime(expire.getTime() + 86400000 * days);
    document.cookie = name + '=' + encodeURIComponent(value) +
      ';path=/;expires=' + expire.toUTCString() + ';samesite=lax';
  };

  /* ====== 5. HTML Escape Utility ====== */
  window.escHtml = function(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  };

})(jQuery);
