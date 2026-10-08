import { NextResponse } from "next/server";
import { connectDB } from "@/lib/mongodb";
import { isAdminAuthenticated } from "@/lib/auth";
import { Match } from "@/models/Match";
import { matchSchema } from "@/lib/validations";

export async function GET() {
  if (!(await isAdminAuthenticated())) {
    return NextResponse.json({ message: "Authentification requise." }, { status: 401 });
  }

  try {
    await connectDB();
    const matches = await Match.find().sort({ matchDateTime: 1 }).lean();
    return NextResponse.json({ matches });
  } catch {
    return NextResponse.json({ message: "Impossible de charger les matchs." }, { status: 500 });
  }
}

export async function POST(req: Request) {
  if (!(await isAdminAuthenticated())) {
    return NextResponse.json({ message: "Authentification requise." }, { status: 401 });
  }

  try {
    const parsed = matchSchema.safeParse(await req.json());
    if (!parsed.success) {
      return NextResponse.json({ message: "Données de match invalides." }, { status: 400 });
    }

    const body = parsed.data;
    await connectDB();
    const accreditationDeadline =
      body.accreditationDeadline ?? new Date(body.matchDateTime.getTime() - 24 * 60 * 60 * 1000);
    const match = await Match.create({ ...body, accreditationDeadline });
    return NextResponse.json({ match }, { status: 201 });
  } catch {
    return NextResponse.json({ message: "Impossible de créer le match." }, { status: 500 });
  }
}
