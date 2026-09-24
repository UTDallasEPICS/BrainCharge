import path from "path";
import { fileURLToPath } from "url";
import Database from "better-sqlite3";
import { betterAuth } from "better-auth";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dbPath = path.join(__dirname, "auth.db");

const baseURL = process.env.BETTER_AUTH_URL || "http://localhost:5173";
const clientOrigin = process.env.CLIENT_ORIGIN || "http://localhost:5173";

if (!process.env.BETTER_AUTH_SECRET) {
  console.warn(
    "Warning: BETTER_AUTH_SECRET is not set. Add it to server/.env before production."
  );
}

export const auth = betterAuth({
  baseURL,
  secret: process.env.BETTER_AUTH_SECRET || "dev-only-change-me-use-32-chars-min!!",
  trustedOrigins: [clientOrigin, "http://127.0.0.1:5173", "http://localhost:5173"],
  database: new Database(dbPath),
  emailAndPassword: {
    enabled: true,
    minPasswordLength: 8,
  },
  advanced: {
    useSecureCookies: false,
  },
});
