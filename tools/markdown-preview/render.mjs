/**
 * Render Markdown to HTML for the Elixir file view.
 *
 * The parse stays on the deepseek-harness UI grammar
 * (packages/client/ui-primitives/src/markdown/parse.ts at tag dsh-v0.2.2-rc.1):
 * mdast-util-from-markdown + micromark-extension-gfm + mdast-util-gfm, with
 * GFM `singleTilde: false` so `10~20` stays literal. DSH walks that tree in
 * React and shows raw HTML as text. Elixir compiles the same tree to HTML.
 * A cmark-gfm swap is not required: micromark already emits html nodes, and
 * GitHub's YAML metadata table is a blob-view feature, not a cmark-gfm
 * feature, so a different parser would still need this pass.
 *
 * Raw HTML is parsed (hast-util-raw) and then sanitized with the GitHub-style
 * hast-util-sanitize schema. Script, style, event handlers, and non-http(s)
 * / mailto URLs cannot survive. YAML frontmatter at the start of a file is
 * turned into the vertical key/value table GitHub's blob view shows.
 * Math, mermaid, and DSH-only syntax extensions are not part of this preview.
 */

import { fromMarkdown } from 'mdast-util-from-markdown'
import { gfmFromMarkdown } from 'mdast-util-gfm'
import { gfm } from 'micromark-extension-gfm'
import { frontmatter } from 'micromark-extension-frontmatter'
import { frontmatterFromMarkdown } from 'mdast-util-frontmatter'
import { toHast } from 'mdast-util-to-hast'
import { toHtml } from 'hast-util-to-html'
import { raw } from 'hast-util-raw'
import { defaultSchema, sanitize } from 'hast-util-sanitize'
import { parse as parseYaml } from 'yaml'

/** Same option DSH passes to micromark-extension-gfm. */
const gfmOptions = { singleTilde: false }

function markdownParseOptions(withFrontmatter) {
  return {
    extensions: withFrontmatter
      ? [frontmatter('yaml'), gfm(gfmOptions)]
      : [gfm(gfmOptions)],
    mdastExtensions: withFrontmatter
      ? [frontmatterFromMarkdown('yaml'), gfmFromMarkdown()]
      : [gfmFromMarkdown()],
  }
}

/** Prefix on every id inside the preview so Markdown cannot clobber page controls. */
const ID_PREFIX = 'md-'

const ABSOLUTE_PROTOCOLS = new Set(['http:', 'https:', 'mailto:'])
const IMAGE_PROTOCOLS = new Set(['http:', 'https:'])

/**
 * @param {string} markdown
 * @param {{ sourceBase?: string, filePath?: string }} [options]
 * sourceBase is the Elixir source root (`/proj/tag/source`), no trailing slash.
 * filePath is the file inside that tree (`/docs/README.md`).
 * @returns {string} sanitized HTML
 */
export function renderMarkdown(markdown, options = {}) {
  const sourceBase = stripTrailingSlash(options.sourceBase || '')
  const filePath = options.filePath || '/'
  let text = typeof markdown === 'string' ? markdown : String(markdown ?? '')
  if (text.charCodeAt(0) === 0xfeff) text = text.slice(1)

  const tree = fromMarkdown(text, markdownParseOptions(true))
  const metadata = takeFrontmatter(tree)

  const hast = toHast(tree, { allowDangerousHtml: true })
  if (!hast || hast.type !== 'root') return ''

  let parsed
  try {
    parsed = raw(hast)
  } catch {
    parsed = hast
    rawToText(parsed)
  }
  if (!parsed || parsed.type !== 'root') return ''
  if (!parsed.children) parsed.children = []

  if (metadata) {
    const table = frontmatterTable(metadata, new WeakSet())
    if (table) parsed.children.unshift(table)
  }

  const headingIds = addHeadingIds(parsed)
  rewriteResources(parsed, { sourceBase, filePath, headingIds })

  const clean = sanitize(parsed, previewSchema())
  // Never serialize leftover raw nodes as HTML. The sanitizer already drops
  // them; this keeps a future schema change from becoming an XSS sink.
  return toHtml(clean, { allowDangerousHtml: false })
}

/**
 * YAML frontmatter is a GitHub blob-view feature: a vertical key/value table,
 * one row per key (`th` + `td`), no header row. Invalid YAML must not throw.
 * Unclosed fences are not frontmatter (micromark leaves them as Markdown).
 * A value that parses but is not a mapping is put back so it still renders.
 * @param {import('mdast').Root} tree
 * @returns {Record<string, unknown> | null}
 */
