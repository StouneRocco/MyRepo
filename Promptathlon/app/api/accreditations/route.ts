import { NextResponse } from "next/server";
import { connectDB } from "@/lib/mongodb";
import { Match } from "@/models/Match";
import { AccreditationRequest } from "@/models/AccreditationRequest";
import { accreditationSchema } from "@/lib/validations";

export async function POST(req: Request) {
  const parsed = accreditationSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ message: "Vérifiez les informations saisies." }, { status: 400 });
  }

  try {
    const body = parsed.data;
    await connectDB();
    const match = await Match.findById(body.matchId);
    if (!match) return NextResponse.json({ message: "Match introuvable." }, { status: 404 });

    const now = new Date();
    if (match.status !== "UPCOMING" || match.matchDateTime <= now || match.accreditationDeadline <= now) {
      return NextResponse.json({ message: "Les inscriptions sont closes 24 heures avant le match." }, { status: 400 });
    }

    const request = await AccreditationRequest.create({
      ...body,
      pressCardUrl: body.profileType === "JOURNALIST" ? body.pressCardUrl || undefined : undefined,
      portfolioUrl: body.profileType !== "JOURNALIST" ? body.portfolioUrl || undefined : undefined,
      needsBib: body.profileType === "JOURNALIST" ? body.needsBib : false,
      sport: match.sport,
      email: body.email.trim().toLowerCase(),
    });
    return NextResponse.json({ requestId: request._id, message: "Demande envoyée avec succès. Elle reste en attente de décision." }, { status: 201 });
  } catch (error) {
    if (typeof error === "object" && error !== null && "code" in error && error.code === 11000) {
      return NextResponse.json({ message: "Une demande existe déjà pour ce match et ce profil avec cette adresse email." }, { status: 409 });
    }
    return NextResponse.json({ message: "Le service est momentanément indisponible." }, { status: 500 });
  }
}
