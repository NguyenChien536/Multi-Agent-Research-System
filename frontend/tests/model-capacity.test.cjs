const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync(path.join(__dirname,'../src/components/ModelConnectionFields.tsx'),'utf8');
const code = ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX}}).outputText;
const root='https://openrouter.ai/api/v1';
const catalog=[
  {id:'fixture/small:free',free:true,max_output_tokens:8192,supports_json_schema:false},
  {id:'fixture/large:free',free:true,max_output_tokens:460800,supports_json_schema:true},
];
async function panel(model='openrouter/free',selectedRoot=root,rows=catalog) {
  let value={api_key:'fake-not-real',base_url:selectedRoot,model,input_price_per_million:0,output_price_per_million:0,output_token_limit:8192};
  let cursor=0; const states=[],deps=[],effects=[];
  const hooks={
    useState(initial){const i=cursor++; if(!(i in states)) states[i]=initial;return[states[i],v=>{states[i]=typeof v==='function'?v(states[i]):v;}];},
    useRef(initial){const i=cursor++;if(!(i in states))states[i]={current:initial};return states[i];},
    useEffect(callback,next){const i=cursor++;if(!deps[i]||next.some((v,j)=>v!==deps[i][j])){deps[i]=next;effects.push(callback);}},
  };
  const context={exports:{},require(name){
    if(name==='react')return hooks;
    if(name==='react/jsx-runtime')return require(name);
    if(name==='@/lib/api')return{api:{tasks:{modelConnectionOptions:async()=>({base_urls:[selectedRoot]})},settings:{discoverModels:async()=>({models:rows})}}};
    throw Error(name);
  }};
  vm.runInNewContext(code,context);
  const render=()=>{cursor=0;return context.exports.ModelConnectionFields({value,onChange:v=>value=v,isEn:true});};
  render();while(effects.length)effects.shift()();await new Promise(setImmediate);
  return{render,value:()=>value};
}
function nodes(n){if(!n||typeof n!=='object')return[];if(Array.isArray(n))return n.flatMap(nodes);return[n,...nodes(n.props?.children)];}
function text(n){if(n==null||typeof n==='boolean')return'';if(typeof n!=='object')return String(n);if(Array.isArray(n))return n.map(text).join('');return text(n.props?.children);}
const button=(tree,label)=>nodes(tree).find(n=>n.type==='button'&&text(n).startsWith(label));

test('loading free catalog replaces router placeholder with highest output model and its maximum',async()=>{
  const p=await panel();await button(p.render(),'Load available models').props.onClick();
  assert.equal(p.value().model,'fixture/large:free');assert.equal(p.value().output_token_limit,460800);
  assert.equal(p.value().structured_output_mode,'json_schema');
});
test('loading catalog preserves explicit model; choosing another model uses its own maximum',async()=>{
  const p=await panel('fixture/small:free');await button(p.render(),'Load available models').props.onClick();
  assert.equal(p.value().model,'fixture/small:free');assert.equal(p.value().output_token_limit,8192);
  const select=nodes(p.render()).find(n=>n.type==='select'&&n.props.value==='fixture/small:free');
  select.props.onChange({target:{value:'fixture/large:free'}});
  assert.equal(p.value().output_token_limit,460800);
});
test('model maximum button restores advertised maximum after manual editing',async()=>{
  const p=await panel();await button(p.render(),'Load available models').props.onClick();
  const input=nodes(p.render()).find(n=>n.type==='input'&&n.props.type==='number'&&n.props.value===460800);
  input.props.onChange({target:{value:'16384'}});assert.equal(p.value().output_token_limit,16384);
  button(p.render(),'Use model maximum').props.onClick();assert.equal(p.value().output_token_limit,460800);
});

test('invalid Google model names are flagged; selecting a catalog model sets its compatible output mode',async()=>{
  const google='https://generativelanguage.googleapis.com/v1beta/openai';
  const rows=[{id:'gemma-fixture',display_name:'Gemma fixture',free:null,max_output_tokens:32768,recommended_output_mode:'prompt_json'}];
  const p=await panel('geminiTypo',google,rows);await button(p.render(),'Load available models').props.onClick();
  assert.ok(text(p.render()).includes('This model was not found'));
  const select=nodes(p.render()).find(n=>n.type==='select'&&n.props.value==='geminiTypo');
  assert.ok(text(select).includes('Gemma fixture'));
  select.props.onChange({target:{value:'gemma-fixture'}});
  assert.equal(p.value().structured_output_mode,'prompt_json');assert.equal(p.value().output_token_limit,32768);
});
