import React from 'react'
export function formatted(text: string) {
  const lines = text.split('\n')
  return lines.flatMap((line, li) => {
    const parts = line.split(/(\*+[^*\n]+\*+|_[^_\n]+_)/g)
    return [<React.Fragment key={`l${li}`}>{parts.map((p,i) => {
      if(p.startsWith('*')) return <strong key={i}>{p.replace(/^\*+|\*+$/g,'')}</strong>
      if(p.startsWith('_')&&p.endsWith('_')) return <em key={i}>{p.slice(1,-1)}</em>
      return <React.Fragment key={i}>{p.replace(/\*/g,'')}</React.Fragment>
    })}</React.Fragment>, ...(li<lines.length-1?[<br key={`b${li}`} />]:[]) ]
  })
}
export const timeLabel = (date: string) => new Date(date).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})
