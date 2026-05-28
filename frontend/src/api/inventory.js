import client from './client'

export const inventoryApi = {
  getAll:    (params) => client.get('/inventory/',          { params }),
  adjust:    (data)   => client.post('/inventory/adjust',   data),
  movements: (params) => client.get('/inventory/movement/', { params }),
  batchIO:   (data)   => client.post('/inventory/batch',    data),   // QuickIO
}
