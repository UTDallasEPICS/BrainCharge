import { createAuthClient } from "better-auth/react";

const baseURL =
  import.meta.env.VITE_AUTH_URL ||
  (typeof window !== "undefined" ? window.location.origin : "http://localhost:5173");

export const authClient = createAuthClient({
  baseURL,
  fetchOptions: {
    credentials: "include",
  },
});

export const { signIn, signUp, signOut, useSession, getSession } = authClient;
