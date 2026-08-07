<template>
  <div class="well well-small cron-list-toolbar" style="padding:8px 10px;margin:0 0 10px;overflow:hidden">
    <div class="cron-toolbar-left">
      <span class="cron-filter-label">异常</span>
      <div class="btn-group cron-filter-group">
        <a class="btn btn-mini cron-chip-fail" :class="{ active: health === 'failing' }"
           href="javascript:;" @click="setHealth('failing')">连续失败</a>
        <a class="btn btn-mini cron-chip-warn" :class="{ active: health === 'today_fail' }"
           href="javascript:;" @click="setHealth('today_fail')">今日失败</a>
      </div>
      <span class="cron-filter-sep">|</span>
      <span class="cron-filter-label">状态</span>
      <div class="btn-group cron-filter-group">
        <a class="btn btn-mini cron-chip-run" :class="{ active: status === '1' }"
           href="javascript:;" @click="setStatus('1')">运行中</a>
        <a class="btn btn-mini cron-chip-pause" :class="{ active: status === '0' }"
           href="javascript:;" @click="setStatus('0')">已暂停</a>
        <a class="btn btn-mini cron-chip-all" :class="{ active: !health && !status }"
           href="javascript:;" @click="clearStatusAndHealth">全部</a>
      </div>
      <span class="cron-filter-sep">|</span>
      <span class="cron-toolbar-label">业务组</span>
      <select class="cron-toolbar-select" v-model="scopeVal" @change="doFetch">
        <option value="all">全部（可见）</option>
        <option value="global">全局共享</option>
        <option v-for="g in scopeGroups" :key="g.id" :value="'group:' + g.id">{{ g.name }}</option>
      </select>
      <span class="cron-filter-sep">|</span>
      <span class="cron-toolbar-label">标签</span>
      <select class="cron-toolbar-select" v-model="tagVal" @change="doFetch">
        <option value="">全部</option>
        <option v-for="t in allTags" :key="t" :value="t">{{ t }}</option>
      </select>
    </div>
    <div class="cron-toolbar-search">
      <span class="cron-search-label">任务名</span>
      <input type="text" v-model="kw" @input="onKwInput" placeholder="模糊匹配">
      <button type="button" class="btn btn-primary" @click="doFetch">搜索</button>
      <a href="javascript:;" class="btn" @click="doReset">重置</a>
    </div>
    <div class="cron-toolbar-right">
      <a v-if="canCreate" :href="addUrl" class="btn btn-primary btn-mini cron-add-btn">+ 新建任务</a>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  listUrl: { type: String, required: true },
  addUrl: { type: String, default: '' },
  canCreate: { type: Boolean, default: false },
  currentKw: { type: String, default: '' },
  currentStatus: { type: String, default: '' },
  currentHealth: { type: String, default: '' },
  currentScope: { type: String, default: 'all' },
  currentGroup: { type: String, default: '' },
  scopeGroupsJson: { type: String, default: '[]' },
  allTagsJson: { type: String, default: '[]' },
  currentTag: { type: String, default: '' },
})

const kw = ref(props.currentKw)
const status = ref(props.currentStatus)
const health = ref(props.currentHealth)

const scopeGroups = ref([])
try { scopeGroups.value = JSON.parse(props.scopeGroupsJson) } catch (_) {}

const allTags = ref([])
try { allTags.value = JSON.parse(props.allTagsJson) } catch (_) {}
const tagVal = ref(props.currentTag || '')

// 'all' | 'global' | 'group:N'
const scopeVal = ref(
  props.currentScope === 'group' && props.currentGroup
    ? 'group:' + props.currentGroup
    : (props.currentScope || 'all')
)

let debounceTimer = null

function buildParams(includePartial) {
  const p = new URLSearchParams()
  if (kw.value) p.set('task_name', kw.value)
  if (status.value) p.set('status', status.value)
  if (health.value) p.set('health', health.value)
  if (scopeVal.value === 'global') {
    p.set('scope_view', 'global')
  } else if (scopeVal.value.startsWith('group:')) {
    p.set('scope_view', 'group')
    p.set('group_id', scopeVal.value.slice(6))
  } else {
    p.set('scope_view', 'all')
  }
  if (tagVal.value) p.set('tag', tagVal.value)
  if (includePartial) p.set('partial', '1')
  return p
}

function doFetch() {
  const tbody = document.getElementById('cron-tbody')
  const pagination = document.getElementById('cron-pagination')

  fetch(props.listUrl + '?' + buildParams(true).toString())
    .then(function(r) { return r.json() })
    .then(function(data) {
      if (tbody) tbody.innerHTML = data.rows || ''
      if (pagination) pagination.innerHTML = data.pagination || ''
      // re-mount CronStatusCell on newly inserted elements
      if (window.CronStatusCell) window.CronStatusCell.mountAll()
      // update browser URL without partial=1
      history.replaceState(null, '', props.listUrl + '?' + buildParams(false).toString())
    })
    .catch(function() {})
}

function setHealth(val) {
  health.value = val
  status.value = ''
  doFetch()
}

function setStatus(val) {
  status.value = val
  health.value = ''
  doFetch()
}

function clearStatusAndHealth() {
  health.value = ''
  status.value = ''
  doFetch()
}

function doReset() {
  kw.value = ''
  status.value = ''
  health.value = ''
  scopeVal.value = 'all'
  tagVal.value = ''
  doFetch()
}

function onKwInput() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(doFetch, 150)
}
</script>
