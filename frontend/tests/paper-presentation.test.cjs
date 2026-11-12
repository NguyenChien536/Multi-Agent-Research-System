const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

function load(relative) {
  const filename = path.resolve(__dirname, relative);
  const source = ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
    jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true,
  } }).outputText;
  const exports = {};
  const scopedRequire = name => name.startsWith('.')
    ? load(path.relative(__dirname, path.resolve(path.dirname(filename), name + (name.endsWith('Presentation') ? '.ts' : '.tsx'))))
    : require(name);
  new Function('require', 'exports', source)(scopedRequire, exports);
  return exports;
}
const presentation = load('../src/lib/paperPresentation.ts');
const { MarkdownViewer } = load('../src/components/ui/MarkdownViewer.tsx');
const render = content => renderToStaticMarkup(React.createElement(MarkdownViewer, { content }));

test('preview removes only the repeated initial title and preserves the original source', () => {
  const manuscript = '# **A study**\n\n## Abstract\n\nText.\n# Other heading';
  assert.equal(presentation.withoutRepeatedTitle(manuscript, 'A study'), '## Abstract\n\nText.\n# Other heading');
  assert.equal(presentation.withoutRepeatedTitle(manuscript, 'Different title'), manuscript);
  assert.equal(presentation.withoutRepeatedTitle('## A study\nText', 'A study'), '## A study\nText');
});

test('math renders inline and block formulas without interpreting fenced or inline code', () => {
  const html = render('The error is $x^2$.\n\n$$\n\\frac{1}{n}\\sum_i x_i\n$$\n\n`$raw$`\n\n```tex\n$x^2$\n```');
  assert.equal((html.match(/class="katex"/g) || []).length, 2);
  assert.ok(html.includes('<math'));
  assert.ok(html.includes('>$raw$</code>'));
  assert.ok(html.includes('<code>$x^2$</code>'));
  assert.ok(render('\\[x^2\\]').includes('katex-display'));
  assert.ok(!render('$$ unclosed').includes('class="katex"'));
  assert.ok(!render('Costs between $10 and $20 per unit.').includes('class="katex"'));
  assert.ok(!render('Escaped \\$10 and \\$20.').includes('class="katex"'));
});

test('untrusted links and math cannot introduce active content; legitimate citations survive', () => {
  const html = render('[unsafe](javascript:alert) [data](data:text/html,evil) [file](file:///secret) [source](https://example.org/paper) [1]\n\n$\\href{javascript:alert}{evil}$\n<script>alert(1)</script>');
  assert.ok(!/href="(?:javascript|data|file):/i.test(html));
  assert.ok(!html.includes('<script>'));
  assert.ok(html.includes('rel="noopener noreferrer"'));
  assert.ok(html.includes('href="https://example.org/paper"'));
  assert.ok(html.includes('Citation [1]'));
});

test('oversize formulas bypass KaTeX and recursive macros stop without crashing the article', () => {
  const huge = render('$' + '<'.repeat(4100) + '$');
  assert.ok(!huge.includes('class="katex"'));
  assert.ok(huge.includes('&lt;'));
  const loop = render('$\\def\\a{\\a}\\a$\n\nEnd of article.');
  assert.ok(loop.includes('katex-error'));
  assert.ok(loop.includes('End of article.'));
  const sizing = render('$\\rule{999em}{999em}$');
  // MathML annotation retains the original TeX; only visual CSS dimensions are bounded.
  assert.ok(!/style="[^"]*999em/.test(sizing));
  assert.ok(/style="[^"]*20em/.test(sizing));
});
