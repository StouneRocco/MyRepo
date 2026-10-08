import { NextResponse } from "next/server";
import { connectDB } from "@/lib/mongodb";
import { isAdminAuthenticated } from "@/lib/auth";
import { AccreditationRequest } from "@/models/AccreditationRequest";

export async function GET() {
  if (!(await isAdminAuthenticated())) {
    return NextResponse.json({ message: "Authentification requise." }, { status: 401 });
  }

  try {
    await connectDB();
    const requests = await AccreditationRequest.find()
      .sort({ createdAt: -1 })
      .limit(500)
      .lean();
    return NextResponse.json({ requests });
  } catch {
    return NextResponse.json({ message: "Impossible de charger les demandes." }, { status: 500 });
  }
}
