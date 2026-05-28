import client from './client'

export const warehouseApi = {
  // 倉庫
  getAll:           ()      => client.get('/warehouse/'),
  getOne:           (id)    => client.get(`/warehouse/${id}`),
  create:           (data)  => client.post('/warehouse/', data),
  update:           (id, d) => client.put(`/warehouse/${id}`, d),
  delete:           (id)    => client.delete(`/warehouse/${id}`),
  // 儲位
  getLocations:     (whId)  => client.get(`/warehouse/${whId}/location/`),
  createLocation:   (whId, d) => client.post(`/warehouse/${whId}/location/`, d),
  updateLocation:   (locId, d) => client.put(`/warehouse/location/${locId}`, d),
  deleteLocation:   (locId)    => client.delete(`/warehouse/location/${locId}`),
}
