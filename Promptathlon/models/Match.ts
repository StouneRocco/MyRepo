import { Schema, model, models } from "mongoose";

const MatchSchema = new Schema(
  {
    sport: {
      type: String,
      enum: ["BASKETBALL", "HANDBALL"],
      required: true,
      index: true,
    },
    homeTeam: {
      type: String,
      required: true,
      trim: true,
    },
    awayTeam: {
      type: String,
      required: true,
      trim: true,
    },
    matchDateTime: {
      type: Date,
      required: true,
      index: true,
    },
    venue: {
      type: String,
      required: true,
      trim: true,
    },
    description: {
      type: String,
      trim: true,
    },
    status: {
      type: String,
      enum: ["UPCOMING", "FINISHED", "CANCELLED"],
      default: "UPCOMING",
      required: true,
      index: true,
    },
    accreditationDeadline: {
      type: Date,
      required: true,
      index: true,
    },
  },
  {
    timestamps: true,
    versionKey: false,
  },
);

MatchSchema.index({ sport: 1, matchDateTime: 1 });
MatchSchema.index({ status: 1, matchDateTime: 1 });

export const Match = models.Match || model("Match", MatchSchema);
