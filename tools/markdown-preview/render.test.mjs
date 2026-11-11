import assert from 'node:assert/strict'
import test from 'node:test'
import { renderMarkdown } from './render.mjs'

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
  assert.doesNotMatch(html, /<script[\s>]/i)
  assert.doesNotMatch(html, /<img[\s>]/i)
  assert.doesNotMatch(html, /<[a-zA-Z][^>]*\sonerror\s*=/i)
  assert.doesNotMatch(html, /<[a-zA-Z][^>]*\sonclick\s*=/i)
  assert.doesNotMatch(html, /href="javascript:/i)
  assert.doesNotMatch(html, /src="javascript:/i)
  assert.doesNotMatch(html, /src="data:/i)
  assert.doesNotMatch(html, /href="data:/i)
  assert.match(html, /&#x3C;script>alert/)
  assert.match(html, /<p><a>click<\/a><\/p>/)
  assert.match(html, /<span>bad<\/span>/)
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
