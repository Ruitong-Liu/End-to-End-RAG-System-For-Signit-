import React, {useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';
import {readEvents} from './stream';
type Source = {id:string; source:string; heading:string; text:string; citation:number; score:number|null};
const statusLabels:Record<string,string>={answer:'Answer complete',retrieval_only:'Sources found',insufficient_evidence:'Insufficient evidence',clarify:'More information needed',greeting:'Welcome',handoff:'Human support'};
type Turn = {question:string; answer:string; sources:Source[]; status:string; complete:boolean};
function App(){
 const [turns,setTurns]=useState<Turn[]>([]); const [question,setQuestion]=useState('');
 const controller=useRef<AbortController|null>(null);
 const [busy,setBusy]=useState(false); const [error,setError]=useState('');
 async function ask(e:React.FormEvent){
  e.preventDefault(); if(busy||!question.trim())return;
  const q=question.trim(); const index=turns.length;
  const history=turns.filter(t=>t.complete).slice(-6).flatMap(t=>[{role:'user',content:t.question},{role:'assistant',content:t.answer}]);
  setTurns(t=>[...t,{question:q,answer:'',sources:[],status:'Searching documents…',complete:false}]); setQuestion('');setBusy(true);setError('');
  const update=(fn:(t:Turn)=>Turn)=>setTurns(ts=>ts.map((t,i)=>i===index?fn(t):t));
  let complete=false;
  const active=new AbortController(); controller.current=active;
  try{
   await readEvents(await fetch('/api/chat',{method:'POST',signal:active.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q,history})}), (event,data)=>{
    if(event==='status'){const labels:Record<string,string>={queued:'Waiting for an available slot…',rewriting:'Understanding your question…',retrieving:'Searching documents…',generating:'Writing answer · citations pending',validating:'Checking citations…'};update(t=>({...t,status:labels[data.phase]||'Working…'}));}
    if(event==='replace')update(t=>({...t,answer:data.text,complete:false}));
    if(event==='sources')update(t=>({...t,sources:data.items,status:'Preparing your answer…'}));
    if(event==='token')update(t=>({...t,answer:t.answer+data.text,status:'Writing answer · citations pending'}));
    if(event==='done'){complete=true;update(t=>({...t,complete:true,status:`${statusLabels[data.intent]||'Complete'} · ${data.latency_ms} ms${data.handoff?' · Consider contacting support':''}`}));}
    if(event==='error')throw new Error(data.message);
   });
   if(!complete)throw new Error('The response did not complete. Please try again.');
  }catch(e){
   if(active.signal.aborted){update(t=>({...t,status:'Stopped · partial answer not verified',complete:false}));}
   else{setError(e instanceof Error?e.message:'Request failed');update(t=>({...t,answer:'The answer could not be completed or verified. Please try again.',status:'Request failed',complete:false}));}
  }finally{controller.current=null;setBusy(false);}
 }
 return <main><header><div className="brand">SUPPORT / ATLAS</div><span>Document-grounded support</span></header>
  <section className="intro"><small>INTELLIGENT CUSTOMER SUPPORT</small><h1>Answers you can trace.</h1><p>Ask a product question and explore the supporting documents. When evidence is missing, we will tell you.</p></section>
  {turns.length===0&&<div className="suggestions">{['How do I reset my password?','How many records can one report export contain?','Talk to a human agent'].map(q=><button key={q} onClick={()=>setQuestion(q)}>{q} ↗</button>)}</div>}
  <div aria-live="polite">{turns.map((t,i)=><article key={i}><div className="question">{t.question}</div><div className="answer">{t.answer||'Searching relevant documents…'}</div><small>{t.status}</small><div className="sources">{t.sources.map(s=><details key={s.id}><summary>[{s.citation}] {s.source} · {s.heading}</summary><p className="source-note">Original source text — preserved in its original language.</p><pre>{s.text}</pre></details>)}</div></article>)}</div>
  {error&&<p role="alert" className="error">{error}</p>}
  <form onSubmit={ask}><label htmlFor="question">Your question</label><div className="input"><input id="question" maxLength={1000} value={question} onChange={e=>setQuestion(e.target.value)} placeholder="For example: How do I reset my password?" disabled={busy}/><button disabled={busy||!question.trim()}>{busy?'Working…':'Send ↗'}</button>{busy&&<button type="button" onClick={()=>controller.current?.abort()}>Stop</button>}</div></form>
  <footer>Live text is provisional until citation checks finish. Verify answers against the source documents. This assistant explains documentation and does not perform account or signing actions.</footer></main>;
}
createRoot(document.getElementById('root')!).render(<App/>);
