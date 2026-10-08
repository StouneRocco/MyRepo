# Promptathlon

Site Next.js de gestion des accréditations presse basketball et handball.

## Lancer

Copier .env.example vers .env.local, renseigner MongoDB et AUTH_SECRET, puis npm install && npm run dev.

Le socle comprend les pages publiques, formulaire dynamique, MongoDB/Mongoose, règle J-24h et authentification admin. Les étapes de production (stockage externe sécurisé, emails idempotents, audit et tests complets) restent à finaliser.