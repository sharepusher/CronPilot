/* Task edit preflight: no persistence, no credentials copied into HTML or storage. */
;(function($) {
  'use strict';
  $(function() {
    var $form = $('form.js-cron-edit-noop');
    if (!$form.length) return;

    function state() {
      var result = {};
      $form.serializeArray().forEach(function(item) {
        if (item.name === 'csrf_token' || item.name === 'edit_snapshot') return;
        // Preserve every submitted field; unfamiliar fields fail conservatively by differing.
        var value = item.value;
        if (/^(task_name|task_keyword|req_url|req_body)$/.test(item.name)) value = $.trim(value);
        if (item.name === 'req_method') value = $.trim(value).toUpperCase();
        if (item.name === 'tags') {
          var names = {};
          value.split(',').forEach(function(name) {
            name = $.trim(name).toLowerCase();
            if (name) names['tag:' + name] = true;
          });
          value = Object.keys(names).sort();
        }
        if (!result[item.name]) result[item.name] = [];
        result[item.name].push(value);
      });
      return JSON.stringify(result);
    }

    var original = state();
    // Native error re-render retains T0 in the signed token. Do not mistake the
    // displayed submitted R for a new local baseline and suppress a valid retry.
    var hasError = $form.closest('.tf-container').find('[role="alert"]').length > 0;
    $form.on('cp:form-before-ajax-submit', function(event) {
      // Blur adds tags asynchronously on this page. Commit pending input before comparison.
      if (window.tagsInput && $.trim(window.tagsInput.value) && window.addTag) {
        window.addTag(window.tagsInput.value);
      }
      if (hasError || state() !== original) return;
      event.preventDefault();
      if (window.CpToast) window.CpToast.success('未检测到变更，无需保存');
    });
    // Native Enter submit must use the same preflight and double-submit guard as clicking.
    $form.on('submit', function(event) {
      event.preventDefault();
      $form.find('button.js-ajax-submit').first().trigger('click');
    });
    $('.js-cron-edit-reload').on('click', function() {
      if (!window.CpConfirm) return;
      CpConfirm.show({title: '重新加载编辑页',
        body: '重新加载将放弃未保存的输入，并读取任务的当前配置。',
        onConfirm: function() { window.location.assign($form.attr('action')); }});
    });
    $(document).on('cp:form-outcome', function(event, response, sourceForm) {
      if (!sourceForm || sourceForm[0] !== $form[0]) return;
      var outcome = response.data && response.data.outcome;
      if (outcome !== 'conflict' && !(response.data && response.data.reload_required)) return;
      var $container = $form.closest('.tf-container');
      $container.children('[role="alert"]').remove();
      $('<p class="tf-warning" role="alert"></p>').text(response.errmsg).insertBefore($form);
    });
  });
})(jQuery);
