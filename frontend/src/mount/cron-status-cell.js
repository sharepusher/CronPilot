import { createApp } from 'vue'
import CronStatusCell from '../components/CronStatusCell.vue'

function mountAll() {
  document.querySelectorAll('[id^="cron-ops-"]:not(.cron-ops-mounted)').forEach(el => {
    el.classList.add('cron-ops-mounted')
    createApp(CronStatusCell, {
      cronId: Number(el.dataset.cronId),
      status: Number(el.dataset.status),
      canWrite: el.dataset.canWrite === 'true',
      canRetire: el.dataset.canRetire === 'true',
      hasUrl: el.dataset.hasUrl === 'true',
      updateUrl: el.dataset.updateUrl || '',
      runUrl: el.dataset.runUrl || '',
      logUrl: el.dataset.logUrl,
      editUrl: el.dataset.editUrl || '',
      retireUrl: el.dataset.retireUrl || '',
    }).mount(el)
  })
}

mountAll()
// expose so CronFilterBar can remount after tbody innerHTML replacement
window.CronStatusCell = { mountAll }
