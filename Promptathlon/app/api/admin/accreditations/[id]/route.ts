import mongoose from "mongoose";
import { NextResponse } from "next/server";
import { z } from "zod";
import { connectDB } from "@/lib/mongodb";
import { isAdminAuthenticated } from "@/lib/auth";
import { AccreditationRequest } from "@/models/AccreditationRequest";
import { Match } from "@/models/Match";
import { sendDecisionEmail } from "@/lib/email";

const decisionSchema = z.object({
  status: z.enum(["ACCEPTED", "REJECTED"]),
});

export async function PUT(req: Request, { params }: { params: Promise<{ id: string }> }) {
  if (!(await isAdminAuthenticated())) {
    return NextResponse.json({ message: "Authentification requise." }, { status: 401 });
  }

  const { id } = await params;
  if (!mongoose.isValidObjectId(id)) {
    return NextResponse.json({ message: "Demande invalide." }, { status: 400 });
  }

  const parsed = decisionSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ message: "Décision invalide." }, { status: 400 });
  }

  try {
    await connectDB();
    const request = await AccreditationRequest.findById(id);
    if (!request) return NextResponse.json({ message: "Demande introuvable." }, { status: 404 });
    if (request.status !== "PENDING") {
      return NextResponse.json({ message: "Cette demande a déjà été traitée." }, { status: 409 });
    }

    const match = await Match.findById(request.matchId).lean();
    if (!match) return NextResponse.json({ message: "Match associé introuvable." }, { status: 404 });

    request.status = parsed.data.status;
    request.processedAt = new Date();
    request.notificationStatus = "SENDING";
    request.notificationError = undefined;
    await request.save();

    try {
      await sendDecisionEmail({
        to: request.email,
        firstName: request.firstName,
        status: parsed.data.status,
        homeTeam: match.homeTeam,
        awayTeam: match.awayTeam,
        matchDateTime: match.matchDateTime,
        venue: match.venue,
      });
      request.notificationStatus = "SENT";
      request.notificationSentAt = new Date();
      request.notificationError = undefined;
      await request.save();
      return NextResponse.json({ message: "Décision enregistrée et email envoyé.", request });
    } catch (error) {
      request.notificationStatus = "FAILED";
      request.notificationError = error instanceof Error ? error.message.slice(0, 500) : "Erreur d’envoi inconnue.";
      await request.save();
      return NextResponse.json({
        message: "Décision enregistrée, mais l’email n’a pas pu être envoyé. Vérifiez la configuration Brevo.",
        request,
      }, { status: 502 });
    }
  } catch {
    return NextResponse.json({ message: "Impossible de traiter la demande." }, { status: 500 });
  }
}
