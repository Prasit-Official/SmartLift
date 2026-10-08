// DOM simulation: verifies feedback and event refresh, not browser appearance.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),path=require('path');
const html=fs.readFileSync(path.join(__dirname,'../website/lift-safe-training.html'),'utf8');
class Element{get value(){return this._value||'';}set value(v){this._value=String(v);}constructor(){this.value='';this.textContent='';this.style={};this.children=[];this.disabled=false;this.events={};this.classList={add(){},remove(){}};}append(...els){this.children.push(...els);}replaceChildren(){this.children=[];}addEventListener(k,f){this.events[k]=f;}checkValidity(){return true;}contains(){return false;}focus(){}removeAttribute(){}}
const ids={};for(const m of html.matchAll(/id="([^"]+)"/g))ids[m[1]]=new Element();
const inputs=[];for(const m of html.matchAll(/<input[^>]*id="([^"]+)"[^>]*value="([^"]*)"/g)){ids[m[1]].value=m[2];inputs.push(ids[m[1]]);}
let timerId=0;const timers=new Map();const ctx={document:{getElementById:id=>ids[id],querySelectorAll:()=>inputs,querySelector:()=>new Element(),createElement:()=>new Element(),activeElement:null},location:{protocol:'http:'},window:{addEventListener(){}},fetch:()=>new Promise(()=>{}),setInterval(){},setTimeout:(f,ms)=>{const id=++timerId;timers.set(id,{f,ms});return id},clearTimeout:id=>timers.delete(id),Date,Math,console};
vm.createContext(ctx);vm.runInContext(html.split('<script>')[1].split('</script>')[0],ctx);
const settings={neck_warning:5,neck_danger:10,head_delta:12,head_absolute:25,head_confidence:.35,leg_rise:.08,zone_margin:.04,leg_dwell:2,forbidden_dwell:2,posture_dwell:2,snapshot_cooldown:10,max_people:20};
const state={settings,people:[],events:[],event_count:0,current_session:'monitor-1',active:false};ctx.state=state;vm.runInContext('render(state)',ctx);
(async()=>{
ids.posture_dwell.value='0';ids.posture_dwell.events.input();assert.match(ids.settingsNotice.textContent,/ยังไม่บันทึก/);assert.equal(ids.start.disabled,true);
let sent;ctx.fetch=async(url,opt)=>{sent=JSON.parse(opt.body);return {ok:true}};
await ids.saveSettings.onclick();assert.equal(sent.settings.posture_dwell,0);assert.equal(sent.settings.front_bend_enabled,1);assert.equal(sent.settings.front_torso_max,.6);assert.equal(sent.settings.front_shoulder_knee_max,1.6);assert.equal(sent.settings.front_knee_min,150);assert.match(ids.settingsNotice.textContent,/กำลังบันทึก/);assert.equal(ids.start.disabled,true);
// An HTTP acceptance is not confirmation. Only matching applied-result confirms.
ctx.state={...state,settings:{...settings,posture_dwell:0},settings_result:{request_id:sent.request_id,ok:true,saved_at:Date.now()/1000}};
vm.runInContext('render(state)',ctx);assert.match(ids.settingsNotice.textContent,/บันทึกตั้งค่าสำเร็จ/);assert.match(ids.appliedSettings.textContent,/ท่าก้ม 0 วิ/);assert.equal(ids.start.disabled,false);
// Saving identical values still receives a success confirmation.
await ids.saveSettings.onclick();ctx.state.settings_result.request_id=sent.request_id;vm.runInContext('render(state)',ctx);assert.match(ids.settingsNotice.textContent,/สำเร็จ/);
// Failure must not turn green or enable use of unconfirmed edits.
ids.posture_dwell.value='3';ids.posture_dwell.events.input();await ids.saveSettings.onclick();ctx.state.settings_result={request_id:sent.request_id,ok:false,error:'disk full'};vm.runInContext('render(state)',ctx);assert.match(ids.settingsNotice.textContent,/ไม่สำเร็จ/);assert.equal(ids.start.disabled,true);
// A new saved event triggers gallery loading without firing a polling timer.
vm.runInContext('var refreshCount=0;history=()=>{refreshCount++}',ctx);ids.sessionSelect.value='monitor-1';ctx.state.event_count=1;ctx.state.events=[{id:4,session:'monitor-1',image:'event.jpg',crop:'crop.jpg',created_at:new Date().toISOString(),reasons:['ท่าก้ม']}];
vm.runInContext('render(state)',ctx);assert.equal(ctx.refreshCount,1);assert.equal(ids.captureNotice,undefined);assert.equal(ids.capturePreview,undefined);
vm.runInContext('render(state)',ctx);assert.equal(ctx.refreshCount,1);
// Hide after exactly the configured 5 seconds, and do not re-show on polling.
vm.runInContext("settingsMessage('saved',true)",ctx);assert.equal(ids.settingsNotice.hidden,false);
let timer=timers.get(vm.runInContext('noticeTimers.settingsNotice',ctx));assert.equal(timer.ms,5000);timer.f();assert.equal(ids.settingsNotice.hidden,true);
vm.runInContext("settingsMessage('new',true)",ctx);assert.equal(ids.settingsNotice.hidden,false);
const oldId=vm.runInContext('noticeTimers.settingsNotice',ctx);vm.runInContext("settingsMessage('newer',true)",ctx);assert.equal(timers.has(oldId),false);
ctx.state.error='camera error';vm.runInContext('render(state)',ctx);timer=timers.get(vm.runInContext('noticeTimers.error',ctx));assert.equal(timer.ms,5000);timer.f();assert.equal(ids.error.hidden,true);vm.runInContext('render(state)',ctx);assert.equal(ids.error.hidden,true);
// Decimal values supported by backend must not fail due to HTML step rules.
ids.neck_warning.value='0.6';ids.neck_danger.value='0.8';ids.head_delta.value='3.5';ids.margin.value='3.25';ids.leg_rise.value='8.5';ids.snapshot_cooldown.value='2.5';ids.posture_dwell.value='0';assert.equal(vm.runInContext('validateFields()',ctx),true);
ids.snapshot_cooldown.value='0';assert.equal(vm.runInContext('validateFields()',ctx),false);assert.match(ids.error.textContent,/เว้นการบันทึกเหตุเดิมซ้ำ/);
ids.snapshot_cooldown.value='10';ids.max_people.value='2.5';assert.equal(vm.runInContext('validateFields()',ctx),false);assert.match(ids.error.textContent,/จำนวนเต็ม/);
ids.max_people.value='20';ids.neck_danger.value='0.5';assert.equal(vm.runInContext('validateFields()',ctx),false);assert.match(ids.error.textContent,/น้อยกว่า/);
assert.match(html,/id="posture_dwell"[^>]*step="any"/);
ctx.state.is_image=true;ctx.state.active=false;ctx.state.people=[];vm.runInContext('render(state)',ctx);assert.equal(ids.start.textContent,'วิเคราะห์ภาพ');assert.equal(ids.imageTestInfo.hidden,false);assert.equal(ids.pause.hidden,true);assert.equal(ids.calibrate.hidden,true);assert.equal(ids.monitorHelp.hidden,true);
console.log('PASS: unsaved/queued/applied/failed settings, zero and identical values, no capture notification, gallery refresh, 5-second hide and no duplicate polling alerts. DOM simulation only.');
})().catch(e=>{console.error(e);process.exitCode=1});
