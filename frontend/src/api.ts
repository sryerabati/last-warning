export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const headers = new Headers(options?.headers)
  if (options?.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(`/api${path}`, {...options, headers})
  if (!response.ok) {
    let detail: unknown
    try { detail = (await response.json()).detail } catch { detail = response.statusText }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return response.status === 204 ? undefined as T : response.json()
}
export function payload<T extends {id?: string; created_at?: string}>(value: T) {
  const {id, created_at, ...rest} = value
  void id; void created_at
  return JSON.stringify(rest)
}
export const clock = (seconds: number) => seconds>=3600?`${Math.floor(seconds/3600)}:${Math.floor(seconds/60%60).toString().padStart(2,'0')}:${Math.floor(seconds%60).toString().padStart(2,'0')}`:`${Math.floor(seconds/60).toString().padStart(2,'0')}:${Math.floor(seconds%60).toString().padStart(2,'0')}`
