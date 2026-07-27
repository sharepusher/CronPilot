<template>
  <a class="btn btn-mini btn-info" href="javascript:;" @click="onLogClick">运行记录</a>
  <button v-if="localStatus === 1 && canWrite && hasUrl"
          class="btn btn-mini btn-success"
          :disabled="busy"
          @click="onRunNow">
    {{ busy && busyAction === 'run' ? '执行中…' : '立即执行' }}
  </button>
  <div :class="['btn-group', { open: menuOpen }]" @click.stop>
    <button class="btn btn-mini btn-default dropdown-toggle"
            @click="menuOpen = !menuOpen">
      更多 <span class="caret"></span>
    </button>
    <ul class="dropdown-menu pull-right">
      <template v-if="localStatus !== -1">
        <template v-if="canWrite">
          <li v-if="localStatus === 0">
            <a href="javascript:;" @click="onToggle"><i class="fa fa-play"></i> 启动</a>
          </li>
          <li v-if="localStatus === 1">
            <a href="javascript:;" @click="onToggle"><i class="fa fa-pause"></i> 暂停</a>
          </li>
          <li><a :href="editUrl"><i class="fa fa-pencil"></i> 编辑</a></li>
        </template>
        <li class="divider"></li>
        <li v-if="canRetire">
          <a class="cron-menu-danger" :href="retireUrl"><i class="fa fa-ban"></i> 下线</a>
        </li>
        <li v-else>
          <a href="javascript:;" @click="onRetireDenied"><i class="fa fa-ban"></i> 下线</a>
        </li>
      </template>
      <li v-if="localStatus === -1" class="disabled">
        <a href="javascript:;">已下线</a>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  cronId: { type: Number, required: true },
  status: { type: Number, required: true },
  canWrite: { type: Boolean, default: false },
  canRetire: { type: Boolean, default: false },
  hasUrl: { type: Boolean, default: false },
  updateUrl: { type: String, default: '' },
  runUrl: { type: String, default: '' },
  logUrl: { type: String, required: true },
  editUrl: { type: String, default: '' },
  retireUrl: { type: String, default: '' },
})

const localStatus = ref(props.status)
const menuOpen = ref(false)
const busy = ref(false)
const busyAction = ref('')

function updateSiblingBadge(newStatus) {
  const badge = document.getElementById('status-badge-' + props.cronId)
  if (!badge) return
  if (newStatus === 1) {
    badge.className = 'label label-info'
    badge.textContent = '运行中'
  } else if (newStatus === 0) {
    badge.className = 'label label-pause'
    badge.textContent = '已暂停'
  }
}

function getCsrfToken() {
  return document.querySelector('meta[name=csrf-token]')?.content ?? ''
}

function csrfPost(url) {
  return fetch(url, {
    method: 'POST',
    headers: { 'X-CSRFToken': getCsrfToken() }
  }).then(r => r.json())
}

function artConfirm(msg, onOk) {
  if (window.Wind) {
    Wind.use('artDialog', function() {
      art.dialog({
        title: false,
        icon: 'question',
        content: msg,
        ok: function() { onOk(); return true },
        cancel: true
      })
    })
  } else if (confirm(msg)) {
    onOk()
  }
}

function artAlert(msg, icon) {
  if (window.Wind) {
    Wind.use('artDialog', function() {
      art.dialog({ title: false, icon: icon || 'succeed', content: msg, ok: true })
    })
  } else {
    alert(msg)
  }
}

function closeMenu() {
  menuOpen.value = false
}

function onLogClick() {
  closeMenu()
  if (window.open_iframe_dialog) {
    open_iframe_dialog(props.logUrl, '运行记录查看')
  } else {
    window.location.href = props.logUrl
  }
}

function onRunNow() {
  closeMenu()
  artConfirm('确定立即执行该任务？执行过程可能等待至多 2 分钟。', async () => {
    busy.value = true
    busyAction.value = 'run'
    try {
      // props.runUrl 已由 Jinja url_for 生成并含 ?id=N，直接使用，不得再追加 ?id=
      const data = await csrfPost(props.runUrl)
      if (data.errcode === 0) {
        if (data.url && window.open_iframe_dialog) {
          open_iframe_dialog(data.url, '立即执行记录')
        } else if (data.url) {
          artAlert((data.errmsg || '执行完成') + ' <a href="' + data.url + '" target="_blank">查看记录</a>', 'succeed')
        } else {
          artAlert(data.errmsg || '执行完成', 'succeed')
        }
      } else {
        artAlert(data.errmsg || '执行失败', 'error')
      }
    } catch {
      artAlert('请求失败，请重试', 'error')
    } finally {
      busy.value = false
      busyAction.value = ''
    }
  })
}

function onToggle() {
  closeMenu()
  const msg = localStatus.value === 0 ? '确定启动该任务？' : '确定暂停该任务？'
  artConfirm(msg, async () => {
    busy.value = true
    busyAction.value = 'toggle'
    try {
      // props.updateUrl 已由 Jinja url_for 生成并含 ?id=N，直接使用，不得再追加 ?id=
      const data = await csrfPost(props.updateUrl)
      if (data.errcode === 0) {
        localStatus.value = localStatus.value === 0 ? 1 : 0
        updateSiblingBadge(localStatus.value)
      } else {
        artAlert(data.errmsg || '操作失败', 'error')
      }
    } catch {
      artAlert('请求失败，请重试', 'error')
    } finally {
      busy.value = false
      busyAction.value = ''
    }
  })
}

function onRetireDenied() {
  closeMenu()
  artAlert('权限不足：当前账号不可下线任务', 'warning')
}

onMounted(() => {
  document.addEventListener('click', closeMenu)
})

onUnmounted(() => {
  document.removeEventListener('click', closeMenu)
})
</script>
