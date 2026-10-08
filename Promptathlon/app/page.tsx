import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen px-6 py-16">
      <div className="mx-auto max-w-5xl">
        <p className="text-sm font-semibold uppercase tracking-widest text-blue-600">JDA</p>
        <h1 className="mt-3 text-4xl font-bold">Accréditations presse sport</h1>
        <p className="mt-4 text-gray-600">
          Déposez une demande d’accréditation pour les matchs de basketball et de handball.
        </p>
        <div className="mt-10 grid gap-6 sm:grid-cols-2">
          <Link className="rounded-2xl bg-white p-8 shadow-sm ring-1 ring-gray-200" href="/basketball">
            <h2 className="text-2xl font-semibold">Basketball</h2>
          </Link>
          <Link className="rounded-2xl bg-white p-8 shadow-sm ring-1 ring-gray-200" href="/handball">
            <h2 className="text-2xl font-semibold">Handball</h2>
          </Link>
        </div>
      </div>
    </main>
  );
}
