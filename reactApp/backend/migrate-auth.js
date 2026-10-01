import "dotenv/config";
import { getMigrations } from "better-auth/db/migration";
import { pathToFileURL } from "url";
import { auth } from "./auth.js";

export async function ensureAuthDatabase() {
  const { toBeCreated, toBeAdded, runMigrations } = await getMigrations(auth.options);

  if (toBeCreated.length === 0 && toBeAdded.length === 0) {
    return;
  }

  console.log("Running Better Auth database migrations...");
  await runMigrations();
  console.log("Better Auth database ready.");
}

const isDirectRun = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;

if (isDirectRun) {
  await ensureAuthDatabase();
  console.log("Auth migration complete.");
}
