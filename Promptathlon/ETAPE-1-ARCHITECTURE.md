# Étape 1 — Architecture du site d'accréditation presse

## Objectif
Application web de gestion des demandes d'accréditation presse pour les matchs de basketball et de handball.

Deux espaces :
- Site public : consultation des matchs et dépôt des demandes.
- Administration privée : gestion des matchs et traitement des demandes.

## Stack
- Next.js + TypeScript
- App Router
- Tailwind CSS
- MongoDB + Mongoose
- Route Handlers Next.js
- Auth.js pour l'authentification administrateur
- Zod pour la validation
- EmailService abstrait
- StorageService abstrait pour les cartes de presse

## Architecture des dossiers

    app/
    ├── page.tsx
    ├── basketball/
    │   ├── page.tsx
    │   └── [id]/page.tsx
    ├── handball/
    │   ├── page.tsx
    │   └── [id]/page.tsx
    ├── admin/
    │   ├── login/page.tsx
    │   ├── page.tsx
    │   ├── basketball/page.tsx
    │   ├── handball/page.tsx
    │   └── accreditations/page.tsx
    └── api/
        ├── matches/route.ts
        ├── matches/[id]/route.ts
        ├── accreditations/route.ts
        └── admin/
            ├── matches/route.ts
            ├── matches/[id]/route.ts
            ├── accreditations/route.ts
            └── accreditations/[id]/route.ts
    components/
    ├── ui/
    ├── matches/
    ├── accreditation/
    └── admin/
    lib/
    ├── mongodb.ts
    ├── auth.ts
    ├── validations/
    ├── services/email/
    ├── services/storage/
    └── utils/
    models/
    ├── Match.ts
    ├── AccreditationRequest.ts
    └── Admin.ts
    types/
    ├── match.ts
    ├── accreditation.ts
    └── admin.ts
    public/
    .env.example
    middleware.ts
    package.json
    tsconfig.json
    next.config.ts
    README.md

## Modèles MongoDB

### Match
- sport : BASKETBALL | HANDBALL
- homeTeam
- awayTeam
- matchDateTime
- venue
- description facultative
- status : UPCOMING | FINISHED | CANCELLED
- accreditationDeadline
- createdAt
- updatedAt

Par défaut, accreditationDeadline = matchDateTime - 24 heures. Une surcharge manuelle pourra être prévue.

### AccreditationRequest
- matchId
- sport
- profileType : JOURNALIST | PHOTOGRAPHER | VIDEOGRAPHER
- firstName
- lastName
- email
- pressCardUrl facultatif
- needsBib facultatif
- portfolioUrl facultatif
- status : PENDING | ACCEPTED | REJECTED
- rejectionReason facultatif
- processedAt facultatif
- createdAt
- updatedAt

### Admin
- email
- passwordHash
- role
- createdAt
- updatedAt

Les mots de passe ne sont jamais stockés en clair.

## Relations
Un Match possède plusieurs AccreditationRequest. Chaque demande référence son match par matchId.

## Routes API

### Public
- GET /api/matches — filtres sport, date, status
- GET /api/matches/[id]
- POST /api/accreditations

POST /api/accreditations doit vérifier côté serveur : existence du match, statut, deadline, validation des données et doublons éventuels avant création.

### Administration
- GET /api/admin/matches
- POST /api/admin/matches
- PUT /api/admin/matches/[id]
- DELETE /api/admin/matches/[id]
- GET /api/admin/accreditations
- PUT /api/admin/accreditations/[id]

Toutes les routes admin nécessitent une authentification.

## Pages frontend
- / : accueil et choix Basketball / Handball
- /basketball : liste des matchs
- /basketball/[id] : détail du match et demande
- /handball : liste des matchs
- /handball/[id] : détail du match et demande
- /admin/login : connexion
- /admin : dashboard
- /admin/basketball
- /admin/handball
- /admin/accreditations

## Formulaire
Un formulaire dynamique unique est utilisé pour les trois profils.

Journaliste : prénom, nom, email, carte de presse facultative, besoin d'un chasuble oui/non.
Photographe ou vidéaste : prénom, nom, email, portfolio facultatif mais recommandé.
Après envoi, la demande reste PENDING jusqu'à décision de l'administrateur.

## Règle métier J-24h
Pour chaque match : accreditationDeadline = matchDateTime - 24 heures.
Avant la deadline : les demandes sont ouvertes.
À partir de la deadline : les demandes sont closes.
La vérification doit être faite côté frontend et impérativement côté serveur.
Les dates sont stockées en UTC et affichées dans le fuseau horaire configuré pour l'organisation.

## Sécurité
- authentification admin séparée
- sessions sécurisées et cookies HTTP-only
- mots de passe hashés
- protection des routes admin
- validation serveur avec Zod
- secrets uniquement dans les variables d'environnement
- aucun accès MongoDB depuis le navigateur
- aucune donnée personnelle exposée par les API publiques
- protection future des cartes de presse
- rate limiting des endpoints sensibles
- aucun log de mot de passe, token ou document privé

## Services extensibles
Les services externes sont isolés dans lib/services/email et lib/services/storage afin de pouvoir changer de fournisseur sans modifier le domaine métier.

## Décisions d'architecture
- Les matchs sont créés depuis l'administration et ne sont pas codés en dur.
- Les trois profils utilisent une collection unique accreditationRequests.
- Le formulaire est dynamique et partagé.
- Cette architecture constitue le contrat de conception pour les étapes suivantes.