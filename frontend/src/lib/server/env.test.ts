import { describe, expect, it } from "vitest";
import {
  ConfigError,
  DEV_DEFAULTS,
  type SettingName,
  backendConfig,
  repositoryUrl,
  sessionSecretOrNull,
  setting,
} from "./env";

const NAMES: SettingName[] = ["BACKEND_URL", "PROXY_SECRET", "SESSION_SECRET", "ADMIN_PASSPHRASE"];
const SECRETS: SettingName[] = ["PROXY_SECRET", "SESSION_SECRET", "ADMIN_PASSPHRASE"];

describe("settings in development", () => {
  it("fall back to the local backend and the dev-only secrets", () => {
    for (const name of NAMES) {
      expect(setting(name, { NODE_ENV: "development" })).toBe(DEV_DEFAULTS[name]);
      expect(setting(name, {})).toBe(DEV_DEFAULTS[name]);
    }
    expect(backendConfig({ NODE_ENV: "development" })).toEqual({
      url: "http://127.0.0.1:8000",
      proxySecret: "dev-only-proxy-secret",
    });
  });

  it("use a value that is set", () => {
    expect(setting("BACKEND_URL", { BACKEND_URL: "http://127.0.0.1:9000/" })).toBe(
      "http://127.0.0.1:9000/",
    );
    expect(backendConfig({ BACKEND_URL: "http://127.0.0.1:9000/" }).url).toBe(
      "http://127.0.0.1:9000",
    );
  });
});

describe("settings in production fail closed", () => {
  const full = {
    NODE_ENV: "production",
    BACKEND_URL: "https://service.example",
    PROXY_SECRET: "a-real-proxy-secret",
    SESSION_SECRET: "a-real-session-secret",
    ADMIN_PASSPHRASE: "a-real-passphrase",
  };

  it("read what is set", () => {
    for (const name of NAMES) {
      expect(setting(name, full)).toBe(full[name]);
    }
  });

  it("never fall back: a missing or empty value is an error", () => {
    for (const name of NAMES) {
      for (const missing of [undefined, "", "   "]) {
        expect(() => setting(name, { ...full, [name]: missing })).toThrow(ConfigError);
      }
    }
    expect(() => backendConfig({ NODE_ENV: "production" })).toThrow(ConfigError);
  });

  it("refuse a development secret, so no default secret can ship", () => {
    for (const name of SECRETS) {
      expect(() => setting(name, { ...full, [name]: DEV_DEFAULTS[name] })).toThrow(
        /development value/,
      );
    }
  });

  it("leave sessions untrusted when the session secret is missing", () => {
    expect(sessionSecretOrNull({ NODE_ENV: "production" })).toBeNull();
    expect(
      sessionSecretOrNull({ ...full, SESSION_SECRET: DEV_DEFAULTS.SESSION_SECRET }),
    ).toBeNull();
    expect(sessionSecretOrNull(full)).toBe("a-real-session-secret");
  });
});

describe("the repository address", () => {
  it("is left out unless it is an https address", () => {
    expect(repositoryUrl({})).toBeNull();
    expect(repositoryUrl({ REPO_URL: "javascript:alert(1)" })).toBeNull();
    expect(repositoryUrl({ REPO_URL: "https://code.example/domain-health" })).toBe(
      "https://code.example/domain-health",
    );
  });
});
