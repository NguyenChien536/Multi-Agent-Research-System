const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ts=require('typescript');
function compile(file){return ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src',file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX}}).outputText;}
const status={exports:{}};vm.runInNewContext(compile('lib/model-connection-status.ts'),status);
async function panel(root='https://openrouter.ai/api/v1',profile={}){
  const states=[],deps=[],effects=[],checks=[],saves=[];let cursor=0;
  const hooks={useState(initial){const i=cursor++;if(!(i in states))states[i]=initial;return[states[i],v=>states[i]=typeof v==='function'?v(states[i]):v];},
    useEffect(fn,next){const i=cursor++;if(!deps[i]||next.some((v,j)=>v!==deps[i][j])){deps[i]=next;effects.push(fn);}}};
  const Fields=()=>null;
  const api={auth:{hasSession:()=>true},tasks:{modelConnectionOptions:async()=>({})},settings:{
    getModelConnection:async()=>({connection:{base_url:root,model:'fixture:free',has_key:true,input_price_per_million:0,output_price_per_million:0,...profile}}),
    checkConnection:async value=>{checks.push(value);return{status:'quota_exhausted',quota:{used:51,limit:50,remaining:0}};},
    saveModelConnection:async value=>saves.push(value),
  }};
  const context={exports:{},URL,Event,window:new EventTarget(),require(name){
    if(name==='react')return hooks;if(name==='react/jsx-runtime')return require(name);
    if(name==='@/lib/api')return{api};if(name==='./ModelConnectionFields')return{ModelConnectionFields:Fields};
    if(name==='@/lib/model-connection-status')return status.exports;throw Error(name);
  }};
  vm.runInNewContext(compile('components/ModelSettingsPanel.tsx'),context);
  const render=()=>{cursor=0;return context.exports.ModelSettingsPanel({isEn:true});};
  render();while(effects.length)effects.shift()();await new Promise(setImmediate);
  return{render,checks,saves,Fields};
}
function nodes(n){if(!n||typeof n!=='object')return[];if(Array.isArray(n))return n.flatMap(nodes);return[n,...nodes(n.props?.children)];}
function text(n){if(n==null||typeof n==='boolean')return'';if(typeof n!=='object')return String(n);return Array.isArray(n)?n.map(text).join(''):text(n.props?.children);}
const button=(tree,label)=>nodes(tree).find(n=>n.type==='button'&&text(n)===label);

test('saved connection is read-only; metadata check neither generates nor saves and exposes quota',async()=>{
  const p=await panel();assert.ok(button(p.render(),'Edit connection'));
  assert.equal(nodes(p.render()).filter(n=>n.type===p.Fields).length,0);assert.equal(p.checks.length,0);
  await button(p.render(),'Check key & quota').props.onClick();
  assert.equal(p.checks[0].generate,false);assert.equal(p.checks[0].api_key,undefined);
  assert.equal(p.saves.length,0);assert.ok(text(p.render()).includes('51/50'));
  assert.ok(text(p.render()).includes('switching models on this account may not help'));
});
test('editing clears old check result and only explicit Save changes the profile',async()=>{
  const p=await panel();await button(p.render(),'Check key & quota').props.onClick();
  button(p.render(),'Edit connection').props.onClick();assert.ok(!text(p.render()).includes('51/50'));
  const fields=nodes(p.render()).find(n=>n.type===p.Fields);
  fields.props.onChange({...fields.props.value,model:'new:free'});assert.equal(p.saves.length,0);
  await nodes(p.render()).find(n=>n.type==='form').props.onSubmit({preventDefault(){}});
  assert.equal(p.saves[0].model,'new:free');assert.ok(button(p.render(),'Edit connection'));
});
test('Google response test requires free-tier confirmation; metadata check remains available',async()=>{
  const p=await panel('https://generativelanguage.googleapis.com/v1beta/openai');
  assert.equal(button(p.render(),'Check response').props.disabled,true);
  assert.equal(button(p.render(),'Check key & quota').props.disabled,false);
  nodes(p.render()).find(n=>n.type==='input'&&n.props.type==='checkbox').props.onChange({target:{checked:true}});
  assert.equal(button(p.render(),'Check response').props.disabled,false);
  await button(p.render(),'Check response').props.onClick();
  assert.equal(p.checks[0].generate,true);assert.equal(p.checks[0].free_tier_confirmed,true);
});

test('paid response test requires explicit consent for each small call',async()=>{
  const p=await panel('https://openrouter.ai/api/v1',{model:'google/gemini-2.5-flash',input_price_per_million:.3,output_price_per_million:2.5});
  assert.equal(button(p.render(),'Check response').props.disabled,true);
  assert.equal(p.checks.length,0);
  nodes(p.render()).find(n=>n.type==='input'&&n.props.type==='checkbox').props.onChange({target:{checked:true}});
  assert.equal(button(p.render(),'Check response').props.disabled,false);
  await button(p.render(),'Check response').props.onClick();
  assert.equal(p.checks[0].paid_probe_confirmed,true);
  assert.equal(button(p.render(),'Check response').props.disabled,true);
});
