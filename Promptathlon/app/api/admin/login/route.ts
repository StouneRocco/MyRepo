import { NextResponse } from "next/server";
import { z } from "zod";
import { connectDB } from "@/lib/mongodb";
import { Admin } from "@/models/Admin";
import { createSession, verifyPassword } from "@/lib/auth";
import { enforceRateLimit } from "@/lib/rate-limit";

const loginSchema = z.object({
  email: z.email().max(254),
  password: z.string().min(1).max(200),
});

export async function POST(req: Request) {
  try {
    const rate = await enforceRateLimit(req, "admin-login", 10, 15 * 60 * 1000);
    if (!rate.allowed) return NextResponse.json({ message: "Trop de tentatives. Réessayez plus tard." }, { status: 429, headers: { "Retry-After": String(rate.retryAfterSeconds) } });
    const parsed = loginSchema.safeParse(await req.json());
    if (!parsed.success) {
      return NextResponse.json({ message: "Identifiants invalides." }, { status: 400 });
    }

    await connectDB();
    const email = parsed.data.email.trim().toLowerCase();
    const admin = await Admin.findOne({ email });
    if (!admin || !(await verifyPassword(parsed.data.password, admin.passwordHash))) {
      return NextResponse.json({ message: "Identifiants invalides." }, { status: 401 });
    }

    await createSession(admin.email);
    return NextResponse.json({ ok: true });
  } catch {
    return NextResponse.json({ message: "Connexion momentanément indisponible." }, { status: 500 });
  }
}
