import { z } from "zod";

const safeHttpUrl = z.url().max(2048).refine((value) => /^https?:\\/\\//i.test(value), "Seules les URL HTTP(S) sont autorisées.");
const optionalUrl = z.union([safeHttpUrl, z.literal("")]).optional();
const pressCardKey = z.union([
  z.string().regex(/^press-cards\/[0-9a-f-]{36}$/),
  z.literal(""),
]).optional();

export const matchSchema = z.object({
  sport: z.enum(["BASKETBALL", "HANDBALL"]),
  homeTeam: z.string().trim().min(2).max(120),
  awayTeam: z.string().trim().min(2).max(120),
  matchDateTime: z.coerce.date(),
  venue: z.string().trim().min(2).max(200),
  description: z.string().trim().max(2000).optional(),
  status: z.enum(["UPCOMING", "FINISHED", "CANCELLED"]).default("UPCOMING"),
  accreditationDeadline: z.coerce.date().optional(),
});

export const accreditationSchema = z.object({
  matchId: z.string().regex(/^[a-f\d]{24}$/i, "Identifiant de match invalide."),
  profileType: z.enum(["JOURNALIST", "PHOTOGRAPHER", "VIDEOGRAPHER"]),
  firstName: z.string().trim().min(2).max(100),
  lastName: z.string().trim().min(2).max(100),
  email: z.email().trim().toLowerCase().max(254),
  pressCardKey,
  needsBib: z.boolean().default(false),
  portfolioUrl: optionalUrl,
}).superRefine((value, context) => {
  if (value.profileType === "JOURNALIST" && !value.pressCardKey) {
    context.addIssue({ code: "custom", path: ["pressCardKey"], message: "La carte de presse est obligatoire pour les journalistes." });
  }
});
