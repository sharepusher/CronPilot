import { createApp } from 'vue'
import CronFilterBar from '../components/CronFilterBar.vue'

document.querySelectorAll('#cron-filter-bar').forEach(function(el) {
  var d = el.dataset
  createApp(CronFilterBar, {
    listUrl: d.listUrl,
    addUrl: d.addUrl || '',
    canCreate: d.canCreate === 'true',
    currentKw: d.currentKw || '',
    currentStatus: d.currentStatus || '',
    currentHealth: d.currentHealth || '',
    currentScope: d.currentScope || 'all',
    currentGroup: d.currentGroup || '',
    scopeGroupsJson: d.scopeGroups || '[]',
    allTagsJson: d.allTags || '[]',
    currentTag: d.currentTag || '',
  }).mount(el)
})
