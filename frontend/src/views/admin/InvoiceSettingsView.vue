<script setup lang="ts">
import { ref, onMounted } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'

const toast   = useToastStore()
const loading = ref(false)
const saving  = ref(false)
const showModal = ref(false)

interface StoreStatus {
  store_id:       string
  store_name:     string
  store_code:     string
  configured:     boolean
  enabled:        boolean
  platform:       string
  terminal_count: number
}

interface Terminal {
  id:           string
  name:         string
  device_model: string
  ecpay_override: {
    merchant_id: string
    hash_key:    string
    hash_iv:     string
  } | null
}

const DEVICE_MODELS = [
  'EPSON TM-T88VI', 'EPSON TM-T88V', 'EPSON TM-T70II',
  'Star TSP143III', 'Star TSP654II',
  'Citizen CT-S310II', 'Custom KPM180H', 'Sewoo LK-TL212',
  '其他',
]

const storeList = ref<StoreStatus[]>([])

const defaultForm = () => ({
  enabled:     false,
  platform:    'ecpay',
  merchant_id: '',
  hash_key:    '',
  hash_iv:     '',
  seller_id:   '',
  test_mode:   true,
  tax_rate:    5,
  auto_issue:  false,
})

const editingStoreId   = ref('')
const editingStoreName = ref('')
const form = ref(defaultForm())

// ── Terminal state ────────────────────────────────────────────
const terminals         = ref<Terminal[]>([])
const terminalLoading   = ref(false)
const terminalSaving    = ref(false)
const showTerminalForm  = ref(false)
const editingTerminalId = ref('')

const defaultTerminalForm = () => ({
  name:         '',
  device_model: '',
  use_override: false,
  merchant_id:  '',
  hash_key:     '',
  hash_iv:      '',
})
const terminalForm = ref(defaultTerminalForm())

async function load() {
  loading.value = true
  try {
    const r = await http.get('/invoice/store/')
    storeList.value = r.data.data || []
  } catch {
    toast.show('載入失敗', 'danger')
  } finally {
    loading.value = false
  }
}

async function openModal(store: StoreStatus) {
  editingStoreId.value   = store.store_id
  editingStoreName.value = store.store_name
  form.value = defaultForm()
  showTerminalForm.value = false
  showModal.value = true
  try {
    const [settingsRes, terminalRes] = await Promise.all([
      http.get(`/invoice/store/${store.store_id}/settings`),
      http.get(`/invoice/store/${store.store_id}/terminals/`),
    ])
    Object.assign(form.value, settingsRes.data.data || {})
    terminals.value = terminalRes.data.data || []
  } catch {
    toast.show('載入設定失敗', 'danger')
  }
}

async function save() {
  saving.value = true
  try {
    await http.put(`/invoice/store/${editingStoreId.value}/settings`, form.value)
    toast.show('設定已儲存', 'success')
    showModal.value = false
    await load()
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '儲存失敗', 'danger')
  } finally {
    saving.value = false
  }
}

// ── Terminal CRUD ─────────────────────────────────────────────
async function loadTerminals() {
  terminalLoading.value = true
  try {
    const r = await http.get(`/invoice/store/${editingStoreId.value}/terminals/`)
    terminals.value = r.data.data || []
  } catch {
    toast.show('機台載入失敗', 'danger')
  } finally {
    terminalLoading.value = false
  }
}

function openTerminalForm(t?: Terminal) {
  if (t) {
    editingTerminalId.value = t.id
    terminalForm.value = {
      name:         t.name,
      device_model: t.device_model,
      use_override: !!t.ecpay_override,
      merchant_id:  t.ecpay_override?.merchant_id || '',
      hash_key:     t.ecpay_override?.hash_key    || '',
      hash_iv:      t.ecpay_override?.hash_iv     || '',
    }
  } else {
    editingTerminalId.value = ''
    terminalForm.value = defaultTerminalForm()
  }
  showTerminalForm.value = true
}