function takeFrontmatter(tree) {
  const node = tree.children[0]
  if (!node || node.type !== 'yaml') return null

  const source = typeof node.value === 'string' ? node.value : ''
  let data
  try {
    data = parseYaml(source, {
      maxAliasCount: 100,
      uniqueKeys: false,
      version: '1.2',
    })
  } catch {
    tree.children.splice(0, 1, { type: 'code', lang: 'yaml', value: source })
    return null
  }

  if (data === null || data === undefined) {
    tree.children.shift()
    return null
  }

  if (!isMapping(data)) {
    const fragment = fromMarkdown(
      `---\n${source}\n---\n`,
      markdownParseOptions(false),
    )
    tree.children.splice(0, 1, ...fragment.children)
    return null
  }

  tree.children.shift()
  return data
}

function isMapping(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false
  if (value instanceof Date) return false
  const proto = Object.getPrototypeOf(value)
  return proto === Object.prototype || proto === null
}

/**
 * @param {Record<string, unknown>} data
 * @param {WeakSet<object>} seen
 */
function frontmatterTable(data, seen) {
  if (!isMapping(data) || seen.has(data)) return null
  seen.add(data)
  const entries = Object.entries(data)
  if (entries.length === 0) return null
  return {
    type: 'element',
    tagName: 'table',
    properties: {},
    children: [{
      type: 'element',
      tagName: 'tbody',
      properties: {},
      children: entries.map(([key, value]) => ({
        type: 'element',
        tagName: 'tr',
        properties: {},
        children: [
          {
            type: 'element',
            tagName: 'th',
            properties: {},
            children: [{ type: 'text', value: String(key) }],
          },
          {
            type: 'element',
            tagName: 'td',
            properties: {},
            children: valueChildren(value, seen),
          },
        ],
      })),
    }],
  }
}

function valueChildren(value, seen) {
  if (value === null || value === undefined) return [{ type: 'text', value: '' }]
  const kind = typeof value
  if (kind === 'string' || kind === 'number' || kind === 'boolean' || kind === 'bigint') {
    return textWithBreaks(value)
  }
  if (value instanceof Date) return [{ type: 'text', value: value.toISOString() }]
  if (typeof value !== 'object') return [{ type: 'text', value: '' }]
  if (seen.has(value)) return [{ type: 'text', value: '' }]

  if (isMapping(value)) {
    const nested = frontmatterTable(value, seen)
    return nested ? [nested] : [{ type: 'text', value: '' }]
  }

  seen.add(value)
  if (Array.isArray(value) && value.every(item => (
    item === null || item === undefined ||
    ['string', 'number', 'boolean', 'bigint'].includes(typeof item)
  ))) {
    return textWithBreaks(value.map(item => (item == null ? '' : String(item))).join(', '))
  }
  try {
    return [{ type: 'text', value: JSON.stringify(value) }]
  } catch {
    return [{ type: 'text', value: '' }]
  }
}

function textWithBreaks(value) {
  const text = String(value)
  const lines = text.split(/\r?\n/)
  if (lines.length === 1) return [{ type: 'text', value: text }]
  /** @type {Array<import('hast').ElementContent>} */
  const children = []
  for (let i = 0; i < lines.length; i++) {
    if (i > 0) children.push({ type: 'element', tagName: 'br', properties: {}, children: [] })
    if (lines[i]) children.push({ type: 'text', value: lines[i] })
  }
  return children.length ? children : [{ type: 'text', value: '' }]
}

/** If the HTML parser throws, keep the source as escaped text instead of raw markup. */
function rawToText(node) {
  if (!node || !node.children) return
  node.children = node.children.flatMap(child => {
    if (child && child.type === 'raw') return [{ type: 'text', value: child.value || '' }]
    rawToText(child)
    return [child]
  })
}

function addHeadingIds(node) {
  const seen = new Map()
  const ids = new Set()
  visitElements(node, element => {
    if (!/^h[1-6]$/.test(element.tagName)) return
    const base = slugify(elementText(element)) || 'section'
    const n = seen.get(base) || 0
    seen.set(base, n + 1)
    const slug = n === 0 ? base : `${base}-${n}`
    element.properties = element.properties || {}
    element.properties.id = ID_PREFIX + slug
    ids.add(slug)
  })
  return ids
}

function rewriteResources(node, ctx) {
  visitElements(node, element => {
    const props = element.properties || (element.properties = {})
    if (typeof props.id === 'string' && props.id !== '' && !props.id.startsWith(ID_PREFIX)) {
      props.id = ID_PREFIX + props.id
    }
    if (typeof props.name === 'string' && props.name !== '' && !props.name.startsWith(ID_PREFIX)) {
      props.name = ID_PREFIX + props.name
    }

    if (element.tagName === 'a' && props.href != null) {
      const resolved = resolveLink(String(props.href), ctx)
      if (!resolved) {
        delete props.href
        return
      }
      props.href = resolved.href
      if (resolved.kind === 'external') {
        props.target = '_blank'
        props.rel = ['nofollow', 'noopener', 'noreferrer']
      }
    }

    if (element.tagName === 'img' && props.src != null) {
      const src = resolveImage(String(props.src), ctx)
      if (!src) {
        element.tagName = 'span'
        element.children = [{ type: 'text', value: String(props.alt || '') }]
        element.properties = {}
        return
      }
      props.src = src
    }
  })
}

