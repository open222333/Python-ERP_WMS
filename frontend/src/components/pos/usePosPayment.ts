// [REFACTOR] 自 PosView.vue 拆出（付款方式 / 現金 Numpad / 電子發票 / LINE Pay / 結帳邏輯）
import { ref, computed, watch, nextTick } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import http from '@/api'
import type { CartRow, SelectionItem } from './types'

export interface PosPaymentProps {
  show:              boolean
  cart:              CartRow[]
  cartTotal:         { subtotal: number; total: number; count: number }
  discount:          number
  selectedWarehouse: string
  payMethods:        any[]
  invoiceEnabled:    boolean
  invAutoIssue:      boolean
  rowPrice:          (row: CartRow) => number
}

export type PosPaymentEmit = (event: 'update:show' | 'success', ...args: any[]) => void

export function usePosPayment(props: PosPaymentProps, emit: PosPaymentEmit) {
  const auth  = useAuthStore()
  const toast = useToastStore()

  // ── State ─────────────────────────────────────────
  const selectedPayMethod = ref('cash')
  const cashReceived      = ref(0)
  const changeAmt         = ref(0)
  const payRemark         = ref('')
  const checkoutLoading   = ref(false)

  // ── Computed ──────────────────────────────────────
  const enabledPayMethods = computed(() => props.payMethods.filter((m: any) => m.enabled !== false))
  const currentPayHasCash = computed(() => {
    const m = props.payMethods.find((m: any) => m.id === selectedPayMethod.value)
    return m?.has_cash ?? false
  })

  // 原 boot() 內邏輯：付款方式載入後預設選第一個
  watch(() => props.payMethods, (list) => {
    selectedPayMethod.value = list[0]?.id ?? 'cash'
  })

  // Numpad state
  const numpadStr  = ref('0')
  const denomMode  = ref<'+'|'-'>('+')

  function numpadPress(digit: string) {
    if (numpadStr.value === '0') {
      numpadStr.value = digit === '00' ? '0' : digit
    } else {
      numpadStr.value += digit
      if (numpadStr.value.length > 8) numpadStr.value = numpadStr.value.slice(0, 8)
    }
    cashReceived.value = parseInt(numpadStr.value) || 0
    calcChange()
  }

  function numpadBack() {
    numpadStr.value = numpadStr.value.slice(0, -1) || '0'
    cashReceived.value = parseInt(numpadStr.value) || 0
    calcChange()
  }

  function numpadClear() {
    numpadStr.value = '0'
    cashReceived.value = 0
    calcChange()
  }

  function addDenom(d: number) {
    cashReceived.value = denomMode.value === '+'
      ? cashReceived.value + d
      : Math.max(0, cashReceived.value - d)
    numpadStr.value = String(cashReceived.value)
    calcChange()
  }

  function fillExact() {
    cashReceived.value = props.cartTotal.total
    numpadStr.value    = String(cashReceived.value)
    calcChange()
  }

  // 電子發票
  const invMode        = ref<'none'|'scan'|'tax'|'love'>('none')
  const invScanRaw     = ref('')    // 掃描框原始輸入
  const invNum         = ref('')    // 確認後的載具號碼
  const invCarrierType = ref('')    // 顯示用名稱：手機條碼 / 自然人憑證
  const invEcpayType   = ref('')    // ECPay 型別：'1' | '2'
  const invBuyerId     = ref('')    // 統一編號
  const invLoveCode    = ref('')    // 愛心碼
  const invScanRef     = ref<HTMLInputElement>()

  function setInvMode(mode: 'none'|'scan'|'tax'|'love') {
    invMode.value = mode
    invScanRaw.value = ''; invNum.value = ''; invCarrierType.value = ''; invEcpayType.value = ''
    invBuyerId.value = ''; invLoveCode.value = ''
    if (mode === 'scan') nextTick(() => invScanRef.value?.focus())
  }

  function detectCarrier(val: string): { ecpayType: string; label: string } | null {
    const v = val.trim()
    if (/^\/[0-9A-Z+\-.]{7}$/i.test(v)) return { ecpayType: '1', label: '手機條碼' }
    if (/^[0-9A-Za-z]{16}$/.test(v))    return { ecpayType: '2', label: '自然人憑證' }
    return null
  }

  function onInvInput() {
    const det = detectCarrier(invScanRaw.value)
    if (det) {
      invEcpayType.value   = det.ecpayType
      invCarrierType.value = det.label
      invNum.value         = invScanRaw.value.trim()
    } else {
      invEcpayType.value = ''; invCarrierType.value = ''; invNum.value = ''
    }
  }

  function onInvScan() {
    const det = detectCarrier(invScanRaw.value)
    if (!det) {
      toast.show('無法識別條碼，手機條碼 /XXXXXXX（8碼）或自然人憑證（16碼）', 'warning')
      return
    }
    invEcpayType.value   = det.ecpayType
    invCarrierType.value = det.label
    invNum.value         = invScanRaw.value.trim()
  }

  function clearInvScan() {
    invScanRaw.value = ''; invNum.value = ''; invCarrierType.value = ''; invEcpayType.value = ''
    nextTick(() => invScanRef.value?.focus())
  }

  // LINE Pay
  const linePayKey     = ref('')
  const linePayScanRef = ref<HTMLInputElement>()
  const LINE_PAY_IDS   = ['linepay', 'zpay']
  const isLinePayMode  = computed(() => LINE_PAY_IDS.includes(selectedPayMethod.value))

  watch(selectedPayMethod, (val) => {
    if (LINE_PAY_IDS.includes(val)) nextTick(() => linePayScanRef.value?.focus())
    else linePayKey.value = ''
  })

  watch(() => props.show, (val) => {
    if (val) {
      numpadStr.value    = '0'
      cashReceived.value = 0
      denomMode.value    = '+'
      changeAmt.value    = 0
    }
  })

  // ── Methods ───────────────────────────────────────
  function calcChange() {
    changeAmt.value = cashReceived.value - props.cartTotal.total
  }

  function selectPayMethod(id: string) {
    selectedPayMethod.value = id
    calcChange()
  }

  async function confirmCheckout() {
    if (!props.selectedWarehouse) return toast.show('請先選擇倉庫', 'danger')
    if (!selectedPayMethod.value) return toast.show('請選擇付款方式', 'danger')
    if (currentPayHasCash.value && cashReceived.value < props.cartTotal.total)
      return toast.show('收現金額不足', 'danger')
    if (isLinePayMode.value && !linePayKey.value.trim())
      return toast.show('請掃描顧客 LINE Pay 付款條碼', 'warning')

    checkoutLoading.value = true
    try {
      const items = props.cart.map(r => ({
        product_name:    r.item.name,
        product_sku:     r.item.sku || '',
        unit:            '份',
        quantity:        r.quantity,
        unit_price:      props.rowPrice(r),
        // 庫存扣減用
        consume_inventory: r.item.consume_inventory ?? true,
        linked_products:   r.item.linked_products  || [],
        product_id:        r.item.product_id       || null,
        // 客製化記錄（存入訂單）
        customizations_selected: (r.selections || []).map((s: SelectionItem) => ({
          group_name:  s.group_name,
          choice_name: s.choice_name,
          extra_price: s.extra_price,
        })),
      }))

      const payment: Record<string, any> = {
        type:        selectedPayMethod.value,
        cash_amount: currentPayHasCash.value ? cashReceived.value : 0,
        card_amount: currentPayHasCash.value ? 0 : props.cartTotal.total,
      }
      if (isLinePayMode.value) payment.linepay_key = linePayKey.value.trim()

      const saleResp = await http.post('/pos/sale', {
        warehouse_id: props.selectedWarehouse,
        store_id:     auth.activeStoreId ?? undefined,
        items,
        payment,
        discount: props.discount,
        remark:   payRemark.value,
      })
      toast.show('結帳成功！', 'success')
      emit('success')              // 原 clearCart()，由 PosView 處理
      emit('update:show', false)   // 原 showPayment.value = false
      payRemark.value         = ''
      cashReceived.value      = 0
      linePayKey.value        = ''
      selectedPayMethod.value = enabledPayMethods.value[0]?.id ?? 'cash'

      // 電子發票自動開立
      if (props.invoiceEnabled && props.invAutoIssue && invMode.value !== 'none') {
        const orderId = saleResp.data?.order?._id
        if (orderId) {
          const payload: Record<string, string> = { order_id: orderId }
          if (invMode.value === 'scan') {
            payload.carrier_type = invEcpayType.value
            payload.carrier_num  = invNum.value
          } else if (invMode.value === 'tax') {
            payload.buyer_id = invBuyerId.value
          } else if (invMode.value === 'love') {
            payload.love_code = invLoveCode.value
          }
          try {
            await http.post('/invoice/issue', payload)
            toast.show('電子發票已開立', 'success')
          } catch (ie: any) {
            toast.show(`發票開立失敗：${ie?.response?.data?.message ?? '請至發票管理補開'}`, 'warning')
          }
        }
        setInvMode('none')
      }
    } catch (e: any) {
      toast.show(e?.response?.data?.message ?? '結帳失敗', 'danger')
    } finally {
      checkoutLoading.value = false
    }
  }

  return {
    selectedPayMethod, cashReceived, changeAmt, payRemark, checkoutLoading,
    enabledPayMethods, currentPayHasCash,
    denomMode, numpadPress, numpadBack, numpadClear, addDenom, fillExact,
    invMode, invScanRaw, invNum, invCarrierType, invBuyerId, invLoveCode, invScanRef,
    setInvMode, onInvInput, onInvScan, clearInvScan,
    linePayKey, linePayScanRef, isLinePayMode,
    selectPayMethod, confirmCheckout,
  }
}
