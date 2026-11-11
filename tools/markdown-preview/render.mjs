/**
 * Render Markdown to HTML for the Elixir file view.
 *
 * The parse is the same grammar deepseek-harness uses for its UI
 * (packages/client/ui-primitives/src/markdown/parse.ts at tag dsh-v0.2.2-rc.1):
 * mdast-util-from-markdown + micromark-extension-gfm + mdast-util-gfm, with
 * GFM `singleTilde: false` so `10~20` stays literal. DSH then walks the mdast
 * in React. Elixir is a Python app, so this compiles that same tree to HTML
 * (mdast-util-to-hast) and sanitizes it. Math, mermaid, and DSH-only syntax
 * extensions (CJK emphasis, Windows paths) are not part of this preview.
 */

import { fromMarkdown } from 'mdast-util-from-markdown'
import { gfmFromMarkdown } from 'mdast-util-gfm'
import { gfm } from 'micromark-extension-gfm'
import { toHast } from 'mdast-util-to-hast'
import { toHtml } from 'hast-util-to-html'
import { defaultSchema, sanitize } from 'hast-util-sanitize'

/** Same option DSH passes to micromark-extension-gfm. */
const gfmOptions = { singleTilde: false }

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
  const text = typeof markdown === 'string' ? markdown : String(markdown ?? '')

  const tree = fromMarkdown(text, {
    extensions: [gfm(gfmOptions)],
    mdastExtensions: [gfmFromMarkdown()],
  })
  literalizeHtml(tree)

  const hast = toHast(tree, { allowDangerousHtml: false })
  if (!hast) return ''

  const headingIds = addHeadingIds(hast)
  rewriteResources(hast, { sourceBase, filePath, headingIds })

  const clean = sanitize(hast, previewSchema())
  return toHtml(clean)
}

/**
 * DSH renders raw HTML nodes as literal text (they never enter the DOM as
 * markup). HTML comments are author notes, not document text, so they are
 * dropped. Everything else is kept as escaped text.
 * @param {import('mdast').Root | import('mdast').Content} node
 */
function literalizeHtml(node) {
  if (!node || !node.children) return
  node.children = node.children.flatMap(child => {
    if (child.type === 'html') {
      const value = child.value || ''
      if (/^\s*<!--[\s\S]*-->\s*$/.test(value)) return []
      return [{ type: 'text', value }]
    }
    literalizeHtml(child)
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

  cachedSchema = {
    ...defaultSchema,
    tagNames,
    attributes,
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
