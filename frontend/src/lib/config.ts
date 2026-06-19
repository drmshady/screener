const TRUTHY = new Set(["1", "true", "yes", "on"]);

function env(name: string): string | undefined {
  const value = process.env[name]?.trim();
  return value ? value : undefined;
}

export function hostedMode(): boolean {
  return TRUTHY.has((process.env.SCREENER_HOSTED_MODE ?? "0").trim().toLowerCase());
}

export function backendBaseUrl(): string {
  const value = env("BACKEND_BASE_URL");
  if (!value && hostedMode()) {
    throw new Error("BACKEND_BASE_URL is required when hosted mode is enabled.");
  }
  return value ?? "http://localhost:8000";
}

export function ownerSecret(): string {
  const value = env("SCREENER_OWNER_SECRET");
  if (!value && hostedMode()) {
    throw new Error("SCREENER_OWNER_SECRET is required when hosted mode is enabled.");
  }
  return value ?? "";
}
