import { NextResponse } from "next/server";
import { MAX_PRESS_CARD_BYTES, storePressCard } from "@/lib/private-storage";

export const runtime = "nodejs";

export async function POST(request: Request) {
  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return NextResponse.json({ message: "Fichier manquant ou formulaire invalide." }, { status: 400 });
  }
  const file = form.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ message: "Sélectionnez une carte de presse au format PDF." }, { status: 400 });
  }
  if (file.type !== "application/pdf" || file.size <= 0 || file.size > MAX_PRESS_CARD_BYTES) {
    return NextResponse.json({ message: "Le document doit être un PDF de 5 Mo maximum." }, { status: 400 });
  }
  try {
    const bytes = Buffer.from(await file.arrayBuffer());
    if (bytes.subarray(0, 5).toString("ascii") !== "%PDF-") {
      return NextResponse.json({ message: "Le fichier sélectionné ne semble pas être un véritable PDF." }, { status: 400 });
    }
    const key = await storePressCard(bytes);
    return NextResponse.json({ key, message: "Carte de presse téléversée de façon privée." }, { status: 201, headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ message: "Le stockage privé est indisponible ou n'est pas configuré." }, { status: 503 });
  }
}
