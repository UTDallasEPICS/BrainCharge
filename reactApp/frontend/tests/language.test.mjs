import assert from "node:assert/strict";
import { before, after, test } from "node:test";
import { readFile } from "node:fs/promises";
import { createServer } from "vite";

let server;
let readLanguage;
let translate;
const originalStorage = globalThis.localStorage;

before(async () => {
  server = await createServer({ configFile: false, optimizeDeps: { noDiscovery: true, include: [] }, server: { middlewareMode: true, hmr: false }, appType: "custom" });
  ({ readLanguage, translate } = await server.ssrLoadModule("/src/i18n/language.js"));
});

after(async () => {
  if (originalStorage === undefined) delete globalThis.localStorage;
  else globalThis.localStorage = originalStorage;
  await server?.close();
});

test("all four language choices are restored from saved settings", () => {
  for (const language of ["en", "fr", "es", "de"]) {
    globalThis.localStorage = { getItem: () => JSON.stringify({ language }) };
    assert.equal(readLanguage(), language);
  }
});

test("missing, malformed, and unsupported preferences fall back to English", () => {
  for (const saved of [null, "{", "null", "{}", '{"language":"unknown"}', '{"language":"__proto__"}']) {
    globalThis.localStorage = { getItem: () => saved };
    assert.equal(readLanguage(), "en");
  }
  globalThis.localStorage = { getItem: () => { throw new Error("Storage unavailable"); } };
  assert.equal(readLanguage(), "en");
});

test("settings labels translate in each language with safe English fallback", () => {
  assert.equal(translate("en", "Settings"), "Settings");
  assert.equal(translate("fr", "Settings"), "Paramètres");
  assert.equal(translate("es", "Settings"), "Ajustes");
  assert.equal(translate("de", "Settings"), "Einstellungen");
  assert.equal(translate("unknown", "Settings"), "Settings");
  for (const language of ["fr", "es", "de"]) {
    assert.equal(translate(language, "Untranslated text"), "Untranslated text");
    assert.equal(translate(language, "toString"), "toString");
  }
});

test("interpolation preserves variable values in translated messages", () => {
  assert.equal(translate("es", "+ {count} more", { count: 3 }), "+ 3 más");
  assert.equal(translate("de", "+ {count} more", { count: 0 }), "+ 0 weitere");
  assert.equal(translate("fr", "+ {count} more", { count: 2 }), "+ 2 autres");
  assert.equal(translate("en", "+ {count} more", { count: 5 }), "+ 5 more");
});

test("every supported dictionary has the same keys and interpolation placeholders", async () => {
  const dictionaries = await Promise.all(["fr", "es", "de"].map(async language => JSON.parse(await readFile(new URL("../src/i18n/" + language + ".json", import.meta.url), "utf8"))));
  const expectedKeys = Object.keys(dictionaries[0]).sort();
  const placeholders = text => [...text.matchAll(/\{(\w+)\}/g)].map(match => match[1]).sort();
  for (const dictionary of dictionaries) {
    assert.deepEqual(Object.keys(dictionary).sort(), expectedKeys);
    for (const key of expectedKeys) {
      assert.equal(typeof dictionary[key], "string");
      assert.ok(dictionary[key].trim(), key);
      assert.deepEqual(placeholders(dictionary[key]), placeholders(key), key);
    }
  }
});
