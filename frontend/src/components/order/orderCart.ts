/** [U10] 顧客點餐頁共用型別與計價（自 views/OrderView.vue 移出） */
export interface SelectionItem {
  group_id:    string
  group_name:  string
  choice_id:   string
  choice_name: string
  extra_price: number
}
export interface CartRow {
  item:       any
  qty:        number
  selections: SelectionItem[]
}

/** 同品項＋同客製組合視為同一列 */
export function selKey(sel: SelectionItem[]) {
  return sel.map(s => `${s.group_id}:${s.choice_id}`).sort().join('|')
}

/** 單價（含客製加價） */
export function rowPrice(row: CartRow): number {
  return (row.item.price || 0) + row.selections.reduce((s, x) => s + (x.extra_price || 0), 0)
}
