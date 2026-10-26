import { useEffect, useRef, useState } from 'react'
import { Paperclip, Send, LogOut, Search, Check, CheckCheck, X, FileText, ShieldCheck, MessageCircle } from 'lucide-react'
import { getMessages, getTyping, login, maxUploadMb, mediaUrl, sendMessage } from './api'
import type { ChatMessage } from './types'
import { formatted, timeLabel } from './format'

const allowed = ['image/jpeg','image/png','image/webp','application/pdf']
const stamp = () => new Date().toISOString()
function App() {
  const [phone,setPhone]=useState(localStorage.getItem('medbuddy_phone')||'')
  const [countryCode,setCountryCode]=useState('+91')
  const [phoneInput,setPhoneInput]=useState('')
  const [messages,setMessages]=useState<ChatMessage[]>([])
  const [typing,setTyping]=useState(false)
  const [draft,setDraft]=useState('')
  const [file,setFile]=useState<File|null>(null)
  const [filePreview,setFilePreview]=useState<string|null>(null)
  const [progress,setProgress]=useState<number|null>(null)
  const [toast,setToast]=useState('')
  const [preview,setPreview]=useState<string|null>(null)
  const [dragging,setDragging]=useState(false)
  const listRef=useRef<HTMLDivElement>(null)
  const followBottom=useRef(true)
  const lastIdRef=useRef(0)
  const fileRef=useRef<HTMLInputElement>(null)
  const retryFiles=useRef(new Map<number,File>())
  const lastMessage=messages[messages.length-1]
  const lastBot=[...messages].reverse().find(m=>m.direction==='out'&&!m.optimistic)?.text?.toLowerCase()||''
  const quick = lastBot.includes('confirm') ? ['Yes','No'] : (lastBot.includes('reply taken')||lastBot.includes('dose')&&lastBot.includes('taken')) ? ['Taken','Missed'] : []

  useEffect(()=>{ if(!toast)return; const t=setTimeout(()=>setToast(''),4500); return()=>clearTimeout(t)},[toast])
  useEffect(()=>{if(!file||!file.type.startsWith('image/')){setFilePreview(null);return}const url=URL.createObjectURL(file);setFilePreview(url);return()=>URL.revokeObjectURL(url)},[file])
  useEffect(()=>{
    if(!phone)return
    let active=true
    lastIdRef.current=0
    const fetchNew=async()=>{ if(document.hidden)return; try { const rows=await getMessages(phone,lastIdRef.current); if(active&&rows.length){lastIdRef.current=Math.max(lastIdRef.current,...rows.map(row=>row.id));setMessages(old=>{const ids=new Set(old.filter(x=>!x.optimistic).map(x=>x.id));return [...old,...rows.filter(x=>!ids.has(x.id))]})} } catch { if(active)setToast('MedBuddy is unreachable. Retrying…') } }
    const poll=()=>{void fetchNew(); void getTyping(phone).then(v=>active&&setTyping(v.typing)).catch(()=>{})}
    poll(); const timer=setInterval(poll,3000)
    const visibility=()=>{if(!document.hidden)poll()}; document.addEventListener('visibilitychange',visibility)
    return()=>{active=false;clearInterval(timer);document.removeEventListener('visibilitychange',visibility)}
  },[phone])
  useEffect(()=>{const el=listRef.current;if(el&&followBottom.current)el.scrollTo({top:el.scrollHeight,behavior:'smooth'})},[messages,typing])

  const signIn=async(e:React.FormEvent)=>{e.preventDefault();try{const result=await login(`${countryCode}${phoneInput}`);setPhone(result.phone);localStorage.setItem('medbuddy_phone',result.phone)}catch(err){setToast(err instanceof Error?err.message:'Could not log in')}}
  const validate=(f:File)=>{if(!allowed.includes(f.type)){setToast('Choose a JPEG, PNG, WebP, or PDF file.');return false}if(f.size>maxUploadMb*1024*1024){setToast(`Files must be ${maxUploadMb} MB or smaller.`);return false}setFile(f);return true}
  const send=async(value=draft, overrideFile?:File|null)=>{
    const current=overrideFile===undefined?file:overrideFile
    if((!value.trim()&&!current)||progress!==null)return
    const tempId=-Date.now()
    if(current)retryFiles.current.set(tempId,current)
    const optimistic:ChatMessage={id:tempId,phone,direction:'in',text:value.trim()||null,media_url:current?URL.createObjectURL(current):null,media_type:current?.type||null,media_name:current?.name||null,media_size:current?.size||null,created_at:stamp(),status:'sent',optimistic:true,progress:0}
    setMessages(old=>[...old,optimistic]);setDraft('');setFile(null);setProgress(0)
    try{const saved=await sendMessage(phone,value,current,p=>{setProgress(p);setMessages(old=>old.map(m=>m.id===tempId?{...m,progress:p}:m))});lastIdRef.current=Math.max(lastIdRef.current,saved.id);setMessages(old=>old.map(m=>m.id===tempId?saved:m));setProgress(null);retryFiles.current.delete(tempId);void getMessages(phone,saved.id).then(rows=>{if(rows.length){lastIdRef.current=Math.max(lastIdRef.current,...rows.map(row=>row.id));setMessages(old=>{const ids=new Set(old.filter(x=>!x.optimistic).map(x=>x.id));return [...old,...rows.filter(x=>!ids.has(x.id))]})}}).catch(()=>{})}
    catch(err){setProgress(null);setMessages(old=>old.map(m=>m.id===tempId?{...m,failed:true}:m));setToast(err instanceof Error?err.message:'Message failed to send')}
  }
  const retry=(m:ChatMessage)=>{const savedFile=retryFiles.current.get(m.id)||null;setMessages(old=>old.filter(x=>x.id!==m.id));void send(m.text||'',savedFile)}
  const logout=()=>{localStorage.removeItem('medbuddy_phone');setPhone('');setMessages([])}

  if(!phone)return <main className="login-screen"><form className="login-card" onSubmit={signIn}><div className="brand-mark"><MessageCircle size={29}/></div><h1>MedBuddy</h1><p className="muted">Your medication companion, right here.</p><label className="field-label">Phone number</label><div className="phone-field"><input className="country-code" aria-label="Country code" inputMode="numeric" value={countryCode} onChange={e=>setCountryCode('+'+e.target.value.replace(/\D/g,'').slice(0,3))}/><input autoFocus inputMode="numeric" placeholder="98765 43210" value={phoneInput} onChange={e=>setPhoneInput(e.target.value.replace(/\D/g,'').slice(0,15))}/></div><button className="primary wide">Continue</button><p className="login-foot"><ShieldCheck size={14}/> Proof-of-concept demo. Not for clinical use.</p></form></main>

  return <main className="app-bg"><div className="app-shell">
    <aside className="sidebar"><div className="side-top"><div className="avatar self">{phone.slice(-2)}</div><button className="icon-btn" title="Log out" onClick={logout}><LogOut size={19}/></button></div><div className="search"><Search size={16}/><input placeholder="Search or start a new chat" /></div><button className="chat-row"><div className="avatar bot">M</div><span className="chat-row-copy"><b>MedBuddy</b><small>{lastMessage?.text||'Your medication companion'}</small></span><time>{lastMessage?timeLabel(lastMessage.created_at):''}</time></button><div className="sidebar-note">Private demo chat<br/><span>{phone}</span></div></aside>
    <section className="chat-pane" onDragOver={e=>{e.preventDefault();setDragging(true)}} onDragLeave={e=>{if(!e.currentTarget.contains(e.relatedTarget as Node))setDragging(false)}} onDrop={e=>{e.preventDefault();setDragging(false);const f=e.dataTransfer.files[0];if(f)validate(f)}}>
      <header className="chat-header"><div className="avatar bot">M</div><div className="head-copy"><b>MedBuddy</b><small>{typing?'typing…':'online'}</small></div><button className="icon-btn mobile-logout" onClick={logout}><LogOut size={18}/></button></header>
      <div className="notice"><ShieldCheck size={17}/><span>This is a proof-of-concept demo, not for clinical use. Use sample prescriptions only. Prescription images are sent to a cloud LLM provider.</span></div>
      <div className="messages" ref={listRef} onScroll={e=>{const el=e.currentTarget;followBottom.current=el.scrollHeight-el.scrollTop-el.clientHeight<100}}>
        <div className="day"><span>Today</span></div>
        {!messages.length&&<div className="welcome"><div className="welcome-icon"><MessageCircle size={28}/></div><b>Welcome to MedBuddy</b><p>Send a message or attach a sample prescription to begin.</p></div>}
        {messages.map(m=><article key={m.id} className={`message ${m.direction==='in'?'mine':'theirs'} ${m.failed?'failed':''}`}>
          <div className="bubble">
            {m.media_url&&m.media_type?.startsWith('image/')&&<img className="chat-image" src={m.media_url.startsWith('blob:')?m.media_url:mediaUrl(m.media_url)} onClick={()=>setPreview(m.media_url!.startsWith('blob:')?m.media_url!:mediaUrl(m.media_url!))} alt="Attached prescription"/>}
            {m.media_url&&m.media_type==='application/pdf'&&<a className="pdf-card" href={m.media_url.startsWith('blob:')?m.media_url:mediaUrl(m.media_url)} target="_blank" rel="noreferrer"><span className="pdf-icon"><FileText/></span><span><b>{m.media_name||'Prescription.pdf'}</b><small>{m.media_size?`${(m.media_size/1024/1024).toFixed(2)} MB · `:''}PDF document</small></span></a>}
            {m.text&&<div className="message-text">{formatted(m.text)}</div>}
            {m.optimistic&&m.progress!==undefined&&<div className="upload-progress"><span style={{width:`${m.progress}%`}}/></div>}
            <footer><time>{timeLabel(m.created_at)}</time>{m.direction==='in'&&(!messages.some(other=>other.direction==='out'&&other.id>m.id)?<Check size={14}/>:typing?<CheckCheck size={16}/>:<CheckCheck size={16} className="ticks"/>)}{m.failed&&<button onClick={()=>retry(m)}>Retry</button>}</footer>
          </div>
        </article>)}
        {typing&&<div className="typing-bubble"><i/><i/><i/></div>}
      </div>
      {quick.length>0&&<div className="quick-replies">{quick.map(q=><button key={q} onClick={()=>void send(q)}>{q}</button>)}</div>}
      {file&&<div className="file-chip">{filePreview?<img className="file-thumb" src={filePreview} alt="Selected prescription"/>:<FileText size={22}/>}<span><b>{file.name}</b><small>{(file.size/1024/1024).toFixed(2)} MB</small></span><button onClick={()=>setFile(null)}><X size={17}/></button></div>}
      <form className="composer" onSubmit={e=>{e.preventDefault();void send()}}><button type="button" className="icon-btn attach" onClick={()=>fileRef.current?.click()}><Paperclip size={22}/></button><input ref={fileRef} hidden type="file" accept="image/jpeg,image/png,image/webp,application/pdf" onChange={e=>{const f=e.target.files?.[0];if(f)validate(f);e.currentTarget.value=''}}/><textarea value={draft} rows={1} placeholder="Type a message" onChange={e=>setDraft(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();void send()}}}/><button className="send-btn" aria-label="Send"><Send size={19}/></button></form>
      {dragging&&<div className="drop-overlay"><div><Paperclip size={34}/><b>Drop prescription here</b></div></div>}
      {toast&&<div role="alert" className="toast">{toast}<button onClick={()=>setToast('')}><X size={16}/></button></div>}
    </section>
  </div>{preview&&<div className="preview" onClick={()=>setPreview(null)}><button><X/></button><img src={preview} onClick={e=>e.stopPropagation()} alt="Prescription preview"/></div>}</main>
}
export default App
