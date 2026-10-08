import { SignJWT, jwtVerify } from "jose";
import bcrypt from "bcryptjs";
import { cookies } from "next/headers";

const COOKIE = "promptathlon_session";
const SESSION_TTL_SECONDS = 8 * 60 * 60;

function getAuthSecret(): Uint8Array {
  const value = process.env.AUTH_SECRET;
  if (!value || value.length < 32) {
    throw new Error("AUTH_SECRET must be configured with at least 32 characters.");
  }
  return new TextEncoder().encode(value);
}

export async function createSession(email: string) {
  const token = await new SignJWT({ email, role: "ADMIN" })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("8h")
    .sign(getAuthSecret());

  (await cookies()).set(COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_TTL_SECONDS,
  });
}

export async function getSession() {
  const token = (await cookies()).get(COOKIE)?.value;
  if (!token) return null;

  try {
    const { payload } = await jwtVerify(token, getAuthSecret());
    if (payload.role !== "ADMIN" || typeof payload.email !== "string") return null;
    return payload;
  } catch {
    return null;
  }
}

export async function isAdminAuthenticated() {
  const session = await getSession();
  return session?.role === "ADMIN" && typeof session.email === "string";
}

export const verifyPassword = (password: string, hash: string) =>
  bcrypt.compare(password, hash);
export const hashPassword = (password: string) => bcrypt.hash(password, 12);