function cancelTerminalForm() {
  showTerminalForm.value  = false
  editingTerminalId.value = ''
}

async function saveTerminal() {
  const f = terminalForm.value
  if (!f.name.trim()) { toast.show('請輸入機台名稱', 'danger'); return }
  terminalSaving.value = true
  try {
    const body: Record<string, unknown> = {
      name:         f.name.trim(),
      device_model: f.device_model,
      ecpay_override: f.use_override
        ? { merchant_id: f.merchant_id, hash_key: f.hash_key, hash_iv: f.hash_iv }
        : null,
    }
    if (editingTerminalId.value) {
      await http.put(`/invoice/store/${editingStoreId.value}/terminals/${editingTerminalId.value}`, body)
      toast.show('機台已更新')
    } else {
      await http.post(`/invoice/store/${editingStoreId.value}/terminals/`, body)
      toast.show('機台已新增')
    }
    showTerminalForm.value = false
    await loadTerminals()
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '儲存失敗', 'danger')
  } finally {
    terminalSaving.value = false
  }
}

async function deleteTerminal(tid: string, name: string) {
  if (!confirm(`確定刪除機台「${name}」？`)) return
  try {
    await http.delete(`/invoice/store/${editingStoreId.value}/terminals/${tid}`)
    toast.show('已刪除')
    await loadTerminals()
  } catch (e: any) {
    toast.show(e?.response?.data?.message ?? '刪除失敗', 'danger')
  }
}

onMounted(load)
</script>

