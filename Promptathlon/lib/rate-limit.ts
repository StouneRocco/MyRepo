import { createHash } from "node:crypto";
import { connectDB } from "@/lib/mongodb";
import { RateLimit } from "@/models/RateLimit";

export async function enforceRateLimit(
  request: Request,
  scope: string,
  limit: number,
  windowMs: number,
): Promise<{ allowed: boolean; retryAfterSeconds: number }> {
  await connectDB();
  const forwarded = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  const address = forwarded || request.headers.get("x-real-ip") || "unknown";
  const key = createHash("sha256").update(`${scope}:${address}`).digest("hex");
  const now = new Date();
  const cutoff = new Date(now.getTime() - windowMs);
  const expiresAt = new Date(now.getTime() + windowMs);

  let record = await RateLimit.findOneAndUpdate(
    { key, windowStartedAt: { $gt: cutoff } },
    { $inc: { count: 1 }, $set: { expiresAt } },
    { new: true },
  ).exec();

  if (!record) {
    try {
      record = await RateLimit.findOneAndUpdate(
        { key },
        { $set: { count: 1, windowStartedAt: now, expiresAt } },
        { new: true, upsert: true, setDefaultsOnInsert: true },
      ).exec();
    } catch (error) {
      const duplicate = typeof error === "object" && error !== null && "code" in error && error.code === 11000;
      if (!duplicate) throw error;
      record = await RateLimit.findOneAndUpdate(
        { key, windowStartedAt: { $gt: cutoff } },
        { $inc: { count: 1 }, $set: { expiresAt } },
        { new: true },
      ).exec();
      if (!record) throw error;
    }
  }

  const resetAt = new Date(record.windowStartedAt).getTime() + windowMs;
  return {
    allowed: record.count <= limit,
    retryAfterSeconds: Math.max(1, Math.ceil((resetAt - now.getTime()) / 1000)),
  };
}
