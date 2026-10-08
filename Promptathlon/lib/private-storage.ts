import { randomUUID } from "node:crypto";
import { GetObjectCommand, HeadObjectCommand, PutObjectCommand, S3Client } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

export const MAX_PRESS_CARD_BYTES = 5 * 1024 * 1024;
export const ALLOWED_DOCUMENT_TYPES = ["application/pdf", "image/jpeg", "image/png", "image/webp"] as const;
export type AllowedDocumentType = (typeof ALLOWED_DOCUMENT_TYPES)[number];

function storageConfig() {
  const bucket = process.env.S3_BUCKET;
  const accessKeyId = process.env.S3_ACCESS_KEY_ID;
  const secretAccessKey = process.env.S3_SECRET_ACCESS_KEY;
  if (!bucket || !accessKeyId || !secretAccessKey) {
    throw new Error("Le stockage privé n'est pas configuré (S3_BUCKET, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY).");
  }
  const endpoint = process.env.S3_ENDPOINT || undefined;
  return {
    bucket,
    client: new S3Client({
      region: process.env.S3_REGION || "auto",
      endpoint,
      forcePathStyle: Boolean(endpoint),
      credentials: { accessKeyId, secretAccessKey },
    }),
  };
}

export function isAllowedDocumentType(value: string): value is AllowedDocumentType {
  return (ALLOWED_DOCUMENT_TYPES as readonly string[]).includes(value);
}

export async function createPressCardUpload() {
  const { bucket, client } = storageConfig();
  const key = `press-cards/${randomUUID()}`;
  const uploadUrl = await getSignedUrl(client, new PutObjectCommand({
    Bucket: bucket,
    Key: key,
    ContentType: "application/pdf",
  }), { expiresIn: 300 });
  return { key, uploadUrl, expiresIn: 300 };
}

export async function verifyPressCardObject(key: string) {
  if (!/^press-cards\/[0-9a-f-]{36}$/.test(key)) return false;
  const { bucket, client } = storageConfig();
  try {
    const object = await client.send(new HeadObjectCommand({ Bucket: bucket, Key: key }));
    return Boolean(
      object.ContentLength &&
      object.ContentLength > 0 &&
      object.ContentLength <= MAX_PRESS_CARD_BYTES &&
      object.ContentType === "application/pdf",
    );
  } catch {
    return false;
  }
}

export async function createPressCardDownloadUrl(key: string) {
  if (!/^press-cards\/[0-9a-f-]{36}$/.test(key)) throw new Error("Clé de document invalide.");
  const { bucket, client } = storageConfig();
  const valid = await verifyPressCardObject(key);
  if (!valid) throw new Error("Document introuvable ou invalide.");
  return getSignedUrl(client, new GetObjectCommand({
    Bucket: bucket,
    Key: key,
    ResponseContentDisposition: 'attachment; filename="carte-de-presse.pdf"',
    ResponseContentType: "application/pdf",
  }), { expiresIn: 60 });
}
