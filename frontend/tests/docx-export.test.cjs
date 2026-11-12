const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const JSZip = require('jszip');

const source = fs.readFileSync(path.join(__dirname, '../src/lib/docxExport.ts'), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
}}).outputText;
const exported = {};
new Function('require', 'exports', compiled)(require, exported);

test('Word export preserves the manuscript bibliography without fabricated identity or uncited sources', async () => {
  const blob = await exported.createPaperDocx({
    title: 'Version-specific title',
    markdownContent: '# Version-specific title\n\n## Abstract\n\nThe supported summary.\n\n## Methods\n\n### Recorded procedure\n\nThe actual procedure.\n\n## References\n\n[7] Original reference from this version.',
    doi: '10.fake/SHOULD_NOT_APPEAR',
    abstract: 'TASK_DESCRIPTION_IS_NOT_AN_ABSTRACT',
    sources: [{title: 'UNCITED_SOURCE', url: 'https://example.com/not-cited'}],
    keywords: ['SEARCH_QUERY_IS_NOT_A_KEYWORD'],
  });
  const files = await JSZip.loadAsync(await blob.arrayBuffer());
  const xml = await files.file('word/document.xml').async('string');
  assert.ok(xml.includes('Original reference from this version.'));
  assert.ok(xml.includes('Recorded procedure'));
  assert.equal((xml.match(/Version-specific title/g) || []).length, 1);
  for (const fake of ['10.fake/', '10.synthia/', 'Consortium', 'CONSORTIUM',
      'TASK_DESCRIPTION_IS_NOT_AN_ABSTRACT', 'UNCITED_SOURCE', 'SEARCH_QUERY_IS_NOT_A_KEYWORD']) {
    assert.ok(!xml.includes(fake), `Export introduced ${fake}`);
  }
  assert.ok(xml.includes('AI-assisted draft'));
});

test('Word export retains table headings, metrics and aligned Markdown separator semantics', async () => {
  const blob = await exported.createPaperDocx({title: 'Metric table', markdownContent:
    '## Results\n\n| Method | **RMSE** |\n| :--- | ---: |\n| Baseline | 1.2345 |\n| Ridge | 0.3456 |'});
  const archive = await JSZip.loadAsync(await blob.arrayBuffer());
  const xml = await archive.file('word/document.xml').async('string');
  for (const value of ['Method', 'RMSE', 'Baseline', '1.2345', 'Ridge', '0.3456']) {
    assert.ok(xml.includes(value), `Missing table value ${value}`);
  }
  assert.ok(!xml.includes(':---'), 'Markdown alignment separator must not become a data row');
});
