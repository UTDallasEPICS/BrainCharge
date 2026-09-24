import { fromNodeHeaders } from "better-auth/node";
import { auth } from "../auth.js";

export async function requireAuth(req, res, next) {
  try {
    const session = await auth.api.getSession({
      headers: fromNodeHeaders(req.headers),
    });

    if (!session) {
      return res.status(401).json({ error: "Unauthorized", details: "Sign in required" });
    }

    req.user = session.user;
    req.session = session.session;
    return next();
  } catch (error) {
    console.error("Auth check failed:", error.message);
    return res.status(401).json({ error: "Unauthorized", details: "Invalid session" });
  }
}
