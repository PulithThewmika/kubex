// Edge function proxy for /api, /auth, /install, /integrations, /mcp.
// vercel.json rewrites those prefixes here with the real upstream path in
// the `p` query param, so the backend hostname lives only in the BACKEND_URL
// env var (set in the Vercel dashboard) and never in committed source.
export const config = { runtime: 'edge' }

export default async function handler(req: Request): Promise<Response> {
  const backend = process.env.BACKEND_URL
  if (!backend) {
    return new Response('Proxy misconfigured: BACKEND_URL is not set', { status: 500 })
  }

  const incoming = new URL(req.url)
  const upstreamPath = incoming.searchParams.get('p')
  if (!upstreamPath) {
    return new Response('Bad request', { status: 400 })
  }
  incoming.searchParams.delete('p')

  const upstreamUrl = new URL(upstreamPath, backend)
  upstreamUrl.search = incoming.search

  const headers = new Headers(req.headers)
  headers.delete('host')
  headers.delete('connection')

  const hasBody = req.method !== 'GET' && req.method !== 'HEAD'
  const upstreamRes = await fetch(upstreamUrl, {
    method: req.method,
    headers,
    body: hasBody ? req.body : undefined,
    // @ts-expect-error required by undici/edge fetch when streaming a body
    duplex: hasBody ? 'half' : undefined,
    // Without this, fetch silently follows a 302 (e.g. /auth/github ->
    // GitHub's OAuth authorize page) itself and hands back GitHub's own
    // response as if it came from our origin -- breaking the OAuth
    // redirect entirely. 'manual' relays the raw 3xx + Location instead.
    redirect: 'manual',
  })

  return new Response(upstreamRes.body, {
    status: upstreamRes.status,
    headers: upstreamRes.headers,
  })
}
