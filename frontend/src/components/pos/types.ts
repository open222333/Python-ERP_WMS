// [REFACTOR] 自 PosView.vue 拆出（共用型別）
export interface SelectionItem {
  group_id:    string
  group_name:  string
  choice_id:   string
  choice_name: string
  extra_price: number
}

export interface CartRow {
  item:       any
  quantity:   number
  selections: SelectionItem[]
}
