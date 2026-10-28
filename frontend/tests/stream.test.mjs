import test from 'node:test';
import assert from 'node:assert/strict';
import {readEvents} from '../.test-build/stream.js';
const encoder=new TextEncoder();
function response(bytes, fragment=1) {
  return new Response(new ReadableStream({start(controller){
    for(let i=0;i<bytes.length;i+=fragment)controller.enqueue(bytes.slice(i,i+fragment));
    controller.close();
  }}));
}
test('reads fragmented UTF-8, CRLF and heartbeat comments',async()=>{
  const input=': keep-alive\r\n\r\nevent: token\r\ndata: {"text":"Hello \u4f60\u597d"}\r\n\r\nevent: done\ndata: {"intent":"answer"}\n\n';
  const events=[];
  await readEvents(response(encoder.encode(input)),(event,data)=>events.push([event,data]));
  assert.deepEqual(events,[['token',{text:'Hello \u4f60\u597d'}],['done',{intent:'answer'}]]);
});
test('rejects a truncated frame',async()=>{
  await assert.rejects(readEvents(response(encoder.encode('event: token\ndata: {"text":"unfinished"}')) ,()=>{}),/unexpectedly/);
});
test('replacement event replaces the draft instead of appending',async()=>{
  let answer='';
  const input='event: token\ndata: {"text":"draft[99]"}\n\nevent: replace\ndata: {"text":"Insufficient evidence"}\n\n';
  await readEvents(response(encoder.encode(input)),(event,data)=>{
    if(event==='token')answer+=data.text;
    if(event==='replace')answer=data.text;
  });
  assert.equal(answer,'Insufficient evidence');
});
test('closes the reader when an error event interrupts processing',async()=>{
  let cancelled=false;
  const body=new ReadableStream({start(c){c.enqueue(encoder.encode('event: error\ndata: {"message":"Provider failed"}\n\n'));},cancel(){cancelled=true;}});
  await assert.rejects(readEvents(new Response(body),(event,data)=>{if(event==='error')throw new Error(data.message);}),/Provider failed/);
  assert.equal(cancelled,true);
});
