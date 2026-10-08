import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "JDA — Accréditations presse",
  description: "Demandes d'accréditation presse pour les matchs de basketball et de handball de la JDA.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
