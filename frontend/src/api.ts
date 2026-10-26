import type { ChatMessage } from './types'

const base = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')
export const maxUploadMb = Number(import.meta.env.VITE_MAX_UPLOAD_MB || 10)
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${base}${path}`, init)
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || `Request failed (${response.status})`)
  }
  return response.json()
}
export const login = (phone: string) => request<{phone:string;is_new:boolean}>('/api/login', {
  method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({phone}),
})
export const getMessages = (phone: string, afterId = 0) => request<ChatMessage[]>(
  `/api/messages?phone=${encodeURIComponent(phone)}&after_id=${afterId}`,
)
export const getTyping = (phone: string) => request<{typing:boolean}>(`/api/typing?phone=${encodeURIComponent(phone)}`)
export function sendMessage(phone: string, text: string, file: File | null, onProgress: (p:number)=>void) {
  return new Promise<ChatMessage>((resolve,reject)=>{
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${base}/api/messages`)
    xhr.upload.onprogress = e => { if(e.lengthComputable) onProgress(Math.round(e.loaded/e.total*100)) }
    xhr.onload = () => {
      if(xhr.status>=200 && xhr.status<300) resolve(JSON.parse(xhr.responseText))
      else { try { reject(new Error(JSON.parse(xhr.responseText).detail || 'Upload failed')) } catch { reject(new Error('Upload failed')) } }
    }
    xhr.onerror = () => reject(new Error('Could not reach MedBuddy. Check your connection and retry.'))
    const body = new FormData(); body.append('phone',phone); if(text.trim()) body.append('text',text.trim()); if(file) body.append('file',file)
    xhr.send(body)
  })
}
export const mediaUrl = (path: string) => `${base}${path}`
