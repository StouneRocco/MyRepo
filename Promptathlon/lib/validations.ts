import { z } from "zod";

const optionalUrl = z.union([z.url().max(2048), z.literal("")]).optional();

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
  pressCardUrl: optionalUrl,
  needsBib: z.boolean().default(false),
  portfolioUrl: optionalUrl,
});
