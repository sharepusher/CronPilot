/* 明确目标首次确认；原目标重试使用签名，不再次取反。 */
window.CpStatus = (function () {
  function send(id, target, button, token) {
    if (button && button.dataset.cpStatusBusy === '1') return;
    if (button) { button.dataset.cpStatusBusy = '1'; button.disabled = true; }
    var data = {id: id, status: target, csrf_token: document.querySelector('meta[name=csrf-token]').content};
    if (token) data.retry_token = token;
    function done() {
      if (button) { delete button.dataset.cpStatusBusy; button.disabled = false; }
    }
    function retryButton(nextToken, message) {
      done(); CpToast.error(message);
      var retry = document.createElement('button');
      retry.type = 'button'; retry.className = 'btn';
      retry.textContent = target === 0 ? '重试暂停' : '重试启动';
      retry.onclick = function () {
        if (nextToken) { send(id, target, retry, nextToken); return; }
        if (retry.dataset.cpStatusBusy === '1') return;
        retry.dataset.cpStatusBusy = '1'; retry.disabled = true;
        $.get('/cron_status_check', {id: id}).done(function (r) {
          delete retry.dataset.cpStatusBusy; retry.disabled = false;
          if (r.errcode !== 0 || !r.result || r.result.target !== target) {
            CpToast.error(r.errmsg || '目标已有变化，请刷新确认'); return;
          }
          send(id, target, retry, r.result.retry_token);
        }).fail(function () {
          delete retry.dataset.cpStatusBusy; retry.disabled = false;
          CpToast.error('暂时无法读取目标，可稍后重试');
        });
      };
      var parent = button && button.parentElement;
      if (parent) {
        var previous = parent.querySelector('[data-cp-status-retry]');
        if (previous) previous.remove();
        retry.dataset.cpStatusRetry = '1'; parent.appendChild(retry);
      }
    }
    $.post(token ? '/cron_status_apply' : '/update_status', data).done(function (r) {
      if (r.errcode === 0) { done(); CpToast.success(r.errmsg); setTimeout(function () { location.reload(); }, 600); }
      else if (r.result && r.result.retry_token) retryButton(r.result.retry_token, r.errmsg);
      else { done(); CpToast.error(r.errmsg || '操作未完成，请刷新确认'); }
    }).fail(function (xhr) {
      if (xhr.status >= 400 && xhr.status < 500) {
        done(); CpToast.error((xhr.responseJSON && xhr.responseJSON.errmsg) || '请求被拒绝，请检查登录状态和权限');
      } else retryButton(token, '请求结果暂时无法确认，可稍后重试明确目标');
    });
  }
  function reconcile(id, target, button) {
    if (button.dataset.cpStatusBusy === '1') return;
    button.dataset.cpStatusBusy = '1'; button.disabled = true;
    $.get('/cron_status_check', {id: id}).done(function (r) {
      delete button.dataset.cpStatusBusy; button.disabled = false;
      if (r.errcode !== 0 || !r.result || r.result.target !== target) {
        CpToast.error(r.errmsg || '任务目标已有变化，请刷新确认'); return;
      }
      send(id, target, button, r.result.retry_token);
    }).fail(function () {
      delete button.dataset.cpStatusBusy; button.disabled = false;
      CpToast.error('暂时无法核实，可稍后重试');
    });
  }
  return {reconcile: reconcile, perform: function (id, target, button) {
    CpConfirm.show({title: target === 0 ? '暂停任务' : '启动任务',
      body: target === 0 ? '确认暂停任务？已开始的执行不会中止。' : '确认启动任务？',
      confirmText: '确认', cancelText: '取消'}).then(function (ok) { if (ok) send(id, target, button); });
  }};
}());
