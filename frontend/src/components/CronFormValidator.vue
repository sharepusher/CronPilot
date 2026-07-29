<template>
  <div class="cron-expr-preview-wrap">
    <div v-if="cronVisible && (humanized || error)" class="cron-expr-preview">
      <span v-if="error" class="cron-preview-error">
        <i class="fa fa-exclamation-triangle"></i> {{ error }}
      </span>
      <template v-else>
        <i class="fa fa-clock-o cron-preview-icon"></i>
        <span class="cron-preview-text">{{ humanized }}</span>
        <code class="cron-preview-expr">{{ exprDisplay }}</code>
      </template>
    </div>
    <div v-if="urlError" class="cron-field-inline-error">
      <i class="fa fa-exclamation-circle"></i> {{ urlError }}
    </div>
    <div v-if="jsonError" class="cron-field-inline-error">
      <i class="fa fa-exclamation-circle"></i> {{ jsonError }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

// ---------- helpers (port of cron_schedule_display.py) ----------

function isStar(v) {
  return !v || v === '*'
}

function everyN(v, unit) {
  var m = /^\*\/(\d+)$/.exec(v || '')
  if (!m) return null
  var n = parseInt(m[1], 10)
  if (n <= 0) return null
  return n === 1 ? ('每' + unit) : ('每 ' + n + ' ' + unit)
}

var WEEKDAY_MAP = {
  '0':'周日','7':'周日','1':'周一','2':'周二','3':'周三',
  '4':'周四','5':'周五','6':'周六',
  'sun':'周日','mon':'周一','tue':'周二','wed':'周三',
  'thu':'周四','fri':'周五','sat':'周六',
}

function weekdayLabel(v) {
  if (!v) return ''
  var parts = v.split(',').map(function(p){ return p.trim().toLowerCase() }).filter(Boolean)
  return parts.map(function(p){ return WEEKDAY_MAP[p] || p }).join('、')
}

function pad(v) {
  return (v && /^\d+$/.test(v)) ? v.padStart(2, '0') : (v || '00')
}

function humanizeCron(dow, day, hour, minute, second) {
  var hasDow = dow && !isStar(dow)
  var hasDay = day && !isStar(day)
  var hasHour = hour && !isStar(hour)
  var hasMin = minute && !isStar(minute)
  var hasSec = second && !isStar(second)

  // second-level: */n second, all others *
  if (hasSec) {
    var e = everyN(second, '秒')
    if (e && isStar(minute) && isStar(hour) && isStar(day) && isStar(dow)) return e
  }

  // minute-level: */n minute
  if (hasMin) {
    var em = everyN(minute, '分钟')
    if (em && isStar(hour) && isStar(day) && isStar(dow)) {
      if (second && second !== '*' && second !== '0') return em + '（第 ' + second + ' 秒）'
      return em
    }
    if (/^\d+$/.test(minute) && isStar(hour) && isStar(day) && isStar(dow)) {
      return '每小时第 ' + minute + ' 分钟'
    }
  }

  // hour-level: */n hour
  if (hasHour) {
    var eh = everyN(hour, '小时')
    if (eh && isStar(day) && isStar(dow)) {
      var m0 = (minute && !isStar(minute)) ? minute : '0'
      return eh + ' 的第 ' + m0 + ' 分'
    }
  }

  // weekly
  if (hasDow && isStar(day)) {
    var wd = weekdayLabel(dow)
    return '每' + wd + ' ' + pad(hour) + ':' + pad(minute)
  }

  // monthly
  if (hasDay && isStar(dow)) {
    return '每月 ' + day + ' 日 ' + pad(hour) + ':' + pad(minute)
  }

  // daily
  if (hasHour || hasMin) {
    if (isStar(day) && isStar(dow)) {
      return '每天 ' + pad(hour) + ':' + pad(minute)
    }
  }

  return null
}

function formatExpr(dow, day, hour, minute, second) {
  var d = dow || '*', dy = day || '*', h = hour || '*', m = minute || '*'
  var clock = h + ':' + m
  if (second && second !== '*') clock += ':' + second
  return d + ' ' + dy + ' ' + clock
}

// ---------- range validation ----------

function validatePart(v, label, min, max) {
  if (!v || v === '*') return null
  if (/^\*\/\d+$/.test(v)) {
    var n = parseInt(v.slice(2), 10)
    if (n < 1) return label + ' 步长不能为 0'
    return null
  }
  var parts = v.split(',')
  for (var i = 0; i < parts.length; i++) {
    var p = parts[i].trim()
    if (p === '*') continue
    var rng = p.split('-')
    if (rng.length === 2) {
      var a = parseInt(rng[0], 10), b = parseInt(rng[1], 10)
      if (isNaN(a) || isNaN(b) || a < min || b > max || a > b) return label + ' 范围无效：' + p
      continue
    }
    if (!/^\d+$/.test(p)) return label + ' 格式无效：' + p
    var num = parseInt(p, 10)
    if (num < min || num > max) return label + ' 超出范围 ' + min + '-' + max + '：' + p
  }
  return null
}

// ---------- URL validation ----------

function validateUrl(url) {
  if (!url) return null
  try { new URL(url) } catch (_) { return '触发 URL 格式无效（需以 http:// 或 https:// 开头）' }
  if (!/^https?:\/\//i.test(url)) return '触发 URL 须以 http:// 或 https:// 开头'
  return null
}

// ---------- JSON Body validation ----------

function validateJson(body, method) {
  if (method !== 'POST' || !body || !body.trim()) return null
  try { var parsed = JSON.parse(body); if (typeof parsed !== 'object' || Array.isArray(parsed)) return '请求 Body 须为 JSON 对象（{…}）' } catch (_) { return '请求 Body 不是合法 JSON' }
  return null
}

// ---------- component state ----------

const cronVisible = ref(false)
const dow = ref('')
const day = ref('')
const hour = ref('')
const minute = ref('')
const second = ref('')
const urlVal = ref('')
const methodVal = ref('GET')
const bodyVal = ref('')

const humanized = computed(function() {
  var h = humanizeCron(dow.value, day.value, hour.value, minute.value, second.value)
  return h || ''
})
const exprDisplay = computed(function() {
  return formatExpr(dow.value, day.value, hour.value, minute.value, second.value)
})
const error = computed(function() {
  return (
    validatePart(minute.value, '分', 0, 59) ||
    validatePart(hour.value, '小时', 0, 23) ||
    validatePart(day.value, '日', 1, 31) ||
    validatePart(second.value, '秒', 0, 59) ||
    null
  )
})
const urlError = computed(function() { return validateUrl(urlVal.value) })
const jsonError = computed(function() { return validateJson(bodyVal.value, methodVal.value) })

// ---------- DOM watcher ----------

function readFields() {
  cronVisible.value = (document.getElementById('cron_div') || {}).style.display !== 'none'
  dow.value = (document.querySelector('input[name=day_of_week]') || {}).value || ''
  day.value = (document.querySelector('input[name=day]') || {}).value || ''
  hour.value = (document.querySelector('input[name=hour]') || {}).value || ''
  minute.value = (document.querySelector('input[name=minute]') || {}).value || ''
  second.value = (document.querySelector('input[name=second]') || {}).value || ''
  urlVal.value = (document.querySelector('input[name=req_url]') || {}).value || ''
  methodVal.value = (document.querySelector('select[name=req_method]') || {}).value || 'GET'
  bodyVal.value = (document.querySelector('textarea[name=req_body]') || {}).value || ''
}

function onFormInput() { readFields() }

onMounted(function() {
  readFields()
  var form = document.querySelector('form.js-cron-form') || document.querySelector('form')
  if (form) form.addEventListener('input', onFormInput)
  // also listen to change for select elements
  if (form) form.addEventListener('change', onFormInput)
})

onUnmounted(function() {
  var form = document.querySelector('form.js-cron-form') || document.querySelector('form')
  if (form) { form.removeEventListener('input', onFormInput); form.removeEventListener('change', onFormInput) }
})
</script>

<style>
.cron-expr-preview-wrap {
  margin: 0 0 4px 0;
}
.cron-expr-preview {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 4px;
  padding: 4px 10px;
  font-size: 12px;
  color: #166534;
  margin-top: 4px;
}
.cron-preview-icon {
  color: #16a34a;
  flex-shrink: 0;
}
.cron-preview-text {
  font-weight: 600;
}
.cron-preview-expr {
  background: #dcfce7;
  color: #14532d;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 11px;
}
.cron-preview-error {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #b91c1c;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 4px;
  padding: 4px 10px;
  font-size: 12px;
  margin-top: 4px;
}
.cron-field-inline-error {
  color: #b91c1c;
  font-size: 12px;
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 5px;
}
</style>
