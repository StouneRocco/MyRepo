import { Schema, model, models } from "mongoose";

const AccreditationRequestSchema = new Schema(
  {
    matchId: {
      type: Schema.Types.ObjectId,
      ref: "Match",
      required: true,
      index: true,
    },
    sport: {
      type: String,
      enum: ["BASKETBALL", "HANDBALL"],
      required: true,
      index: true,
    },
    profileType: {
      type: String,
      enum: ["JOURNALIST", "PHOTOGRAPHER", "VIDEOGRAPHER"],
      required: true,
      index: true,
    },
    firstName: {
      type: String,
      required: true,
      trim: true,
    },
    lastName: {
      type: String,
      required: true,
      trim: true,
    },
    email: {
      type: String,
      required: true,
      lowercase: true,
      trim: true,
      index: true,
    },
    pressCardUrl: {
      type: String,
      trim: true,
    },
    needsBib: {
      type: Boolean,
      default: false,
      required: true,
    },
    portfolioUrl: {
      type: String,
      trim: true,
    },
    status: {
      type: String,
      enum: ["PENDING", "ACCEPTED", "REJECTED"],
      default: "PENDING",
      required: true,
      index: true,
    },
    rejectionReason: {
      type: String,
      trim: true,
    },
    processedAt: Date,
  },
  {
    timestamps: true,
    versionKey: false,
  },
);

AccreditationRequestSchema.index(
  { matchId: 1, email: 1, profileType: 1 },
  { unique: true, name: "unique_request_per_match_email_profile" },
);
AccreditationRequestSchema.index({ matchId: 1, status: 1 });
AccreditationRequestSchema.index({ status: 1, createdAt: -1 });

export const AccreditationRequest =
  models.AccreditationRequest ||
  model("AccreditationRequest", AccreditationRequestSchema);
