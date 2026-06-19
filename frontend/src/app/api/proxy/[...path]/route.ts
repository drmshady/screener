import { getServerSession } from 'next-auth';
import { NextResponse } from 'next/server';
import { authOptions } from '@/auth';
import { backendBaseUrl, hostedMode, ownerSecret } from '@/lib/config';

const HOP_BY_HOP_HEADERS = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
  'host',
  'content-length',
]);

type ProxyContext = {
  params: Promise<{ path?: string[] }> | { path?: string[] };
};

async function resolvePath(context: ProxyContext): Promise<string[]> {
  const params = await context.params;
  return params.path ?? [];
}

function proxyUrl(request: Request, pathParts: string[]): string {
  const incoming = new URL(request.url);
  const base = backendBaseUrl().replace(/\/+$/, '');
  const path = pathParts.map((part) => encodeURIComponent(part)).join('/');
  return `${base}/${path}${incoming.search}`;
}

function forwardedHeaders(request: Request): Headers {
  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });
  headers.set('Content-Type', 'application/json');
  headers.set('X-Owner-Secret', ownerSecret());
  return headers;
}

async function proxy(request: Request, context: ProxyContext) {
  if (hostedMode()) {
    const session = await getServerSession(authOptions);
    if (!session) {
      return NextResponse.json({ detail: 'Unauthorized' }, { status: 401 });
    }
  }

  const method = request.method.toUpperCase();
  const hasBody = !['GET', 'HEAD'].includes(method);
  const backendResponse = await fetch(proxyUrl(request, await resolvePath(context)), {
    method,
    headers: forwardedHeaders(request),
    body: hasBody ? await request.text() : undefined,
    cache: 'no-store',
  });

  const body = await backendResponse.text();
  return new Response(body, {
    status: backendResponse.status,
    headers: {
      'Content-Type': backendResponse.headers.get('Content-Type') ?? 'application/json',
    },
  });
}

export async function GET(request: Request, context: ProxyContext) {
  return proxy(request, context);
}

export async function POST(request: Request, context: ProxyContext) {
  return proxy(request, context);
}

export async function PUT(request: Request, context: ProxyContext) {
  return proxy(request, context);
}

export async function PATCH(request: Request, context: ProxyContext) {
  return proxy(request, context);
}

export async function DELETE(request: Request, context: ProxyContext) {
  return proxy(request, context);
}
