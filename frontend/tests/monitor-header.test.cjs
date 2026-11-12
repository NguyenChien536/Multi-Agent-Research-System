const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const source = fs.readFileSync(path.join(__dirname,'../src/components/monitoring/MonitorUI.tsx'),'utf8');
const code = ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText;
const context={exports:{},require(name){
  if(name==='react/jsx-runtime')return require(name);
  if(name==='lucide-react')return {Activity:()=>null,AlertTriangle:()=>null,RefreshCw:()=>null};
  if(name==='@/lib/monitoring')return {statusLabel:value=>value};
  if(name==='@/lib/i18n')return {useLanguage:()=>({language:'en'})};
  throw Error(name);
}};
vm.runInNewContext(code,context);
function nodes(n){if(!n||typeof n!=='object')return[];if(Array.isArray(n))return n.flatMap(nodes);return[n,...nodes(n.props?.children)];}
function text(n){if(n==null||typeof n==='boolean')return'';if(typeof n!=='object')return String(n);if(Array.isArray(n))return n.map(text).join('');return text(n.props?.children);}

test('compact metadata row retains refresh action and stale-data warning',()=>{
  let refreshed=0;
  const tree=context.exports.PollStatus({compact:true,error:'Temporarily offline',lastSuccess:new Date('2026-11-09T03:00:00Z'),refresh:()=>refreshed++,
    details:React.createElement('span',null,'Started: 09:00 · Sampled at: 09:05')});
  const row=tree.props.children[0];
  assert.match(text(row), /Started: 09:00 · Sampled at: 09:05/);
  assert.match(text(row), /Last synchronized:/);
  assert.match(text(row), /Refresh now/);
  assert.doesNotMatch(row.props.className, /border-zinc/);
  nodes(row).find(n=>n.type==='button').props.onClick();
  assert.equal(refreshed,1);
  const alert=nodes(tree).find(n=>n.props?.role==='alert');
  assert.match(text(alert), /Temporarily offline/);
  assert.match(text(alert), /Showing cached data/);
  assert.doesNotMatch(text(row), /Auto-refreshes periodically/);
});
