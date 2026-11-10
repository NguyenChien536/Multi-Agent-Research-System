const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const ts=require('typescript');
const React=require('react');const {renderToStaticMarkup}=require('react-dom/server');
const exported={};const code=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/components/ResearchRecoveryNotice.tsx'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
new Function('require','exports',code)(name=>name==='next/link'?{__esModule:true,default:props=>React.createElement('a',props)}:require(name),exported);
const render=task=>renderToStaticMarkup(React.createElement(exported.ResearchRecoveryNotice,{task,isEn:true,busy:false,onContinue:()=>{},onExtend:()=>{}}));
test('budget-limited articles offer a new article instead of a futile retry',()=>{
 const html=render({status:'NEEDS_REVIEW',current_step:'BUDGET_LIMIT'});
 assert.ok(html.includes('Create new research'));assert.ok(!html.includes('Continue from failed step'));assert.ok(html.includes('Saved sources and writing'));
});
test('failed articles have an explicit checkpoint continue action',()=>{
 assert.ok(render({status:'FAILED'}).includes('Continue from failed step'));
});
test('scheduled provider wait is automatic and has no duplicate continue action',()=>{
 const html=render({status:'QUEUED',provider_wait:{retry_at:'2026-11-06T01:00:00Z'}});
 assert.ok(html.includes('Automatic retry'));assert.ok(!html.includes('Continue from failed step'));
});

test('explicit recovery shows new resource limits while preserving the cost ceiling',()=>{
 const html=render({status:'NEEDS_REVIEW',current_step:'BUDGET_LIMIT',token_allowance:{can_extend:true,next_input_tokens:200000,next_output_tokens:100000,next_max_llm_calls:50,next_timeout_seconds:1800,max_cost_usd:.5}});
 assert.ok(html.includes('Approve limits and continue'));
 assert.ok(html.includes('200,000') && html.includes('100,000'));
 assert.ok(html.includes('The cost ceiling stays unchanged'));
 assert.ok(html.includes('50 calls') && html.includes('30 active minutes') && html.includes('$0.50'));
 assert.ok(!render({status:'NEEDS_REVIEW',current_step:'BUDGET_LIMIT',token_allowance:{can_extend:false}}).includes('Approve limits'));
});
