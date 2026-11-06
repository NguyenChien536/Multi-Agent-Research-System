const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const ts=require('typescript');
const React=require('react');const {renderToStaticMarkup}=require('react-dom/server');
const exported={};const code=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/components/ResearchRecoveryNotice.tsx'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
new Function('require','exports',code)(name=>name==='next/link'?{__esModule:true,default:props=>React.createElement('a',props)}:require(name),exported);
const render=task=>renderToStaticMarkup(React.createElement(exported.ResearchRecoveryNotice,{task,isEn:true,busy:false,onContinue:()=>{}}));
test('budget-limited articles offer a new article instead of a futile retry',()=>{
 const html=render({status:'NEEDS_REVIEW',current_step:'BUDGET_LIMIT'});
 assert.ok(html.includes('Create new research'));assert.ok(!html.includes('Continue from failed step'));assert.ok(html.includes('Saved sources and results'));
});
test('failed articles have an explicit checkpoint continue action',()=>{
 assert.ok(render({status:'FAILED'}).includes('Continue from failed step'));
});
test('scheduled provider wait is automatic and has no duplicate continue action',()=>{
 const html=render({status:'QUEUED',provider_wait:{retry_at:'2026-11-06T01:00:00Z'}});
 assert.ok(html.includes('Automatic retry'));assert.ok(!html.includes('Continue from failed step'));
});
