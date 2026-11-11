import { renderMarkdown } from './render.mjs'

const api = {
  render(markdown, options) {
    return renderMarkdown(markdown, options || {})
  },
}

const root = typeof window !== 'undefined' ? window : globalThis
root.ElixirMarkdown = api
