export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = options.body instanceof FormData ? {} : {'Content-Type': 'application/json'}
  const response = await fetch('/api' + path, {...options, credentials: 'same-origin', headers: {...headers, ...options.headers}})
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = data.detail
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((x: {msg: string}) => x.msg.replace(/^Value error,\s*/i, '')).join('；') : `请求失败（${response.status}）`)
  }
  return data
}
export function post<T>(path: string, body: unknown = {}): Promise<T> { return api(path, {method: 'POST', body: JSON.stringify(body)}) }
export const statusNames: Record<string, string> = {pending: '待处理', processing: '处理中', review: '待审核', published: '已发布', closed: '已关闭', queued: '排队中', running: '评价中', succeeded: '已生成草稿', failed: '执行失败', draft: '草稿'}
export function formatDate(s?: string | null) {
  if (!s) return '未记录时间'
  const value = new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(s) ? s : s + 'Z')
  return Number.isNaN(value.getTime()) ? '时间格式待核对' : value.toLocaleString('zh-CN', {hour12: false})
}
