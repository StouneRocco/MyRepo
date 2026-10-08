import { Schema, model, models } from "mongoose";

const AdminSchema = new Schema(
  {
    email: {
      type: String,
      required: true,
      unique: true,
      lowercase: true,
      trim: true,
    },
    passwordHash: {
      type: String,
      required: true,
    },
    role: {
      type: String,
      enum: ["ADMIN"],
      default: "ADMIN",
      required: true,
    },
  },
  {
    timestamps: true,
    versionKey: false,
  },
);

AdminSchema.index({ email: 1 }, { unique: true });

export const Admin = models.Admin || model("Admin", AdminSchema);