/**
 * @param {string} href
 * @param {{ sourceBase: string, filePath: string, headingIds: Set<string> }} ctx
 */
function resolveLink(href, ctx) {
  const trimmed = href.trim()
  if (trimmed === '') return null
  if (trimmed.startsWith('#')) {
    const frag = slugify(decodeFragment(trimmed.slice(1)))
    if (!frag) return { kind: 'fragment', href: '#' }
    return { kind: 'fragment', href: `#${ID_PREFIX}${frag}` }
  }

  const cleaned = stripControls(trimmed)
  let url
  try {
    url = new URL(cleaned, directoryBase(ctx.filePath))
  } catch {
    return null
  }

  if (url.origin === 'https://elixir.invalid') {
    const path = safePathname(url.pathname)
    if (path == null) return null
    return {
      kind: 'internal',
      href: `${ctx.sourceBase}${path}${url.search}${url.hash}`,
    }
  }

  if (!ABSOLUTE_PROTOCOLS.has(url.protocol)) return null
  if (url.protocol === 'mailto:') return { kind: 'mailto', href: url.href }
  return { kind: 'external', href: url.href }
}

function resolveImage(src, ctx) {
  const resolved = resolveLink(src, ctx)
  if (!resolved) return null
  if (resolved.kind === 'internal') {
    const hashAt = resolved.href.indexOf('#')
    const before = hashAt === -1 ? resolved.href : resolved.href.slice(0, hashAt)
    const hash = hashAt === -1 ? '' : resolved.href.slice(hashAt)
    const joiner = before.includes('?') ? '&' : '?'
    return `${before}${joiner}raw${hash}`
  }
  if (resolved.kind !== 'external') return null
  try {
    const url = new URL(resolved.href)
    if (!IMAGE_PROTOCOLS.has(url.protocol)) return null
    return url.href
  } catch {
    return null
  }
}

function directoryBase(filePath) {
  const path = filePath.startsWith('/') ? filePath : `/${filePath}`
  const slash = path.lastIndexOf('/')
  const dir = slash <= 0 ? '/' : path.slice(0, slash + 1)
  return `https://elixir.invalid${dir}`
}

function safePathname(pathname) {
  if (typeof pathname !== 'string' || !pathname.startsWith('/')) return null
  if (pathname.includes('\\') || pathname.includes('\0')) return null
  return pathname
}

function stripControls(value) {
  return value.replace(/[\u0000-\u0020]/g, '')
}

function stripTrailingSlash(value) {
  return value.length > 1 && value.endsWith('/') ? value.slice(0, -1) : value
}

function decodeFragment(value) {
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

function slugify(text) {
  return String(text)
    .toLowerCase()
    .replace(/[!"#$%&'()*+,./:;<=>?@[\\\]^_`{|}~]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
}

function elementText(node) {
  if (!node) return ''
  if (node.type === 'text') return node.value || ''
  if (node.type === 'element') return (node.children || []).map(elementText).join('')
  return ''
}

function visitElements(node, fn) {
  if (!node || typeof node !== 'object') return
  if (node.type === 'element') fn(node)
  const children = node.children
  if (!children) return
  for (let i = 0; i < children.length; i++) visitElements(children[i], fn)
}

let cachedSchema

function previewSchema() {
  if (cachedSchema) return cachedSchema
  const attributes = { ...defaultSchema.attributes }
  const star = attributes['*'] ? [...attributes['*']] : []
  if (!star.includes('id')) star.push('id')
  if (!star.includes('className')) star.push('className')
  attributes['*'] = star

  const extend = (tag, names) => {
    const current = attributes[tag] ? [...attributes[tag]] : []
    for (const name of names) {
      if (!current.includes(name)) current.push(name)
    }
    attributes[tag] = current
  }
  extend('a', ['target', 'rel'])
  extend('input', ['type', 'checked', 'disabled'])
  extend('th', ['align'])
  extend('td', ['align'])
  extend('ol', ['start'])
  extend('code', ['className'])
  extend('span', ['className'])
  extend('div', ['className'])
  extend('li', ['className'])
  extend('ul', ['className'])
  extend('pre', ['className'])

  const tagNames = defaultSchema.tagNames.includes('input')
    ? defaultSchema.tagNames
    : [...defaultSchema.tagNames, 'input']

  const strip = [...(defaultSchema.strip || [])]
  if (!strip.includes('style')) strip.push('style')

  cachedSchema = {
    ...defaultSchema,
    tagNames,
    attributes,
    strip,
    // Ids are already prefixed with md-. An extra prefix would break in-page links.
    clobberPrefix: '',
    protocols: {
      ...defaultSchema.protocols,
      href: ['http', 'https', 'mailto'],
      src: ['http', 'https'],
    },
  }
  return cachedSchema
}
