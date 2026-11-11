import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parseFragment } from 'parse5'
import { renderMarkdown } from './render.mjs'

const URL_ATTRS = new Set(['href', 'src', 'srcdoc', 'action', 'formaction', 'xlink:href', 'poster'])
const BANNED_TAGS = new Set(['script', 'style', 'iframe', 'object', 'embed', 'svg', 'math', 'link', 'meta', 'base'])

function assertSafeDom(html) {
  const walk = node => {
    if (!node || typeof node !== 'object') return
    if (node.tagName) {
      const tag = String(node.tagName).toLowerCase()
      assert.equal(BANNED_TAGS.has(tag), false, `banned tag <${tag}> in ${html}`)
      for (const attr of node.attrs || []) {
        const name = String(attr.name).toLowerCase()
        assert.equal(/^on/.test(name), false, `${tag} ${name}`)
        if (URL_ATTRS.has(name)) {
          assert.doesNotMatch(String(attr.value), /javascript:/i, attr.value)
          assert.doesNotMatch(String(attr.value), /^\s*data:/i, attr.value)
        }
      }
    }
    for (const child of node.childNodes || []) walk(child)
  }
  walk(parseFragment(html))
}

function fixture(name) {
  return fs.readFileSync(new URL(`./fixtures/${name}`, import.meta.url), 'utf8')
}

const base = { sourceBase: '/proj/v1/source', filePath: '/docs/README.md' }

function render(markdown, options = base) {
  return renderMarkdown(markdown, options)
}

test('renders GFM headings, lists, tables, fences, and strikethrough', () => {
  const html = render(`# Title

- item
- [x] done
- [ ] todo

| A | B |
| - | - |
| 1 | 2 |

~~gone~~ and 10~20

\`inline\`

\`\`\`js
console.log(1)
\`\`\`

https://example.com/docs
`)
  assert.match(html, /<h1 id="md-title">Title<\/h1>/)
  assert.match(html, /<li>item<\/li>/)
  assert.match(html, /<input[^>]*checked[^>]*disabled|<input[^>]*disabled[^>]*checked/)
  assert.match(html, /<table>/)
  assert.match(html, /<del>gone<\/del>/)
  assert.match(html, /10~20/)
  assert.doesNotMatch(html, /<del>20<\/del>/)
  assert.match(html, /<code>inline<\/code>/)
  assert.match(html, /<pre><code class="language-js">/)
  assert.match(html, /console\.log/)
  assert.match(html, /href="https:\/\/example\.com\/docs"/)
  assert.match(html, /target="_blank"/)
  assert.match(html, /rel="nofollow noopener noreferrer"/)
})

test('rewrites relative links and images into the file browser', () => {
  const html = render(`
[guide](note.markdown)
[root](/README.md)
[up](../README.md)
[hash](#title)
![pixel](../images/pixel.png)
![remote](https://example.com/a.png)
`)
  assert.match(html, /href="\/proj\/v1\/source\/docs\/note\.markdown"/)
  assert.match(html, /href="\/proj\/v1\/source\/README\.md"/)
  assert.match(html, /href="\/proj\/v1\/source\/README\.md"/)
  assert.match(html, /href="#md-title"/)
  assert.match(html, /src="\/proj\/v1\/source\/images\/pixel\.png\?raw"/)
  assert.match(html, /src="https:\/\/example\.com\/a\.png"/)
})

