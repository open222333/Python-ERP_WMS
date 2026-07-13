// [OPT-N4] .js → .ts 遷移（原內容不變，僅補型別）
import client from './client'
import type { Data, Id } from './types'

export const warehouseApi = {
  // 倉庫
  getAll:           ()               => client.get('/warehouse/'),
  getOne:           (id: Id)         => client.get(`/warehouse/${id}`),
  create:           (data: Data)     => client.post('/warehouse/', data),
  update:           (id: Id, d: Data) => client.put(`/warehouse/${id}`, d),
  delete:           (id: Id)         => client.delete(`/warehouse/${id}`),
  // 儲位
  getLocations:     (whId: Id)         => client.get(`/warehouse/${whId}/location/`),
  createLocation:   (whId: Id, d: Data) => client.post(`/warehouse/${whId}/location/`, d),
  updateLocation:   (locId: Id, d: Data) => client.put(`/warehouse/location/${locId}`, d),
  deleteLocation:   (locId: Id)        => client.delete(`/warehouse/location/${locId}`),
}
