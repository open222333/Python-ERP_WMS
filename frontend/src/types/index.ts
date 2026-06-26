// ─── Auth ────────────────────────────────────────────────
export type Role = 'super_admin' | 'admin' | 'operator' | 'cashier' | 'viewer'

export interface MeResponse {
  success:       boolean
  username:      string
  role:          Role
  store_ids:     string[]
  template_id:   string | null
  template_name: string | null
  pages_enabled: Record<string, boolean> | null
}

// ─── User ────────────────────────────────────────────────
export interface User {
  _id:         string
  username:    string
  role:        Role
  store_ids:   string[]
  template_id: string | null
  created_at?: string
  locked?:     boolean
}

// ─── Store ───────────────────────────────────────────────
export interface Store {
  _id:           string
  name:          string
  code:          string
  status:        string
  store_role_id: string | null
  created_at:    string
}

// ─── StoreRole ───────────────────────────────────────────
export interface StoreRole {
  _id:         string
  name:        string
  description: string
  is_system:   boolean
  created_at:  string
}

// ─── UserTemplate ────────────────────────────────────────
export interface UserTemplate {
  _id:           string
  name:          string
  role:          Role
  description:   string
  pages_enabled: Record<string, boolean>
  is_system:     boolean
  created_at:    string
}

// ─── Product / Category ──────────────────────────────────
export interface Category {
  _id:        string
  name:       string
  sort_order: number
}

export interface Product {
  _id:         string
  name:        string
  sku:         string
  barcode?:    string
  category_id: string | null
  unit:        string
  sell_price?: number
  cost_price?: number
  price?:      number
  cost?:       number
  min_stock:   number
  description: string
  status:      number   // 1=啟用 0=停用
}

// ─── Warehouse ───────────────────────────────────────────
export interface Warehouse {
  _id:         string
  code?:       string
  name:        string
  address:     string
  manager?:    string
  phone?:      string
  description: string
  store_id?:   string | null
}

// ─── Inventory ───────────────────────────────────────────
export interface InventoryItem {
  _id:          string
  product_id:   string
  product_name: string
  sku:          string
  warehouse_id: string
  warehouse_name: string
  quantity:     number
  unit:         string
  updated_at:   string
}

// ─── Inbound / Outbound / Movement ───────────────────────
export interface StockMovement {
  _id:            string
  type:           'inbound' | 'outbound' | 'move'
  product_id:     string
  product_name:   string
  warehouse_id:   string
  warehouse_name: string
  to_warehouse_id?:   string
  to_warehouse_name?: string
  quantity:       number
  note:           string
  operator:       string
  created_at:     string
}

// ─── Customer Order ──────────────────────────────────────
export type OrderStatus = 'pending' | 'processing' | 'completed' | 'cancelled'

export interface OrderItem {
  product_id:   string
  product_name: string
  quantity:     number
  price:        number
}

export interface CustomerOrder {
  _id:        string
  table_no:   string
  items:      OrderItem[]
  total:      number
  status:     OrderStatus
  note:       string
  created_at: string
  updated_at: string
}

// ─── POS ─────────────────────────────────────────────────
export interface PosItem {
  product_id:   string
  product_name: string
  quantity:     number
  price:        number
  subtotal:     number
}

export interface PosSale {
  _id:            string
  items:          PosItem[]
  total:          number
  discount:       number
  paid:           number
  change:         number
  payment_method: string
  operator:       string
  note:           string
  refunded:       boolean
  created_at:     string
}

// ─── Menu ────────────────────────────────────────────────
export interface MenuCategory {
  _id:        string
  name:       string
  sort_order: number
  enabled:    boolean
}

export interface MenuItem {
  _id:         string
  name:        string
  category_id: string | null
  price:       number
  description: string
  image_url:   string
  enabled:     boolean
  sort_order:  number
}

export interface Menu {
  _id:        string
  name:       string
  categories: MenuCategory[]
  items:      MenuItem[]
  is_active:  boolean
}

// ─── Delivery ────────────────────────────────────────────
export type DeliveryPlatform = 'ubereats' | 'foodpanda'
export type DeliveryOrderStatus = 'pending' | 'accepted' | 'completed' | 'cancelled'

export interface DeliveryOrder {
  _id:        string
  platform:   DeliveryPlatform
  order_id:   string
  items:      OrderItem[]
  total:      number
  status:     DeliveryOrderStatus
  created_at: string
}

// ─── Log ─────────────────────────────────────────────────
export interface LogEntry {
  _id:        string
  action:     string
  target:     string
  detail:     string
  operator:   string
  created_at: string
}

// ─── Settings ────────────────────────────────────────────
export interface SystemSettings {
  default_warehouse_id: string | null
}

export interface PaymentMethod {
  id:         string
  label:      string
  enabled:    boolean
  has_cash:   boolean
  sort_order: number
}

// ─── Analytics ───────────────────────────────────────────
export interface SalesSummary {
  date:     string
  revenue:  number
  orders:   number
  items:    number
}
