const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const source=fs.readFileSync(path.join(__dirname,'../src/app/research/[id]/page.tsx'),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;

function elements(node) {
  if (!node || typeof node!=='object') return [];
  if (Array.isArray(node)) return node.flatMap(elements);
  return [node,...elements(node.props?.children)];
}
function text(node) {
  if (node==null || typeof node==='boolean') return '';
  if (typeof node!=='object') return String(node);
  if (Array.isArray(node)) return node.map(text).join('');
  return text(node.props?.children);
}
async function workspace(status='FAILED',kind='REVIEW',retryError=false) {
  const states=[],effects=[],calls=[];
  let cursor=0;
  const task={id:'fixture',title:'UI fixture research',research_question:'UI fixture question',status,research_type:kind,
    research_depth:'STANDARD',language:'en',attempt_number:2,max_iterations:2,current_iteration:0,
    max_sources:12,plan_version:1,total_tokens_used:20,total_cost_usd:0,
    created_at:new Date().toISOString(),updated_at:new Date().toISOString(),
    latest_error:'PROVIDER_UNAVAILABLE: 503',failed_agent:'Methodologist'};
  const hooks={
    useState:initial=>{const i=cursor++;if(!(i in states)) states[i]=initial;return [states[i],value=>{states[i]=typeof value==='function'?value(states[i]):value;}];},
    useRef:initial=>{const i=cursor++;if(!(i in states)) states[i]={current:initial};return states[i];},
    useEffect:callback=>{cursor++;effects.push(callback);},
    useCallback:callback=>{cursor++;return callback;},
  };
  const tasks=new Proxy({get:async()=>task,getReport:async()=>{throw {status:404};},getProtocol:async()=>({}),
    retry:async id=>{calls.push(['retry',id]);if(retryError)throw new Error('Network failure, please retry');},
    start:async id=>{calls.push(['start',id]);},cancel:async id=>{calls.push(['cancel',id]);},
    uploadDataset:async(id,file)=>{calls.push(['dataset',id,file.name]);return {file_name:file.name,rows_count:120,columns_count:3};},
  },{get:(target,key)=>target[key]|| (async()=>[])});
  const context={exports:{},Error,URLSearchParams,setInterval:()=>1,clearInterval(){},setTimeout(){},
    window:{location:{search:'',hash:''},confirm:()=>true},confirm:()=>true,document:{querySelector:()=>null},
    require:name=>{
      if(name==='react')return hooks;
      if(name==='react/jsx-runtime')return require(name);
      if(name==='next/link')return {default:'a'};
      if(name==='next/navigation')return {useParams:()=>({id:'fixture'}),useRouter:()=>({push(){}})};
      if(name==='@/lib/api')return {api:{tasks}};
      if(name==='@/lib/i18n')return {useLanguage:()=>({language:'en',t:key=>key})};
      if(name==='@/lib/monitoring')return {stageState:()=> 'pending'};
      if(name==='@/lib/paperPresentation')return {withoutRepeatedTitle:content=>content};
      if(name==='@/lib/docxExport')return {exportPaperToDocx(){}};
      if(name==='@/components/ui/MarkdownViewer')return {extractHeadings:()=>[],MarkdownViewer:'markdown'};
      if(name==='@/components/ResearchErrorNotice')return {ResearchErrorNotice:'error-notice',researchErrorText:()=> 'Provider is overloaded (503).'};
      if(name==='lucide-react')return new Proxy({},{get:(_,key)=>key});
      if(name.startsWith('@/components/'))return new Proxy({},{get:(_,key)=>key==='Button'?'button':key});
      throw new Error('Unexpected import '+name);
    }};
  vm.runInNewContext(compiled,context);
  function render(){cursor=0;return context.exports.default();}
  render();
  const initial=effects.splice(0);
  initial.forEach(callback=>callback());
  await new Promise(resolve=>setImmediate(resolve));
  return {render,calls};
}

test('failed workspace shows retry and uses the saved-step retry endpoint',async()=>{
  const h=await workspace();
  const tree=h.render();
  const notice=elements(tree).find(node=>node.type==='error-notice');
  assert.equal(notice.props.error,'PROVIDER_UNAVAILABLE: 503');
  assert.equal(notice.props.step,'Methodologist');
  await elements(tree).find(node=>node.type==='button' && text(node).includes('Retry research')).props.onClick();
  assert.deepEqual(h.calls,[['retry','fixture']]);
});
test('running workspace exposes the stop control',async()=>{
  const h=await workspace('RUNNING');
  await elements(h.render()).find(node=>node.type==='button' && text(node).includes('Stop research')).props.onClick();
  assert.deepEqual(h.calls,[['cancel','fixture']]);
});
test('collapsed pipeline can be reopened from the persistent header',async()=>{
  const h=await workspace();
  const toggle=()=>elements(h.render()).find(node=>node.props?.['aria-controls']==='stages-sidebar');
  assert.equal(toggle().props['aria-expanded'],true);
  toggle().props.onClick();
  assert.equal(toggle().props['aria-expanded'],false);
  toggle().props.onClick();
  assert.equal(toggle().props['aria-expanded'],true);
});
test('waiting computational research accepts CSV directly on the default workspace',async()=>{
  const h=await workspace('WAITING_USER_DATA','EMPIRICAL_COMPUTATIONAL');
  const input=elements(h.render()).find(node=>node.props?.['aria-label']==='Upload computational CSV');
  assert.ok(input);
  await input.props.onChange({target:{files:[{name:'synthetic.csv'}],value:'file'}});
  assert.deepEqual(h.calls,[['dataset','fixture','synthetic.csv']]);
  assert.ok(text(h.render()).includes('Uploaded successfully'));
});
test('retry errors stay visible inside the workspace',async()=>{
  const h=await workspace('FAILED','REVIEW',true);
  await elements(h.render()).find(node=>node.type==='button' && text(node).includes('Retry research')).props.onClick();
  await new Promise(resolve=>setImmediate(resolve));
  assert.ok(elements(h.render()).some(node=>node.props?.role==='alert' && text(node).includes('Network failure')));
});
