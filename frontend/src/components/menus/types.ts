/** [U10] 菜單管理共用型別（自 views/admin/MenusView.vue 移出，供拆分後的子元件共用） */
export interface SimpleProduct   { _id: string; name: string; sku: string }
export interface SimpleWarehouse { _id: string; name: string }

export interface MenuCat {
  _id: string
  name: string
  sort_order: number
  status: number
}

export interface OptionChoice {
  _id:         string
  name:        string
  extra_price: number
  is_default:  boolean
}

export interface OptionGroup {
  _id:      string
  name:     string
  type:     'single' | 'multiple'
  required: boolean
  choices:  OptionChoice[]
}

export interface LinkedProduct {
  product_id:   string
  warehouse_id: string
  consume_qty:  number
}

export interface MenuItemData {
  _id:               string
  name:              string
  category:          string
  price:             number
  description:       string
  status:            number
  sort_order:        number
  consume_inventory: boolean
  linked_products:   LinkedProduct[]
  applied_group_ids: string[]
  applied_groups:    OptionGroup[]
}

export interface MenuData {
  _id:           string
  name:          string
  description:   string
  sort_order:    number
  status:        number
  store_id?:     string | null
  categories?:   MenuCat[]
  items?:        MenuItemData[]
  option_groups?: OptionGroup[]
}