<template>
  <div class="table-card">
    <div class="table-header">
      <h6><i class="bi bi-receipt-cutoff me-1"></i>電子發票設定</h6>
    </div>

    <div v-if="loading" class="text-center py-4">
      <div class="spinner-border spinner-border-sm text-primary"></div>
    </div>

    <div v-else class="table-responsive">
      <table class="table mb-0">
        <thead>
          <tr>
            <th>店家</th>
            <th>代碼</th>
            <th>發票平台</th>
            <th>機台數</th>
            <th>狀態</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!storeList.length">
            <td colspan="6" class="text-center text-muted py-3">尚無店家資料</td>
          </tr>
          <tr v-for="s in storeList" :key="s.store_id">
            <td class="fw-semibold">{{ s.store_name }}</td>
            <td><code>{{ s.store_code || '—' }}</code></td>
            <td class="text-muted small">{{ s.configured ? s.platform.toUpperCase() : '—' }}</td>
            <td class="text-center">
              <span class="badge bg-secondary">{{ s.terminal_count }}</span>
            </td>
            <td>
              <span v-if="!s.configured" class="badge bg-secondary">未設定</span>
              <span v-else-if="s.enabled"  class="badge bg-success">啟用</span>
              <span v-else class="badge bg-warning text-dark">停用</span>
            </td>
            <td>
              <button class="btn btn-sm btn-outline-primary" @click="openModal(s)">
                <i class="bi bi-gear me-1"></i>設定
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- Settings Modal -->
  <Teleport to="body">
    <div v-if="showModal" class="modal d-block" style="background:rgba(0,0,0,.5);z-index:1055"
         @click.self="showModal = false">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              <i class="bi bi-receipt-cutoff me-1"></i>電子發票設定 ─ {{ editingStoreName }}
            </h5>
            <button class="btn-close" @click="showModal = false"></button>
          </div>
          <div class="modal-body">

            <!-- ── 共用憑證設定 ──────────────────────────────── -->
            <div class="d-flex align-items-center justify-content-between mb-3 p-3 bg-light rounded">
              <div>
                <div class="fw-semibold">啟用電子發票</div>
                <small class="text-muted">關閉時不顯示發票相關選項</small>
              </div>
              <div class="form-check form-switch m-0">
                <input v-model="form.enabled" class="form-check-input" type="checkbox"
                       style="width:2.5em;height:1.3em;cursor:pointer" />
              </div>
            </div>

            <div class="mb-3">
              <label class="form-label fw-semibold">發票平台</label>
              <select v-model="form.platform" class="form-select" style="max-width:200px">
                <option value="ecpay">綠界科技 (ECPay)</option>
              </select>
            </div>

            <div class="mb-3">
              <label class="form-label fw-semibold">
                特店編號 MerchantID <span class="text-danger">*</span>
              </label>
              <input v-model="form.merchant_id" type="text" class="form-control"
                     placeholder="例：3002599" style="max-width:260px" />
              <div class="form-text">各機台未設定獨立憑證時，預設使用此組</div>
            </div>

            <div class="row g-3 mb-3">
              <div class="col-sm-6">
                <label class="form-label fw-semibold">HashKey <span class="text-danger">*</span></label>
                <input v-model="form.hash_key" type="password" class="form-control"
                       placeholder="已設定則顯示 ******" autocomplete="new-password" />
              </div>
              <div class="col-sm-6">
                <label class="form-label fw-semibold">HashIV <span class="text-danger">*</span></label>
                <input v-model="form.hash_iv" type="password" class="form-control"
                       placeholder="已設定則顯示 ******" autocomplete="new-password" />
              </div>
            </div>

            <div class="mb-3">
              <label class="form-label fw-semibold">賣方統一編號</label>
              <input v-model="form.seller_id" type="text" class="form-control"
                     placeholder="8 位數字" maxlength="8" style="max-width:180px" />
              <div class="form-text">開立 B2B 三聯式發票時使用</div>
            </div>

            <hr />

            <div class="row g-3 mb-3">
              <div class="col-auto d-flex align-items-center gap-3">
                <div class="form-check form-switch m-0">
                  <input v-model="form.test_mode" class="form-check-input" type="checkbox"
                         id="testMode" style="width:2.2em;height:1.2em;cursor:pointer" />
                  <label class="form-check-label fw-semibold" for="testMode">測試模式</label>
                </div>
                <small class="text-warning">
                  <i class="bi bi-exclamation-triangle me-1"></i>Stage 環境，不開立真實發票
                </small>
              </div>
              <div class="col-auto d-flex align-items-center gap-3">
                <div class="form-check form-switch m-0">
                  <input v-model="form.auto_issue" class="form-check-input" type="checkbox"
                         id="autoIssue" style="width:2.2em;height:1.2em;cursor:pointer" />
                  <label class="form-check-label fw-semibold" for="autoIssue">POS 結帳後自動開立</label>
                </div>
              </div>
            </div>

            <div class="d-flex align-items-center gap-2 mb-4">
              <label class="form-label fw-semibold mb-0">稅率（%）</label>
              <input v-model.number="form.tax_rate" type="number" min="0" max="100"
                     class="form-control" style="width:90px" />
              <small class="text-muted">目前台灣標準稅率 5%</small>
            </div>

            <!-- ── 機台管理 ──────────────────────────────────── -->
            <hr />
            <div class="d-flex justify-content-between align-items-center mb-3">
              <div class="fw-semibold"><i class="bi bi-printer me-1"></i>發票機台</div>
              <button class="btn btn-sm btn-outline-primary" @click="openTerminalForm()">
                <i class="bi bi-plus-lg me-1"></i>新增機台
              </button>
            </div>

            <!-- Terminal list -->
            <div v-if="terminalLoading" class="text-center py-2">
              <div class="spinner-border spinner-border-sm text-secondary"></div>
            </div>
            <div v-else-if="!terminals.length && !showTerminalForm"
                 class="text-muted small text-center py-3 border rounded bg-light mb-3">
              尚未新增機台。各機台可設定獨立 ECPay 憑證，或共用店家憑證。
            </div>
            <div v-else-if="terminals.length" class="list-group mb-3">
              <div v-for="t in terminals" :key="t.id"
                   class="list-group-item d-flex align-items-center gap-2 py-2">
                <code class="badge bg-secondary" style="font-size:.75rem">{{ t.id }}</code>
                <span class="flex-grow-1 fw-semibold small">{{ t.name }}</span>
                <span v-if="t.device_model"
                      class="badge bg-light text-dark border small">
                  <i class="bi bi-printer me-1"></i>{{ t.device_model }}
                </span>
                <span v-if="t.ecpay_override" class="badge bg-info text-dark small">獨立憑證</span>
                <span v-else class="badge bg-secondary small">共用憑證</span>
                <button class="btn btn-sm btn-outline-secondary btn-icon"
                        @click="openTerminalForm(t)">
                  <i class="bi bi-pencil"></i>
                </button>
                <button class="btn btn-sm btn-outline-danger btn-icon"
                        @click="deleteTerminal(t.id, t.name)">
                  <i class="bi bi-trash"></i>
                </button>
              </div>
            </div>

            <!-- Terminal add/edit form -->
            <div v-if="showTerminalForm"
                 class="border rounded p-3 mb-3" style="background:#f8f9fa">
              <div class="fw-semibold mb-3 small text-uppercase text-muted" style="letter-spacing:.05em">
                {{ editingTerminalId ? '編輯機台' : '新增機台' }}
              </div>
              <div class="row g-3 mb-3">
                <div class="col-sm-6">
                  <label class="form-label small fw-semibold">機台名稱 <span class="text-danger">*</span></label>
                  <input v-model="terminalForm.name" type="text" class="form-control form-control-sm"
                         placeholder="例：1號收銀台" />
                </div>
                <div class="col-sm-6">
                  <label class="form-label small fw-semibold">機型</label>
                  <select v-model="terminalForm.device_model" class="form-select form-select-sm">
                    <option value="">— 不指定 —</option>
                    <option v-for="m in DEVICE_MODELS" :key="m" :value="m">{{ m }}</option>
                  </select>
                </div>
              </div>

              <!-- Override toggle -->
              <div class="form-check form-switch mb-2">
                <input v-model="terminalForm.use_override" class="form-check-input" type="checkbox"
                       id="overrideToggle" style="width:2em;height:1.1em;cursor:pointer" />
                <label class="form-check-label small" for="overrideToggle">
                  使用獨立 ECPay 憑證（不繼承店家設定）
                </label>
              </div>
              <div v-if="terminalForm.use_override" class="mt-2 ps-3 border-start border-info">
                <div class="row g-2">
                  <div class="col-12">
                    <label class="form-label small">MerchantID</label>
                    <input v-model="terminalForm.merchant_id" type="text"
                           class="form-control form-control-sm" placeholder="特店編號" />
                  </div>
                  <div class="col-sm-6">
                    <label class="form-label small">HashKey</label>
                    <input v-model="terminalForm.hash_key" type="password"
                           class="form-control form-control-sm" placeholder="******"
                           autocomplete="new-password" />
                  </div>
                  <div class="col-sm-6">
                    <label class="form-label small">HashIV</label>
                    <input v-model="terminalForm.hash_iv" type="password"
                           class="form-control form-control-sm" placeholder="******"
                           autocomplete="new-password" />
                  </div>
                </div>
              </div>
              <div class="d-flex gap-2 mt-3">
                <button class="btn btn-primary btn-sm" :disabled="terminalSaving" @click="saveTerminal">
                  <span v-if="terminalSaving" class="spinner-border spinner-border-sm me-1"></span>
                  <i v-else class="bi bi-floppy me-1"></i>儲存機台
                </button>
                <button class="btn btn-secondary btn-sm" @click="cancelTerminalForm">取消</button>
              </div>
            </div>

          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showModal = false">取消</button>
            <button class="btn btn-primary" :disabled="saving" @click="save">
              <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
              <i v-else class="bi bi-floppy me-1"></i>儲存設定
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
