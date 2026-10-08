import mongoose from "mongoose";

declare global {
  // Reuse a single connection while Next.js reloads modules in development.
  var mongooseCache: { conn: typeof mongoose | null; promise: Promise<typeof mongoose> | null } | undefined;
}

const cached = global.mongooseCache ?? (global.mongooseCache = { conn: null, promise: null });

export async function connectDB() {
  if (cached.conn) return cached.conn;

  const uri = process.env.MONGODB_URI;
  if (!uri) throw new Error("MONGODB_URI is not configured");

  if (!cached.promise) cached.promise = mongoose.connect(uri);
  cached.conn = await cached.promise;
  return cached.conn;
}
