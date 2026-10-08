"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";

type MatchRow = {
  _id: string; sport: "BASKETBALL" | "HANDBALL"; homeTeam: string; awayTeam: string;
  matchDateTime: string; venue: string; description?: string; status: "UPCOMING" | "FINISHED" | "CANCELLED";
  accreditationDeadline: string;
};

export default function MatchAdminManager() {
  const [matches, setMatches] = useState<MatchRow[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const response = await fetch("/api/admin/matches", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || "Chargement des matchs impossible.");
    setMatches(data.matches || []);
  }
  useEffect(() => { void load().catch((e) => setMessage(e.message)); }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setMessage("");
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    const matchDateTime = new Date(String(values.matchDateTime)).toISOString();
    try {
      const response = await fetch("/api/admin/matches", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...values, matchDateTime, status: "UPCOMING" }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || "Création impossible.");
      form.reset();
      setMessage("Match créé. Les inscriptions ferment automatiquement 24 heures avant le coup d’envoi.");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Erreur inattendue.");
    } finally { setBusy(false); }
  }

  return <main className="min-h-screen bg-gray-50 px-4 py-8 sm:px-8"><div className="mx-auto max-w-6xl">
    <Link href="/admin" className="text-blue-700 hover:underline">← Tableau de bord</Link>
    <h1 className="mt-4 text-3xl font-bold">Gestion des matchs</h1>
    {message && <p role="status" className="mt-4 rounded-lg bg-blue-50 p-4 text-sm">{message}</p>}
    <section className="mt-6 rounded-xl bg-white p-6 shadow-sm ring-1 ring-gray-200">
      <h2 className="text-xl font-semibold">Ajouter un match</h2>
      <form onSubmit={submit} className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className="text-sm">Sport<select required name="sport" className="mt-1 block w-full rounded-lg border p-3"><option value="BASKETBALL">Basketball</option><option value="HANDBALL">Handball</option></select></label>
        <label className="text-sm">Date et heure<input required name="matchDateTime" type="datetime-local" className="mt-1 block w-full rounded-lg border p-3"/></label>
        <label className="text-sm">Équipe domicile<input required minLength={2} name="homeTeam" className="mt-1 block w-full rounded-lg border p-3"/></label>
        <label className="text-sm">Équipe extérieure<input required minLength={2} name="awayTeam" className="mt-1 block w-full rounded-lg border p-3"/></label>
        <label className="text-sm sm:col-span-2">Lieu<input required minLength={2} name="venue" className="mt-1 block w-full rounded-lg border p-3"/></label>
        <label className="text-sm sm:col-span-2">Informations complémentaires<textarea name="description" maxLength={2000} className="mt-1 block w-full rounded-lg border p-3"/></label>
        <div className="sm:col-span-2"><button disabled={busy} className="rounded-lg bg-blue-700 px-5 py-3 font-semibold text-white disabled:opacity-50">{busy ? "Création…" : "Créer le match"}</button></div>
      </form>
    </section>
    <section className="mt-8"><h2 className="text-xl font-semibold">Matchs enregistrés ({matches.length})</h2><div className="mt-4 grid gap-3">{matches.map((match) => <article key={match._id} className="rounded-xl bg-white p-5 ring-1 ring-gray-200"><div className="flex flex-wrap justify-between gap-2"><strong>{match.sport === "BASKETBALL" ? "Basketball" : "Handball"} · {match.homeTeam} — {match.awayTeam}</strong><span className="text-sm text-gray-600">{match.status}</span></div><p className="mt-2 text-sm text-gray-600">{new Date(match.matchDateTime).toLocaleString("fr-FR", { timeZone: "Europe/Paris" })} · {match.venue}</p><p className="mt-1 text-xs text-gray-500">Clôture : {new Date(match.accreditationDeadline).toLocaleString("fr-FR", { timeZone: "Europe/Paris" })}</p></article>)}</div></section>
  </div></main>;
}
