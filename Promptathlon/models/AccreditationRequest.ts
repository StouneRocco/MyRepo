import { Schema, model, models } from "mongoose";

const AccreditationRequestSchema = new Schema({
  matchId: { type: Schema.Types.ObjectId, ref: "Match", required: true, index: true },
  sport: { type: String, enum: ["BASKETBALL", "HANDBALL"], required: true },
  profileType: { type: String, enum: ["JOURNALIST", "PHOTOGRAPHER", "VIDEOGRAPHER"], required: true },
  firstName: { type: String, required: true, trim: true, maxlength: 100 },
  lastName: { type: String, required: true, trim: true, maxlength: 100 },
  email: { type: String, required: true, lowercase: true, trim: true, index: true, maxlength: 254 },
  pressCardUrl: { type: String, maxlength: 2048 },
  needsBib: { type: Boolean, default: false },
  portfolioUrl: { type: String, maxlength: 2048 },
  status: { type: String, enum: ["PENDING", "ACCEPTED", "REJECTED"], default: "PENDING", index: true },
  rejectionReason: { type: String, maxlength: 500 },
  processedAt: Date,
  notificationStatus: { type: String, enum: ["NOT_REQUIRED", "PENDING", "SENDING", "SENT", "FAILED"], default: "PENDING" },
  notificationSentAt: Date,
  notificationError: { type: String, maxlength: 500 },
}, { timestamps: true });

AccreditationRequestSchema.index({ matchId: 1, email: 1, profileType: 1 }, { unique: true });
export const AccreditationRequest = models.AccreditationRequest || model("AccreditationRequest", AccreditationRequestSchema);
