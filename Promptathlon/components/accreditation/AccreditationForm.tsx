"use client";

import { FormEvent, useState } from "react";

const MAX_FILE_BYTES = 5 * 1024 * 1024;

export default function AccreditationForm({ matchId }: { matchId: string }) {
  const [profileType, setProfileType] = useState("JOURNALIST");
  const [pressCardKey, setPressCardKey] = useState("");
  const [message, setMessage] = useState("");
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function uploadPressCard(file: File | undefined) {
    setPressCardKey("");
    if (!file) return;
    if (file.type !== "application/pdf" || file.size <= 0 || file.size > MAX_FILE_BYTES) {
      setMessage("La carte de presse doit être un PDF de 5 Mo maximum.");
      return;
    }
    setUploading(true);
    setMessage("Téléversement sécurisé de la carte de presse…");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const result = await fetch("/api/accreditations/upload", { method: "POST", body: formData });
      const upload = await result.json();
      if (!result.ok) throw new Error(upload.message || "Téléversement indisponible.");
      setPressCardKey(upload.key);
      setMessage(upload.message || "Carte de presse téléversée de façon privée.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Échec du téléversement.");
    } finally {
      setUploading(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (profileType === "JOURNALIST" && !pressCardKey) {
      setMessage("Veuillez téléverser votre carte de presse en PDF.");
      return;
    }
    setSubmitting(true);
    setMessage("");
    try {
      const data = Object.fromEntries(new FormData(form));
      const response = await fetch("/api/accreditations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...data,
          matchId,
          profileType,
          pressCardKey: profileType === "JOURNALIST" ? pressCardKey : undefined,
          needsBib: data.needsBib === "on",
        }),
      });
      const result = await response.json();
      setMessage(result.message || (response.ok ? "Demande envoyée." : "Une erreur est survenue."));
      if (response.ok) {
        form.reset();
        setPressCardKey("");
        setProfileType("JOURNALIST");
      }
    } catch {
      setMessage("Impossible de joindre le serveur. Réessayez.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-6 rounded-2xl bg-white p-8 shadow-sm ring-1 ring-gray-200">
      <h2 className="text-2xl font-semibold">Demande d’accréditation</h2>
      <label className="mt-6 block text-sm font-medium">Profil
        <select name="profileType" value={profileType} onChange={(event) => { setProfileType(event.target.value); setPressCardKey(""); setMessage(""); }} className="mt-2 w-full rounded-lg border p-3">
          <option value="JOURNALIST">Journaliste</option>
          <option value="PHOTOGRAPHER">Photographe</option>
          <option value="VIDEOGRAPHER">Vidéaste</option>
        </select>
      </label>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <input required name="firstName" minLength={2} maxLength={100} autoComplete="given-name" placeholder="Prénom" className="rounded-lg border p-3" />
        <input required name="lastName" minLength={2} maxLength={100} autoComplete="family-name" placeholder="Nom" className="rounded-lg border p-3" />
        <input required type="email" name="email" maxLength={254} autoComplete="email" placeholder="Email" className="rounded-lg border p-3 sm:col-span-2" />
        {profileType === "JOURNALIST" ? (
          <>
            <label className="sm:col-span-2 block text-sm font-medium">Carte de presse (PDF, 5 Mo maximum) *
              <input required type="file" accept="application/pdf,.pdf" onChange={(event) => void uploadPressCard(event.target.files?.[0])} className="mt-2 block w-full rounded-lg border p-3" />
              <span className="mt-1 block font-normal text-gray-500">Le document est stocké dans un espace privé et n’est pas publié sur le site.</span>
              {pressCardKey && <span className="mt-1 block text-sm text-green-700">Document prêt à être envoyé avec la demande.</span>}
            </label>
            <label className="sm:col-span-2 flex items-center gap-2"><input type="checkbox" name="needsBib" /> Besoin d’un chasuble</label>
          </>
        ) : (
          <label className="sm:col-span-2 block text-sm font-medium">Portfolio (facultatif)
            <input type="url" name="portfolioUrl" maxLength={2048} placeholder="https://…" className="mt-2 w-full rounded-lg border p-3" />
          </label>
        )}
      </div>
      <button disabled={uploading || submitting} className="mt-6 rounded-lg bg-blue-700 px-5 py-3 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50">
        {uploading ? "Téléversement…" : submitting ? "Envoi…" : "Envoyer la demande"}
      </button>
      {message && <p role="status" className="mt-4 text-sm">{message}</p>}
    </form>
  );
}
