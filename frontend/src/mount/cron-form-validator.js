import { createApp } from 'vue'
import CronFormValidator from '../components/CronFormValidator.vue'

document.querySelectorAll('#cron-form-validator').forEach(function(el) {
  createApp(CronFormValidator).mount(el)
})
