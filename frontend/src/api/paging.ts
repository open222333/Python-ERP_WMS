/**
 * [U3] 分批取完整清單：後端列表有筆數上限（產品預設 200、最多 1000），
 * 原本前端直接 GET 一次，產品超過 200 個時選單與產品頁都會少資料且沒有提示。
 * 用 offset 逐批取，直到某批不足一頁為止。
 */
import http from './index'

export async function fetchAllPages<T = any>(
  url: string, params: Record<string, any> = {}, pageSize = 1000, maxItems = 20000,
): Promise<T[]> {
  const all: T[] = []
  for (let offset = 0; offset < maxItems; offset += pageSize) {
    const { data } = await http.get(url, { params: { ...params, limit: pageSize, offset } })
    const page: T[] = data?.data ?? data ?? []
    all.push(...page)
    if (page.length < pageSize) break
  }
  return all
}
