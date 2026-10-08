import { NextResponse } from "next/server";
import { z } from "zod";
import { createPressCardUpload } from "@/lib/private-storage";

const uploadSchema = z.object({ contentType: z.literal("application/pdf") });

export async function POST(request: Request) {
  const parsed = uploadSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ message: "Seuls les fichiers PDF sont acceptés." }, { status: 400 });
  }
  try {
    const upload = await createPressCardUpload();
    return NextResponse.json(upload, { status: 201, headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ message: "Le téléversement des documents n'est pas configuré. Contactez l'administration." }, { status: 503 });
  }
}
