"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type RequestRow = {
  _id: string;
  firstName: string;
  lastName: string;
  email: string;
  profileType: "JOURNALIST" | "PHOTOGRAPHER" | "VIDEOGRAPHER";
  sport: "BASKETBALL" | "HANDBALL";
  status: "PENDING" | "ACCEPTED" | "REJECTED";
  needsBib?: boolean;
  pressCardKey?: string;
  portfolioUrl?: string;
  matchId: { _id: string; homeTeam: string; awayTeam: string; matchDateTime: string; venue: string } | string;
  notificationStatus?: string;
};

const profileLabels = { JOURNALIST: "Journaliste", PHOTOGRAPHER: "Photographe", VIDEOGRAPHER: "Vidéaste" };
const statusLabels = { PENDING: "En attente", ACCEPTED: "Acceptée", REJECTED: "Refusée" };

export default function AccreditationAdminList() {
  const [rows, setRows] = useState<RequestRow[]>([]);
  const [filter, setFilter] = useState("PENDING");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const response = await fetch("/api/admin/accreditations", { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || "Chargement impossible.");
      setRows(data.requests || []);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Erreur de chargement.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function decide(id: string, status: "ACCEPTED" | "REJECTED") {
    const label = status === "ACCEPTED" ? "accepter" : "refuser";
    if (!window.confirm("Confirmer : " + label + " cette demande ?")) return;
    setBusy(id);
    setMessage("");
    try {
      const response = await fetch("/api/admin/accreditations/" + id, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      const data = await response.json();
      setMessage(data.message || (response.ok ? "Décision enregistrée." : "Une erreur est survenue."));
      await load();
    } catch {
      setMessage("Impossible de joindre le serveur.");
    } finally {
      setBusy(null);
    }
  }

  const visible = rows.filter((row) => filter === "ALL" || row.status === filter);
  return (
    <main className="min-h-screen bg-gray-50 px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-7xl">
        <Link href="/admin" className="text-blue-700 hover:underline">← Tableau de bord</Link>
        <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
          <div><h1 className="text-3xl font-bold">Demandes d’accréditation</h1><p className="mt-2 text-gray-600">{rows.length} demande(s) au total</p></div>
          <select aria-label="Filtrer par statut" value={filter} onChange={(e) => setFilter(e.target.value)} className="rounded-lg border bg-white p-3">
            <option value="PENDING">En attente</option><option value="ACCEPTED">Acceptées</option><option value="REJECTED">Refusées</option><option value="ALL">Toutes</option>
          </select>
        </div>
        {message && <p role="status" className="mt-5 rounded-lg bg-blue-50 p-4 text-sm text-blue-900">{message}</p>}
        {loading ? <p className="mt-8">Chargement des demandes…</p> : visible.length === 0 ? <p className="mt-8 rounded-xl bg-white p-8 text-gray-600">Aucune demande dans cette catégorie.</p> : (
          <div className="mt-6 overflow-x-auto rounded-xl bg-white shadow-sm ring-1 ring-gray-200">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead className="bg-gray-100"><tr>{["Candidat", "Profil", "Sport", "Match", "Contact / pièces", "Statut", "Email", "Décision"].map((h) => <th key={h} className="p-3 font-semibold">{h}</th>)}</tr></thead>
              <tbody>{visible.map((row) => {
                const match = typeof row.matchId === "object" ? row.matchId : null;
                return <tr key={row._id} className="border-t align-top">
                  <td className="p-3 font-medium">{row.firstName} {row.lastName}{row.needsBib && <span className="block text-xs text-gray-500">Chasuble demandée</span>}</td>
                  <td className="p-3">{profileLabels[row.profileType]}</td><td className="p-3">{row.sport === "BASKETBALL" ? "Basketball" : "Handball"}</td>
                  <td className="p-3">{match ? <>{match.homeTeam} — {match.awayTeam}<span className="block text-xs text-gray-500">{new Date(match.matchDateTime).toLocaleString("fr-FR", { timeZone: "Europe/Paris" })}<br />{match.venue}</span></> : "Match " + String(row.matchId)}</td>
                  <td className="p-3"><a className="text-blue-700 underline" href={"mailto:" + row.email}>{row.email}</a>{row.pressCardKey && <a className="mt-1 block text-blue-700 underline" href={"/api/admin/accreditations/" + row._id + "/document"} target="_blank" rel="noreferrer">Télécharger la carte de presse</a>}{row.portfolioUrl && <a className="mt-1 block text-blue-700 underline" href={row.portfolioUrl} target="_blank" rel="noreferrer">Portfolio externe</a>}</td>
                  <td className="p-3">{statusLabels[row.status]}</td><td className="p-3">{row.notificationStatus || "Non renseigné"}</td>
                  <td className="p-3">{row.status === "PENDING" ? <div className="flex gap-2"><button disabled={busy === row._id} onClick={() => void decide(row._id, "ACCEPTED")} className="rounded bg-green-700 px-3 py-2 text-white disabled:opacity-50">Accepter</button><button disabled={busy === row._id} onClick={() => void decide(row._id, "REJECTED")} className="rounded bg-red-700 px-3 py-2 text-white disabled:opacity-50">Refuser</button></div> : "Traité"}</td>
                </tr>;
              })}</tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
