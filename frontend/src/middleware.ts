import { withAuth, type NextRequestWithAuth } from 'next-auth/middleware';
import { NextResponse, type NextFetchEvent, type NextRequest } from 'next/server';

const TRUTHY = new Set(['1', 'true', 'yes', 'on']);

function hostedMode(): boolean {
  return TRUTHY.has((process.env.SCREENER_HOSTED_MODE ?? '0').trim().toLowerCase());
}

function isOwner(email: string | null | undefined): boolean {
  const owner = process.env.SCREENER_OWNER_EMAIL?.trim().toLowerCase();
  return Boolean(owner && email && email.toLowerCase() === owner);
}

const authMiddleware = withAuth({
  callbacks: {
    authorized({ token }) {
      return isOwner(token?.email);
    },
  },
});

export default function middleware(request: NextRequest, event: NextFetchEvent) {
  if (!hostedMode()) {
    return NextResponse.next();
  }
  return authMiddleware(request as NextRequestWithAuth, event);
}

export const config = {
  matcher: [
    '/((?!api/auth|_next/static|_next/image|favicon.ico|robots.txt|sitemap.xml).*)',
  ],
};