test('does not execute raw HTML or dangerous URLs', () => {
  const html = render(`
<script>alert('xss-md')</script>

before <img src=x onerror="alert('xss-md')"> after

[click](javascript:alert('xss-md'))

[click2](JaVaScRiPt:alert(1))

[spaced](java\nscript:alert(1))

[data](data:text/html,boom)

![bad](javascript:alert(1))

![svg](data:image/svg+xml,boom)

[trick](https://example.com/" onclick="alert(1))
`)
  assertSafeDom(html)
  assert.doesNotMatch(html, /<script[\s>]/i)
  assert.doesNotMatch(html, /xss-md/)
  assert.doesNotMatch(html, /href="javascript:/i)
  assert.doesNotMatch(html, /src="javascript:/i)
  assert.doesNotMatch(html, /src="data:/i)
  assert.doesNotMatch(html, /href="data:/i)
  assert.match(html, /<p><a>click<\/a><\/p>/)
  assert.match(html, /<span>bad<\/span>/)
  // The inline image is kept as an element, with the handler removed.
  assert.match(html, /before <img src="\/proj\/v1\/source\/docs\/x\?raw"> after/)
})

test('drops HTML comments and keeps a parent-directory image from the repo root', () => {
  const html = renderMarkdown(`<!-- secret -->
# Notes
![pixel](images/pixel.png)
`, { sourceBase: '/proj/v1/source', filePath: '/README.md' })
  assert.doesNotMatch(html, /secret/)
  assert.match(html, /<h1 id="md-notes">/)
  assert.match(html, /src="\/proj\/v1\/source\/images\/pixel\.png\?raw"/)
})

test('keeps in-repo traversal inside the source tree', () => {
  const html = render('[x](../../../../etc/passwd)', {
    sourceBase: '/proj/v1/source',
    filePath: '/docs/README.md',
  })
  assert.match(html, /href="\/proj\/v1\/source\/etc\/passwd"/)
  assert.doesNotMatch(html, /href="\/etc\/passwd"/)
})

test('empty and non-string input do not throw', () => {
  assert.equal(renderMarkdown(''), '')
  assert.equal(renderMarkdown(null, base), '')
})

test('renders raw anchors, tables, and images from the harness README', () => {
  const html = renderMarkdown(fixture('readme-zh-raw-html.md'), {
    sourceBase: '/deepseek-harness/dsh-v0.2.2-rc.1/source',
    filePath: '/README.zh.md',
  })
  assert.match(html, /<a id="md-run-from-source"><\/a>/)
  assert.doesNotMatch(html, /&lt;a/)
  assert.doesNotMatch(html, /&#x3C;a/)
  assert.doesNotMatch(html, /&lt;table/)
  assert.match(html, /<table>/)
  assert.match(html, /<thead>/)
  assert.match(html, /<tbody>/)
  assert.match(html, /<th align="center">入群问卷<\/th>/)
  assert.match(html, /<th align="center">微信公众号<\/th>/)
  assert.match(html, /<td align="center">/)
  assert.match(html, /<img src="https:\/\/cdn\.deepseek\.com\/harness\/readme\/community-wecom-survey\.png" alt="DeepSeek Harness 入群问卷二维码" width="180" height="180">/)
  assert.match(html, /<img src="https:\/\/cdn\.deepseek\.com\/harness\/readme\/community-wecom-wechat-official-account\.png" alt="DeepSeek Harness 团队微信公众号二维码" width="180" height="180">/)
  assert.match(html, /href="https:\/\/trtgsjkv6r\.feishu\.cn\/share\/base\/form\/shrcnIt5twSVdLGD52KJBckGCgg"/)
  assert.match(html, /target="_blank"/)
  assert.match(html, /rel="nofollow noopener noreferrer"/)
  assert.match(html, /<h3 id="md-从源码运行">从源码运行<\/h3>/)
})

test('rewrites links and images that are written as raw HTML', () => {
  const html = render(`
<a href="note.markdown">guide</a>
<a href="#run-from-source">jump</a>
<img src="../images/pixel.png" alt="pixel">
<p>Hello<br>there</p>
<hr>
`, { sourceBase: '/proj/v1/source', filePath: '/docs/README.md' })
  assert.match(html, /href="\/proj\/v1\/source\/docs\/note\.markdown"/)
  assert.match(html, /href="#md-run-from-source"/)
  assert.match(html, /src="\/proj\/v1\/source\/images\/pixel\.png\?raw"/)
  assert.match(html, /alt="pixel"/)
  assert.match(html, /<p>Hello<br>there<\/p>/)
  assert.match(html, /<hr>/)
})

test('sanitizes dangerous raw HTML', () => {
  const html = render(`
<script>alert('xss-html')</script>
<style>body{background:url(javascript:alert(1))}</style>
<img src="javascript:alert(1)" alt="bad" onerror="alert(1)">
<img src="https://cdn.example.com/ok.png" alt="ok" width="12" height="12" oNeRrOr="alert(1)">
<a href="javascript:alert(1)" onclick="alert(1)">no</a>
<a href="JaVaScRiPt:alert(1)">no2</a>
<a href="java&#10;script:alert(1)">no3</a>
<a href="https://example.com" ONCLICK="alert(1)" style="color:red">ok</a>
<iframe src="https://evil.example/"></iframe>
<iframe srcdoc="<script>alert(1)</script>"></iframe>
<svg onload="alert(1)"><script>alert(1)</script></svg>
<p onclick="alert(1)">hi</p>
<math><mtext><table><mglyph><style><!--</style><img title="--><img src=x onerror=alert(1)>"></table></mtext></math>
`)
  assertSafeDom(html)
  assert.doesNotMatch(html, /<script[\s>]/i)
  assert.doesNotMatch(html, /<\/script/i)
  assert.doesNotMatch(html, /<style[\s>]/i)
  assert.doesNotMatch(html, /<iframe[\s>]/i)
  assert.doesNotMatch(html, /<svg[\s>]/i)
  assert.doesNotMatch(html, /javascript:/i)
  assert.doesNotMatch(html, /style="/i)
  assert.doesNotMatch(html, /xss-html/)
  assert.match(html, /src="https:\/\/cdn\.example\.com\/ok\.png"/)
  assert.match(html, /alt="ok"/)
  assert.match(html, /width="12"/)
  assert.match(html, /height="12"/)
  assert.match(html, /href="https:\/\/example\.com\/"/)
  assert.match(html, /<p>hi<\/p>/)
  assert.match(html, /<span>bad<\/span>/)
})

test('renders YAML frontmatter as a GitHub blob key/value table', () => {
  const zh = renderMarkdown(fixture('packages-core-readme.zh.md'), {
    sourceBase: '/deepseek-harness/dsh-v0.2.2-rc.1/source',
    filePath: '/packages/core/README.zh.md',
  })
  const description = 'core 分组地图：构成产品 API 主干的会话日志、系统提示词组装、工具注册表、agent（智能体）词汇与默认循环。'
  assert.match(
    zh,
    new RegExp(
      `<table><tbody><tr><th>description</th><td>${description}</td></tr><tr><th>kind</th><td>package-group</td></tr></tbody></table>`,
    ),
  )
  assert.doesNotMatch(zh, /<thead>/)
  assert.ok(zh.indexOf('<th>description</th>') < zh.indexOf('<h1'))
  assert.match(zh, /<h1[^>]*>packages\/core<\/h1>/)
  assert.doesNotMatch(zh, /"core 分组地图/)

  const en = renderMarkdown(fixture('packages-core-readme.md'), {
    sourceBase: '/deepseek-harness/dsh-v0.2.2-rc.1/source',
    filePath: '/packages/core/README.md',
  })
  assert.match(
    en,
    /<th>description<\/th><td>The core group map: the session log, system-prompt assembly, tool registry, agent vocabulary, and default loop that form the product API spine\.<\/td>/,
  )
  assert.match(en, /<th>kind<\/th><td>package-group<\/td>/)
  assert.ok(en.indexOf('<th>kind</th>') < en.indexOf('<h1'))
})

test('frontmatter scalars keep quotes off and nested values stay text', () => {
  const html = render(`---
description: "say \\"hi\\""
kind: package-group
count: 2
draft: false
empty: null
tags:
  - one
  - two
nested:
  danger: "<script>alert(1)</script>"
---

# After
`)
  assert.match(html, /<th>description<\/th><td>say "hi"<\/td>/)
  assert.match(html, /<th>kind<\/th><td>package-group<\/td>/)
  assert.match(html, /<th>count<\/th><td>2<\/td>/)
  assert.match(html, /<th>draft<\/th><td>false<\/td>/)
  assert.match(html, /<th>empty<\/th><td><\/td>/)
  assert.match(html, /<th>tags<\/th><td>one, two<\/td>/)
  assert.match(html, /<th>nested<\/th><td><table><tbody><tr><th>danger<\/th><td>/)
  assert.doesNotMatch(html, /<script[\s>]/i)
  assert.match(html, /<h1[^>]*>After<\/h1>/)
  assert.ok(html.indexOf('<th>description</th>') < html.indexOf('<h1'))
})

test('invalid, unclosed, and non-leading frontmatter do not throw', () => {
  const invalid = render('---\n: [\n<script>alert(1)</script>\n---\n\n# Hi\n')
  assert.match(invalid, /<h1[^>]*>Hi<\/h1>/)
  assert.match(invalid, /<pre><code class="language-yaml">/)
  assert.doesNotMatch(invalid, /<script[\s>]/i)

  const unclosed = render('---\ndescription: "hi"\n\n# Hi\n')
  assert.match(unclosed, /<h1[^>]*>Hi<\/h1>/)
  assert.doesNotMatch(unclosed, /<th>description<\/th>/)

  const later = render('# Title\n\n---\ndescription: "nope"\nkind: "x"\n---\n')
  assert.match(later, /<h1[^>]*>Title<\/h1>/)
  assert.doesNotMatch(later, /<th>description<\/th>/)

  const crlf = render('---\r\ndescription: "core"\r\nkind: "package-group"\r\n---\r\n')
  assert.match(crlf, /<th>description<\/th><td>core<\/td>/)
  assert.match(crlf, /<th>kind<\/th><td>package-group<\/td>/)

  const bom = render('\uFEFF---\ndescription: "hi"\nkind: "package-group"\n---\n')
  assert.match(bom, /<th>description<\/th><td>hi<\/td>/)

  assert.doesNotThrow(() => render('---\n'))
  assert.doesNotThrow(() => render('---\n---\n# Empty\n'))
  const scalar = render('---\nhello\n---\n# Title\n')
  assert.match(scalar, /<h1[^>]*>Title<\/h1>/)
  assert.match(scalar, /hello/)
  const empty = render('---\n---\n# Empty\n')
  assert.match(empty, /<h1[^>]*>Empty<\/h1>/)
  assert.doesNotMatch(empty, /<th>/)
})

test('frontmatter values that look like HTML are escaped', () => {
  const html = render('---\ndescription: "<script>alert(1)</script>"\nkind: "javascript:alert(1)"\n---\n')
  assert.match(html, /<th>description<\/th><td>/)
  assert.match(html, /<th>kind<\/th><td>javascript:alert\(1\)<\/td>/)
  assert.doesNotMatch(html, /<script[\s>]/i)
  assert.doesNotMatch(html, /<img[\s>]/i)
  assert.match(html, /&#x3C;script>alert\(1\)&#x3C;\/script>/)
})

test('cyclic YAML frontmatter does not hang the renderer', () => {
  const html = render('---\na: &cycle\n  name: loop\n  self: *cycle\nkind: "ok"\n---\n')
  assert.match(html, /<th>kind<\/th><td>ok<\/td>/)
  assert.match(html, /<th>name<\/th><td>loop<\/td>/)
  assert.doesNotMatch(html, /<script/i)
})

test('yaml frontmatter does not pollute Object.prototype', () => {
  const html = render('---\n__proto__:\n  polluted: true\nkind: "ok"\n---\n')
  assert.equal(/** @type {any} */ ({}).polluted, undefined)
  assert.match(html, /<th>kind<\/th><td>ok<\/td>/)
  assert.doesNotThrow(() => render('---\nconstructor:\n  prototype:\n    polluted: true\n---\n'))
  assert.equal(/** @type {any} */ ({}).polluted, undefined)
})
