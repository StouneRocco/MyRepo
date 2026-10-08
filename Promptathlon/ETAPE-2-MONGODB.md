# Étape 2 — MongoDB / Mongoose

## Objectif

Mettre en place une couche MongoDB/Mongoose propre et réutilisable pour les trois collections minimales du projet :

- `matches`
- `accreditationRequests`
- `admins`

## Implémentation

### Connexion MongoDB

`lib/mongodb.ts` :

- lit `MONGODB_URI` depuis l'environnement ;
- réutilise la connexion en développement pour éviter les connexions multiples avec Next.js ;
- limite le temps de sélection d'un serveur à 5 secondes ;
- configure un pool de 10 connexions ;
- réinitialise la promesse en cas d'échec afin qu'une tentative suivante puisse réussir ;
- expose aussi `disconnectDB()` pour les tests et scripts.

### Modèle Match

Collection logique : `matches`.

Champs :

- `sport` : BASKETBALL | HANDBALL
- `homeTeam`
- `awayTeam`
- `matchDateTime`
- `venue`
- `description`
- `status` : UPCOMING | FINISHED | CANCELLED
- `accreditationDeadline`
- `createdAt`
- `updatedAt`

Index :

- sport
- matchDateTime
- status
- accreditationDeadline
- sport + matchDateTime
- status + matchDateTime

Les dates sont stockées comme des dates MongoDB ; la couche d'affichage pourra ensuite appliquer la timezone métier.

### Modèle AccreditationRequest

Collection logique : `accreditationRequests`.

Champs :

- `matchId` : référence MongoDB vers Match
- `sport`
- `profileType` : JOURNALIST | PHOTOGRAPHER | VIDEOGRAPHER
- `firstName`
- `lastName`
- `email`
- `pressCardUrl`
- `needsBib`
- `portfolioUrl`
- `status` : PENDING | ACCEPTED | REJECTED
- `rejectionReason`
- `processedAt`
- `createdAt`
- `updatedAt`

Contrainte métier persistante :

`matchId + email + profileType` est unique afin d'empêcher une double demande pour le même match, la même adresse et le même profil.

Index complémentaires :

- matchId + status
- status + createdAt

### Modèle Admin

Collection logique : `admins`.

Champs :

- `email` unique
- `passwordHash`
- `role` : ADMIN
- `createdAt`
- `updatedAt`

Le mot de passe n'est jamais stocké en clair.

## Règles

La validation fonctionnelle des payloads reste dans Zod/API. Mongoose assure en plus :

- types MongoDB ;
- champs obligatoires ;
- enums ;
- trim/lowercase ;
- références ;
- index et unicité ;
- timestamps.

La règle J-24h reste une règle serveur/API : elle ne doit pas être considérée comme une simple contrainte de schéma MongoDB.

## Vérification de l'étape 2

À tester localement :

```bash
npm install
npm run typecheck
npm run build
```

Puis avec MongoDB disponible :

1. démarrer l'application ;
2. créer un match ;
3. vérifier son document dans `matches` ;
4. créer une demande d'accréditation ;
5. vérifier son document dans `accreditationRequests` ;
6. vérifier `status = PENDING` ;
7. tenter le même couple `matchId + email + profileType` deux fois ;
8. vérifier que MongoDB empêche le doublon ;
9. créer un administrateur et vérifier `passwordHash`.

## Limites

Cette étape ne couvre pas encore :

- stockage externe de carte de presse ;
- envoi d'e-mails ;
- workflow admin acceptation/refus complet ;
- audit sécurité ;
- tests automatisés finaux ;
- gestion définitive de la timezone et des tests J-24h de l'étape 8.
