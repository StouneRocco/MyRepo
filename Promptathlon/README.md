# Promptathlon — Accréditations presse JDA

Application Next.js (App Router), TypeScript, Tailwind CSS et MongoDB/Mongoose pour centraliser les demandes d'accréditation presse aux matchs de basketball et de handball.

## Fonctionnalités présentes

- Pages publiques par sport, liste des matchs à venir et formulaire de demande.
- Clôture des demandes à la date limite du match (par défaut 24 heures avant le coup d'envoi), contrôlée côté serveur.
- Prévention des demandes en double (index MongoDB unique).
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

## Points à finaliser avant la mise en production

- **Stockage des cartes de presse :** le formulaire actuel accepte encore une URL. Il faut intégrer un téléversement vers un stockage privé (S3 compatible ou équivalent), avec téléchargement signé réservé à l'administration, contrôle du type et de la taille et politique de rétention.
- **Emails :** configurer et vérifier le domaine expéditeur Brevo. Une décision est sauvegardée même si l'envoi échoue; l'état d'envoi est visible afin d'éviter de confondre décision et notification.
- **Protection anti-abus :** ajouter un rate limiting persistant aux endpoints publics et à la connexion.
- **Exploitation :** confirmer l'hébergement, configurer les variables secrètes, les sauvegardes MongoDB, la rétention RGPD et les tests de bout en bout sur un environnement de préproduction.

## Branche de travail

Les évolutions en cours sont dans la branche `feature/jda-security-baseline` et la pull request associée. Elles ne sont pas fusionnées dans la branche de base.
