// The server's settings, read from the environment when a request needs them and never at build.
//
// In development a missing value falls back to the local backend and to secrets that only work
// against `make dev`. In production nothing falls back: a missing secret is an error, and so is
// one of the development values, so no default secret can ever ship.

export type Env = Record<string, string | undefined>;

export type SettingName = "BACKEND_URL" | "PROXY_SECRET" | "SESSION_SECRET" | "ADMIN_PASSPHRASE";

export const DEV_DEFAULTS: Readonly<Record<SettingName, string>> = {
  BACKEND_URL: "http://127.0.0.1:8000",
  PROXY_SECRET: "dev-only-proxy-secret",
  SESSION_SECRET: "dev-only-session-secret",
  ADMIN_PASSPHRASE: "dev-only-passphrase",
};

const SECRETS: readonly SettingName[] = ["PROXY_SECRET", "SESSION_SECRET", "ADMIN_PASSPHRASE"];

export class ConfigError extends Error {
  constructor(
    public readonly setting: SettingName,
    why: string,
  ) {
    super(`${setting} ${why}`);
    this.name = "ConfigError";
  }
}

export function isProduction(env: Env): boolean {
  return env.NODE_ENV === "production";
}

/** One setting, or `ConfigError`. Only outside production is there a default. */
export function setting(name: SettingName, env: Env = process.env): string {
  const given = (env[name] ?? "").trim();
  if (!isProduction(env)) {
    return given || DEV_DEFAULTS[name];
  }
  if (!given) {
    throw new ConfigError(name, "is not set");
  }
  if (SECRETS.includes(name) && given === DEV_DEFAULTS[name]) {
    throw new ConfigError(name, "is the development value");
  }
  return given;
}

export interface BackendConfig {
  url: string;
  proxySecret: string;
}

export function backendConfig(env: Env = process.env): BackendConfig {
  return {
    url: setting("BACKEND_URL", env).replace(/\/+$/, ""),
    proxySecret: setting("PROXY_SECRET", env),
  };
}

/** The session secret, or null when it cannot be had: then no cookie is trusted or made. */
export function sessionSecretOrNull(env: Env = process.env): string | null {
  try {
    return setting("SESSION_SECRET", env);
  } catch {
    return null;
  }
}

/** The repository's address for the "Source" links. Not a secret; left out when unset. */
export function repositoryUrl(env: Env = process.env): string | null {
  const given = (env.REPO_URL ?? "").trim();
  return /^https:\/\/[^\s]+$/.test(given) ? given : null;
}
