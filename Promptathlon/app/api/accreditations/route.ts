import { NextResponse } from "next/server";
import { connectDB } from "@/lib/mongodb";
import { Match } from "@/models/Match";
import { AccreditationRequest } from "@/models/AccreditationRequest";
import { accreditationSchema } from "@/lib/validations";
import { verifyPressCardObject } from "@/lib/private-storage";

export async function POST(req: Request) {
  const parsed = accreditationSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ message: "Vérifiez les informations saisies, dont la carte de presse pour les journalistes." }, { status: 400 });
  }

  try {
    const body = parsed.data;
    if (body.profileType === "JOURNALIST") {
      if (!body.pressCardKey || !(await verifyPressCardObject(body.pressCardKey))) {
        return NextResponse.json({ message: "La carte de presse est absente, invalide ou trop volumineuse. Téléversez un PDF de 5 Mo maximum." }, { status: 400 });
      }
    }
    await connectDB();
    const match = await Match.findById(body.matchId);
    if (!match) return NextResponse.json({ message: "Match introuvable." }, { status: 404 });

    const now = new Date();
    if (match.status !== "UPCOMING" || match.matchDateTime <= now || match.accreditationDeadline <= now) {
      return NextResponse.json({ message: "Les inscriptions sont closes 24 heures avant le match." }, { status: 400 });
    }

    const request = await AccreditationRequest.create({
      ...body,
      pressCardKey: body.profileType === "JOURNALIST" ? body.pressCardKey : undefined,
      needsBib: body.profileType === "JOURNALIST" ? body.needsBib : false,
      portfolioUrl: body.profileType !== "JOURNALIST" ? body.portfolioUrl || undefined : undefined,
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
