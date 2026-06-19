import GoogleProvider from 'next-auth/providers/google';
import type { NextAuthOptions } from 'next-auth';

function env(name: string): string | undefined {
  const value = process.env[name]?.trim();
  return value ? value : undefined;
}

function ownerEmail(): string | undefined {
  return env('SCREENER_OWNER_EMAIL')?.toLowerCase();
}

export function isOwnerEmail(email: string | null | undefined): boolean {
  const owner = ownerEmail();
  return Boolean(owner && email && email.toLowerCase() === owner);
}

function requiredAuthEnvPresent(): boolean {
  return Boolean(
    env('AUTH_GOOGLE_ID') &&
      env('AUTH_GOOGLE_SECRET') &&
      env('AUTH_SECRET') &&
      ownerEmail(),
  );
}

export const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: env('AUTH_GOOGLE_ID') ?? '__missing_google_client_id__',
      clientSecret: env('AUTH_GOOGLE_SECRET') ?? '__missing_google_client_secret__',
    }),
  ],
  session: {
    strategy: 'jwt',
  },
  callbacks: {
    async signIn({ profile }) {
      if (!requiredAuthEnvPresent()) {
        return false;
      }
      const googleProfile = profile as
        | { email?: string | null; email_verified?: boolean | null }
        | undefined;
      return Boolean(
        googleProfile?.email_verified === true && isOwnerEmail(googleProfile.email),
      );
    },
  },
};
