import mongoose from "mongoose";
import { NextResponse } from "next/server";
import { isAdminAuthenticated } from "@/lib/auth";
import { connectDB } from "@/lib/mongodb";
import { AccreditationRequest } from "@/models/AccreditationRequest";
import { createPressCardDownloadUrl } from "@/lib/private-storage";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  if (!(await isAdminAuthenticated())) {
    return NextResponse.json({ message: "Authentification requise." }, { status: 401 });
  }
  const { id } = await params;
  if (!mongoose.isValidObjectId(id)) {
    return NextResponse.json({ message: "Demande invalide." }, { status: 400 });
  }
  try {
    await connectDB();
    const request = await AccreditationRequest.findById(id).select("pressCardKey").lean();
    if (!request?.pressCardKey) {
      return NextResponse.json({ message: "Aucune carte de presse n'est associée à cette demande." }, { status: 404 });
    }
    const url = await createPressCardDownloadUrl(request.pressCardKey);
    return NextResponse.redirect(url, { headers: { "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" } });
  } catch {
    return NextResponse.json({ message: "Le document est indisponible. Vérifiez la configuration du stockage privé." }, { status: 503 });
  }
}
