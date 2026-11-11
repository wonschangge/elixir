/**
 * The blank Markdown pane happened because CSS hid the highlighted source
 * as soon as <html> had class "js", before setupMarkdownPreview filled the
 * preview. These cases use the real stylesheet and a DOM test double for
 * static/script.js.
 */
import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import { fileURLToPath } from 'node:url'

const cssPath = fileURLToPath(new URL('../../static/style.css', import.meta.url))
const scriptPath = fileURLToPath(new URL('../../static/script.js', import.meta.url))
const css = fs.readFileSync(cssPath, 'utf8')
const scriptSource = fs.readFileSync(scriptPath, 'utf8')

function displayRules() {
  const rules = []
  const re = /([^{}]+)\{([^{}]*)\}/g
  let match
  while ((match = re.exec(css)) !== null) {
    const display = /display\s*:\s*([^;]+)/.exec(match[2])
    if (!display) continue
    for (const selector of match[1].split(',')) {
      const text = selector.replace(/\s+/g, ' ').trim()
      if (!text.includes('markdown-preview') && !text.includes('markdown-source')) continue
      const target = text.endsWith('.markdown-source') ? 'source'
        : text.endsWith('.markdown-preview') ? 'preview'
          : null
      if (target === null) continue
      rules.push({ selector: text, target, display: display[1].trim() })
    }
  }
  return rules
}

function selectorMatches(selector, state) {
  const js = state.js === true
  const ready = state.ready === true
  const show = state.showSource === true
  switch (selector) {
    case '.markdown-preview':
      return true
    case '.js .source-markdown.markdown-ready:not(.show-source) .markdown-source':
    case '.js .source-markdown.markdown-ready:not(.show-source) .markdown-preview':
      return js && ready && !show
    case '.js .source-markdown.show-source .markdown-source':
    case '.js .source-markdown.show-source .markdown-preview':
      return js && show
    default:
      throw new Error(`unexpected markdown display selector: ${selector}`)
  }
}

/** Last matching display declaration wins, same as stylesheet order. */
function visibility(state) {
  const shown = { source: 'block', preview: 'block' }
  for (const rule of displayRules()) {
    if (!selectorMatches(rule.selector, state)) continue
    if (rule.target === 'source' || rule.target === 'preview') {
      shown[rule.target] = rule.display
    }
  }
  return shown
}

function classList(initial = []) {
  const values = new Set(initial)
  return {
    add(...names) { for (const name of names) values.add(name) },
    remove(...names) { for (const name of names) values.delete(name) },
    contains(name) { return values.has(name) },
    toggle(name, force) {
      const on = force === undefined ? !values.has(name) : force
      if (on) values.add(name)
      else values.delete(name)
      return on
    },
  }
}

/**
 * Document double for the file-view setup at the bottom of script.js.
 * readyState is already complete, so only setupFileView runs.
 */
function bootPreview({ text = '# Hi\n', render, omitRenderer = false }) {
  const nodes = {}
  function make(id, fields = {}) {
    const node = {
      id,
      classList: classList(fields.classes || []),
      dataset: fields.dataset || {},
      textContent: fields.textContent ?? '',
      innerHTML: '',
      checked: false,
      style: {},
      listeners: {},
      addEventListener(type, fn) {
        (this.listeners[type] ||= []).push(fn)
      },
    }
    nodes[id] = node
    return node
  }

  make('markdown-view', {
    classes: ['lxrcode', 'source-markdown'],
    dataset: { sourceBase: '/proj/v1/source', filePath: '/AGENTS.md' },
  })
  make('markdown-original')
  make('markdown-preview')
  make('markdown-source-data', { textContent: JSON.stringify(text) })
  make('wrap-lines')

  const document = {
    readyState: 'complete',
    documentElement: { classList: classList(['js']) },
    getElementById(id) { return nodes[id] || null },
    querySelector() { return null },
    querySelectorAll() { return [] },
    addEventListener() {},
    fonts: { ready: Promise.resolve() },
  }
  const window = {
    document,
    localStorage: {
      getItem() { return null },
      setItem() {},
    },
    requestAnimationFrame(fn) { fn() },
    addEventListener() {},
  }
  if (!omitRenderer) {
    window.ElixirMarkdown = { render }
  }

  const context = vm.createContext({ console, document, window })
  vm.runInContext(scriptSource, context, { filename: 'script.js' })
  return { document, nodes, window }
}

test('js without markdown-ready still shows the highlighted source', () => {
  const shown = visibility({ js: true, ready: false, showSource: false })
  assert.equal(shown.source, 'block')
  assert.equal(shown.preview, 'none')
})

test('a filled preview hides the source until Original source is checked', () => {
  const filled = visibility({ js: true, ready: true, showSource: false })
  assert.equal(filled.source, 'none')
  assert.equal(filled.preview, 'block')

  const original = visibility({ js: true, ready: true, showSource: true })
  assert.equal(original.source, 'block')
  assert.equal(original.preview, 'none')
})

test('successful render marks the view ready and fills the preview', () => {
  const { nodes } = bootPreview({
    text: '# AGENTS\n',
    render(markdown, options) {
      assert.equal(markdown, '# AGENTS\n')
      assert.equal(options.filePath, '/AGENTS.md')
      return '<h1 id="md-agents">AGENTS</h1>'
    },
  })
  const view = nodes['markdown-view']
  assert.equal(view.classList.contains('markdown-ready'), true)
  assert.equal(view.classList.contains('show-source'), false)
  assert.equal(nodes['markdown-original'].checked, false)
  assert.match(nodes['markdown-preview'].innerHTML, /<h1/)
  const shown = visibility({
    js: true,
    ready: view.classList.contains('markdown-ready'),
    showSource: view.classList.contains('show-source'),
  })
  assert.equal(shown.preview, 'block')
  assert.equal(shown.source, 'none')

  nodes['markdown-original'].checked = true
  for (const fn of nodes['markdown-original'].listeners.change) fn()
  assert.equal(view.classList.contains('show-source'), true)
  const back = visibility({
    js: true,
    ready: true,
    showSource: view.classList.contains('show-source'),
  })
  assert.equal(back.source, 'block')
  assert.equal(back.preview, 'none')
})

test('a render failure reveals the source and checks Original source', () => {
  const { nodes } = bootPreview({
    render() { throw new Error('render failed') },
  })
  const view = nodes['markdown-view']
  assert.equal(view.classList.contains('markdown-ready'), false)
  assert.equal(view.classList.contains('show-source'), true)
  assert.equal(nodes['markdown-original'].checked, true)
  assert.equal(nodes['markdown-preview'].innerHTML, '')
  const shown = visibility({
    js: true,
    ready: false,
    showSource: true,
  })
  assert.equal(shown.source, 'block')
  assert.equal(shown.preview, 'none')
})

test('a missing renderer reveals the source and checks Original source', () => {
  const { nodes } = bootPreview({ omitRenderer: true })
  assert.equal(nodes['markdown-view'].classList.contains('show-source'), true)
  assert.equal(nodes['markdown-original'].checked, true)
  assert.equal(nodes['markdown-view'].classList.contains('markdown-ready'), false)
})
