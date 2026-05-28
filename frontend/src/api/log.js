import client from './client'

export const logApi = {
  getAll: (params) => client.get('/log/', { params }),
}
