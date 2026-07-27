import { createApp } from 'vue'
import CronStatusCell from '../components/CronStatusCell.vue'

document.querySelectorAll('[id^="cron-ops-"]').forEach(el => {
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
