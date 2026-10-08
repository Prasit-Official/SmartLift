// Dependency-free DOM stub: tests quiz logic, not browser rendering.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.style={};this.events={};this.value='';}
 appendChild(x){this.children.push(x);return x;}
 append(...x){this.children.push(...x);}
 replaceChildren(){this.children=[];}
 addEventListener(name,fn){this.events[name]=fn;}
 click(){}
}
const ids={};for(const id of ['quizForm','learner','attemptType','quizResult','exportQuiz'])ids[id]=new Element('div');
ids.learner.value='P001';ids.attemptType.value='pre';
let answers=[1,2,0,1,2,1];let blob;
const ctx={document:{getElementById:id=>ids[id],createElement:tag=>new Element(tag),createTextNode:text=>({text})},
 FormData:class{get(key){return answers[Number(key.slice(1))];}},
 Blob:class{constructor(parts){blob=parts.join('');}},URL:{createObjectURL(){return 'blob:test';},revokeObjectURL(){}},setTimeout:fn=>fn(),Date,console};
vm.createContext(ctx);
const html=fs.readFileSync(require('node:path').join(__dirname,'../website/training-guide.html'),'utf8');
vm.runInContext(html.split('<script>')[1].split('</script>')[0],ctx);
ids.quizForm.events.submit({preventDefault(){}});
assert.match(ids.quizResult.children[0].textContent,/6\/6/);
ids.attemptType.value='post';answers=[0,0,0,0,0,0];
ids.quizForm.events.submit({preventDefault(){}});
assert.match(ids.quizResult.children[0].textContent,/1\/6/);
assert.equal(ids.quizResult.children[1].children.length,6);
ids.exportQuiz.events.click();const report=JSON.parse(blob);
assert.equal(report.attempts.length,2);assert.equal(report.attempts[0].subject_id,'P001');
assert.equal(report.attempts[1].type,'post');
console.log('Quiz logic PASS: pre/post scoring, feedback, participant ID and JSON export. Rendering not tested.');
