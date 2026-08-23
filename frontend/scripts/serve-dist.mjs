/**
 * Serve the production bundle the way nginx.conf does, so the built artefact
 * can be exercised without Docker.
 *
 *   npm run build && node scripts/serve-dist.mjs [port]
 *
 * This mirrors nginx.conf: static files, an SPA fallback to index.html, and a
 * proxy for /api, /config and /health. It is a check on the *bundle*, not a
 * substitute for building the image — nginx itself is still unverified.
 */
import { createServer } from 'node:http'
import { createReadStream, existsSync, statSync } from 'node:fs'
import { extname, join, normalize } from 'node:path'
import { fileURLToPath } from 'node:url'
import { dirname } from 'node:path'

const PORT = Number(process.argv[2] ?? 4173)
const API = process.env.API_URL ?? 'http://localhost:8000'
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', 'dist')

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.woff2': 'font/woff2',
  '.json': 'application/json',
}

if (!existsSync(ROOT)) {
  console.error(`No build at ${ROOT}. Run \`npm run build\` first.`)
  process.exit(1)
}

const server = createServer(async (request, response) => {
  const url = new URL(request.url ?? '/', `http://localhost:${PORT}`)

  // Same three prefixes nginx.conf forwards.
  if (/^\/(api|config|health)\//.test(url.pathname)) {
    try {
      const upstream = await fetch(API + url.pathname + url.search, {
        method: request.method,
        headers: { ...request.headers, host: new URL(API).host },
        body: ['GET', 'HEAD'].includes(request.method ?? 'GET') ? undefined : request,
        duplex: 'half',
      })
      response.writeHead(upstream.status, {
        'content-type': upstream.headers.get('content-type') ?? 'application/json',
      })
      response.end(Buffer.from(await upstream.arrayBuffer()))
    } catch (error) {
      response.writeHead(502, { 'content-type': 'application/json' })
      response.end(JSON.stringify({ error: { code: 'BAD_GATEWAY', message: String(error) } }))
    }
    return
  }

  // Static file, else the SPA fallback — nginx's `try_files $uri $uri/ /index.html`.
  const requested = join(ROOT, normalize(url.pathname).replace(/^(\.\.[/\\])+/, ''))
  const file =
    existsSync(requested) && statSync(requested).isFile() ? requested : join(ROOT, 'index.html')

  response.writeHead(200, {
    'content-type': TYPES[extname(file)] ?? 'application/octet-stream',
  })
  createReadStream(file).pipe(response)
})

server.listen(PORT, () => console.log(`dist served on http://localhost:${PORT} (api → ${API})`))
