<script setup lang="ts">
/**
 * 相機掃條碼（全螢幕覆蓋層）
 *
 * - 優先使用瀏覽器原生 BarcodeDetector（Android Chrome / Edge），零額外下載
 * - 不支援時（iOS Safari、Firefox）才動態載入 @zxing/browser，不影響其他頁面的打包大小
 * - 連續掃描：掃到後 emit('detected')，同一條碼 1.5 秒內不重複觸發，可一次掃多件
 * - 相機需要安全連線（HTTPS 或 localhost），否則瀏覽器不會提供相機
 */
import { ref, watch, onBeforeUnmount, nextTick } from 'vue'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{
  (e: 'detected', code: string): void
  (e: 'close'): void
}>()

const videoEl  = ref<HTMLVideoElement | null>(null)
const status   = ref<'starting' | 'scanning' | 'error'>('starting')
const errorMsg = ref('')
const lastCode = ref('')
const engine   = ref<'native' | 'zxing' | ''>('')

let stream: MediaStream | null = null
let rafTimer: number | null = null
let zxingControls: { stop: () => void } | null = null
let lastAt = 0

const NATIVE_FORMATS = ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128', 'code_39', 'itf', 'qr_code']

function onCode(raw: string) {
  const code = (raw || '').trim()
  if (!code) return
  const now = Date.now()
  if (code === lastCode.value && now - lastAt < 1500) return   // 同條碼去抖動
  lastCode.value = code
  lastAt = now
  try { navigator.vibrate?.(60) } catch { /* 部分瀏覽器不支援 */ }
  emit('detected', code)
}

function explain(err: unknown): string {
  const name = (err as { name?: string })?.name || ''
  if (!window.isSecureContext) return '相機需要 HTTPS 連線才能使用，請改用 https:// 網址開啟'
  if (name === 'NotAllowedError') return '相機權限被拒絕，請到瀏覽器設定允許此網站使用相機'
  if (name === 'NotFoundError' || name === 'OverconstrainedError') return '找不到可用的相機'
  if (name === 'NotReadableError') return '相機正被其他程式使用中'
  return '無法啟動相機：' + ((err as Error)?.message || name || '未知錯誤')
}

async function startNative(): Promise<boolean> {
  const BD = (window as any).BarcodeDetector
  if (!BD) return false
  let formats: string[] = NATIVE_FORMATS
  try {
    const supported: string[] = await BD.getSupportedFormats()
    formats = NATIVE_FORMATS.filter(f => supported.includes(f))
    if (!formats.length) return false
  } catch { return false }

  const detector = new BD({ formats })
  stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: { ideal: 'environment' } }, audio: false,
  })
  const video = videoEl.value!
  video.srcObject = stream
  await video.play()
  engine.value = 'native'
  status.value = 'scanning'

  const tick = async () => {
    if (!stream) return
    try {
      if (video.readyState >= 2) {
        const codes = await detector.detect(video)
        if (codes.length) onCode(codes[0].rawValue)
      }
    } catch { /* 單幀失敗忽略 */ }
    rafTimer = window.setTimeout(tick, 150)
  }
  tick()
  return true
}

async function startZxing() {
  const { BrowserMultiFormatReader } = await import('@zxing/browser')
  const reader = new BrowserMultiFormatReader()
  engine.value = 'zxing'
  zxingControls = await reader.decodeFromConstraints(
    { video: { facingMode: { ideal: 'environment' } }, audio: false },
    videoEl.value!,
    (result) => { if (result) onCode(result.getText()) },
  )
  status.value = 'scanning'
}

async function start() {
  status.value = 'starting'
  errorMsg.value = ''
  lastCode.value = ''
  await nextTick()
  if (!navigator.mediaDevices?.getUserMedia) {
    status.value = 'error'
    errorMsg.value = explain(new Error('此瀏覽器不支援相機'))
    return
  }
  try {
    if (!(await startNative())) await startZxing()
  } catch (e) {
    stop()
    status.value = 'error'
    errorMsg.value = explain(e)
  }
}

function stop() {
  if (rafTimer !== null) { clearTimeout(rafTimer); rafTimer = null }
  if (zxingControls) { try { zxingControls.stop() } catch { /* ignore */ } zxingControls = null }
  if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null }
  if (videoEl.value) videoEl.value.srcObject = null
}

function close() {
  stop()
  emit('close')
}

watch(() => props.open, (v) => { v ? start() : stop() })
onBeforeUnmount(stop)
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="scanner-overlay">
      <video ref="videoEl" class="scanner-video" playsinline muted autoplay></video>

      <div class="scanner-frame" v-if="status === 'scanning'"></div>

      <div class="scanner-top">
        <span class="fw-semibold">
          <i class="bi bi-upc-scan me-1"></i>掃描條碼
        </span>
        <button class="btn btn-light btn-close-scan" @click="close" aria-label="關閉掃描">
          <i class="bi bi-x-lg"></i>
        </button>
      </div>

      <div class="scanner-bottom">
        <div v-if="status === 'starting'">
          <span class="spinner-border spinner-border-sm me-2"></span>啟動相機中…
        </div>
        <div v-else-if="status === 'error'" class="text-warning">
          <i class="bi bi-exclamation-triangle me-1"></i>{{ errorMsg }}
        </div>
        <div v-else>
          將條碼對準框內，可連續掃描多件
          <div v-if="lastCode" class="mt-1 small opacity-75">上一筆：{{ lastCode }}</div>
        </div>
        <button class="btn btn-light btn-lg w-100 mt-3" @click="close">完成</button>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.scanner-overlay {
  position: fixed; inset: 0; z-index: 9500;
  background: #000; color: #fff;
  display: flex; flex-direction: column;
}
.scanner-video {
  position: absolute; inset: 0;
  width: 100%; height: 100%; object-fit: cover;
}
.scanner-frame {
  position: absolute; left: 10%; right: 10%; top: 32%; height: 22%;
  border: 3px solid rgba(255, 255, 255, .9);
  border-radius: 12px;
  box-shadow: 0 0 0 100vmax rgba(0, 0, 0, .45);
  pointer-events: none;
}
.scanner-top, .scanner-bottom {
  position: relative; z-index: 1;
  padding: 14px 16px;
}
.scanner-top {
  display: flex; align-items: center; justify-content: space-between;
  padding-top: calc(14px + env(safe-area-inset-top));
  background: linear-gradient(rgba(0,0,0,.6), transparent);
}
.scanner-bottom {
  margin-top: auto; text-align: center;
  padding-bottom: calc(18px + env(safe-area-inset-bottom));
  background: linear-gradient(transparent, rgba(0,0,0,.75));
}
.btn-close-scan { width: 44px; height: 44px; border-radius: 50%; padding: 0; }
</style>
