# Promptathlon — Accréditations presse JDA

Application Next.js (App Router), TypeScript, Tailwind CSS et MongoDB/Mongoose pour centraliser les demandes d'accréditation presse aux matchs de basketball et de handball.

## Fonctionnalités présentes

- Pages publiques par sport, liste des matchs à venir et formulaire de demande.
- Clôture des demandes à la date limite du match (par défaut 24 heures avant le coup d'envoi), contrôlée côté serveur.
- Prévention des demandes en double (index MongoDB unique).
- Limitation persistante des tentatives de connexion (10/15 min), des demandes publiques (10/15 min) et des téléversements (8/h), avec fenêtres en base MongoDB et purge TTL.
- Carte de presse PDF téléversée directement dans un stockage privé compatible S3; taille maximale 5 Mo et type PDF contrôlés côté serveur.
- Téléchargement de la carte de presse réservé à l'administration, via une URL signée de courte durée.
- Administration protégée : consultation des demandes, filtrage par statut, création de matchs et acceptation/refus.
- Sessions JWT dans un cookie HTTP-only et validation des entrées avec Zod.
- Emails transactionnels de décision via Brevo lorsque les variables correspondantes sont configurées.
- Workflow GitHub Actions pour le contrôle TypeScript et le build de production.

## Environnement

Copier `.env.example` vers `.env.local`, puis renseigner les valeurs réelles :

- `MONGODB_URI` : URI MongoDB de l'organisation.
- `AUTH_SECRET` : secret aléatoire unique d'au moins 32 caractères. Exemple de génération : `openssl rand -base64 32`.
- `APP_TIMEZONE` : fuseau d'affichage, par défaut `Europe/Paris`.
- `BREVO_API_KEY`, `BREVO_SENDER_EMAIL` et éventuellement `BREVO_SENDER_NAME` : nécessaires pour envoyer les emails de décision.
- `S3_BUCKET`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` et, si nécessaire, `S3_ENDPOINT` : accès au bucket privé pour les justificatifs.

### Configuration du bucket privé

Le bucket doit rester privé, sans accès anonyme en lecture. Les clés d'accès doivent être limitées au bucket utilisé par l'application. Les fichiers sont contrôlés par le serveur avant leur envoi au bucket. Les URL de téléchargement expirent après 60 secondes.

Les fichiers acceptés sont les PDF de 5 Mo maximum. Le contrôle de taille est réalisé dans l'interface et à nouveau par le serveur après téléversement. Les objets orphelins (téléversés mais jamais associés à une demande) doivent être supprimés par une règle de cycle de vie du fournisseur, par exemple après 24 heures.

Ne jamais committer `.env.local`, les secrets ou les identifiants de production. Si le secret d'authentification change, les sessions existantes deviennent invalides.

## Développement

```bash
npm install
npm run dev
```

Contrôles :

```bash
npm run typecheck
npm run build
```

L'initialisation du premier compte administrateur doit être faite de façon contrôlée en base avec un mot de passe hashé (bcrypt). Aucun compte ni mot de passe par défaut n'est créé par l'application.

## Points à vérifier avant la mise en production

- Configurer les variables d'environnement MongoDB, JWT, Brevo et stockage privé.
- Vérifier le domaine expéditeur Brevo et tester la délivrabilité.
- Configurer le reverse proxy de façon à fournir un en-tête d’adresse IP client fiable, nécessaire au rate limiting.
- Définir une politique de conservation/suppression des données personnelles et des cartes de presse, les sauvegardes MongoDB et les droits d'accès des administrateurs.
- Tester le parcours complet sur un environnement de préproduction avec les services réels.
- Vérifier les résultats du workflow GitHub Actions avant de fusionner.

## Branche de travail

Les évolutions sont dans la branche `feature/jda-security-baseline` et la pull request associée. Elles ne sont pas fusionnées dans la branche de base.
