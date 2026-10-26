export type ChatMessage = {
  id: number
  phone: string
  direction: 'in' | 'out'
  text: string | null
  media_url: string | null
  media_type: string | null
  media_name: string | null
  media_size: number | null
  created_at: string
  status: string
  optimistic?: boolean
  progress?: number
  failed?: boolean
}
