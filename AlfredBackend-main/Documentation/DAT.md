# DAT – Alfred Backend

## 1. Contexte et objectifs

Alfred est un gestionnaire de maison connectée (projet SI & Infra). Il vise à rendre les écosystèmes domotiques plus simples à utiliser et plus personnalisables, en centralisant la gestion des appareils, des pièces et des foyers derrière une API unique.

Ce backend expose l'API consommée par le(s) client(s) (web responsive).

## 2. Périmètre fonctionnel cible

- Gestion des appareils via protocoles Matter et ZigBee
- Commande des actionneurs et affichage des capteurs
- Scènes 1D pour la synchronisation de LED (évolutif en 2D/3D)
- Visualisation des pièces et des appareils qu'elles contiennent
- Authentification et rôles : `user`, `home_manager`, `admin`, `admin_reader`
- Gestion des foyers (homes)
- Notifications intelligentes
- Bonus : assistant vocal, simulateurs d'appareils

**Entités métier pressenties** (à confirmer) : User, Home, Room, Device, Scene.

## 3. Principes d'architecture

- Architecture **N-tiers** en 4 projets, avec dépendances strictement descendantes
- Modèles de domaine partagés entre couches (pas de duplication par couche)
- Dépendances par **interfaces**, injectées (testabilité)
- Chaque couche déclare ses propres enregistrements DI
- Routes fines, logique métier uniquement dans la BLL

## 4. Architecture applicative

```
Requête HTTP
   ↓
Backend.API     Routes → Controllers → DTOs
   ↓
Backend.BLL     Interfaces → Services
   ↓
Backend.DAL     Repositories → AppDbContext
   ↓
Backend.Models  Modèles de domaine (propriétés seules)
```

| Projet | Rôle | Contenu |
| --- | --- | --- |
| Backend.API | Point d'entrée HTTP | Routes, Controllers, DTOs, DI API |
| Backend.BLL | Logique métier | Interfaces, Services, DI BLL |
| Backend.DAL | Persistance | Repositories, `AppDbContext`, DI DAL |
| Backend.Models | Modèles partagés | POCOs sans logique |

**Règles de dépendance**

- API → BLL, Models ; API → DAL uniquement pour la composition (`Program.cs`)
- BLL → DAL, Models
- DAL → Models
- Models → aucune dépendance
- Interdit : DTO/Controller importés par BLL ou DAL, `AppDbContext` accessible depuis l'API, saut de couche

**Flux d'une requête** : Route (binding) → Controller (DTO → appel service) → Service (règles métier) → Repository (accès BD) → Modèle.

## 5. Stack technique

| Domaine | Choix | Statut |
| --- | --- | --- |
| Runtime / langage | .NET 10, C# 14 | En place |
| API | ASP.NET Core Minimal APIs | En place |
| Documentation API | Swagger UI (Swashbuckle 10.2.3) + OpenAPI | En place (dev) |
| ORM | Entity Framework Core 10 | Configuré, non utilisé |
| Base de données | PostgreSQL (Npgsql 10.0.0) | Prévu, pas de connexion configurée |
| Validation | DataAnnotations sur les DTOs | Partiel (voir §9) |
| Injection de dépendances | Microsoft.Extensions.DependencyInjection | En place |

## 6. Injection de dépendances

`Program.cs` est la racine de composition et appelle, dans cet ordre, `AddDAL()`, `AddBLL()`, `AddAPI()`. Durée de vie par défaut : **Scoped**.

| Fichier | Enregistre |
| --- | --- |
| `Backend.DAL/DependencyInjection.cs` | `AppDbContext`, repositories |
| `Backend.BLL/DependencyInjection.cs` | Services (`I*Service` → `*Service`) |
| `Backend.API/DependencyInjection.cs` | Controllers |

## 7. Données

- `AppDbContext` existe mais ne déclare encore aucune entité ni relation
- Aucun repository ni migration à ce jour
- Migrations EF Core pilotées depuis `Backend.API` (projet de démarrage) vers `Backend.DAL`
- Chaîne de connexion à externaliser dans la configuration (aucun secret en dur)

## 8. Interface API

- Chaque feature expose un groupe de routes (`MapGroup("/<feature>")`) sous forme de méthode d'extension `Map<Feature>Routes()`
- Les DTOs de requête sont dédiés et `sealed` ; les DTOs `GET` utilisent `[AsParameters]`
- Feature de référence : `Example`

| Méthode | Route | Description |
| --- | --- | --- |
| GET | `/example/hello_world?name=` | Retourne un `ExempleUser` (Id + Name) |

- URLs locales : `http://localhost:5230`, `https://localhost:7247`
- Swagger UI disponible uniquement en environnement Development

## 9. Sécurité

| Sujet | État |
| --- | --- |
| Authentification / autorisation par rôles | Prévu, non implémenté |
| HTTPS | Redirection activée |
| Secrets | Hors dépôt (à respecter pour la chaîne de connexion) |
| `AllowedHosts` | `*` (à restreindre en production) |
| Validation des entrées | DataAnnotations présents sur les DTOs ; `AddValidation()` non appelé dans `Program.cs` |

## 10. Build, exécution et déploiement

- Outils : `dotnet restore`, `dotnet build`, `dotnet run --project Backend.API`, `dotnet watch`
- Éditeur : VS Code (`launch.json` et `tasks.json` fournis)
- Pas de conteneurisation, de CI/CD ni de stratégie d'hébergement définies à ce jour

## 11. Conventions

- PascalCase (types, fichiers, namespaces), camelCase (variables), `_camelCase` (champs privés)
- Préfixe `I` pour les interfaces, suffixe `Async` pour les méthodes asynchrones, `Is`/`Has`/`Can` pour les booléens
- Constructeurs primaires privilégiés ; contenu du projet (code, docs, messages) en anglais
- Ajout d'une feature : décliner le gabarit `Example*` couche par couche (checklist dans `AGENTS.md`)

## 12. Points d'attention

1. **Validation inactive** : ajouter `builder.Services.AddValidation()` pour que les DataAnnotations soient appliquées.
2. **Casse des chemins** : les dossiers sont en minuscules (`backend.api`) alors que `backend.slnx` et les références de projet utilisent `Backend.API`. Cela fonctionne sous Windows/macOS mais échouera sous Linux (CI, conteneur).
3. **Persistance** : aucune entité, repository ni connexion PostgreSQL ; la couche DAL est à construire.
4. **Controllers** : classes simples injectées dans les routes (pas des contrôleurs MVC) ; choix à assumer et documenter.
5. **Nommage** : `ExempleUser` (typo) à aligner sur `Example`.
6. **Swagger et OpenAPI** : `MapOpenApi()` et Swashbuckle sont tous deux activés ; n'en conserver qu'un si possible.
7. **Pas de tests** : aucun projet de tests dans la solution.

## 13. Feuille de route technique

1. Persistance : entités, repositories, connexion PostgreSQL, première migration
2. Authentification et rôles
3. Features cœur : Home, Room, Device
4. Intégration protocoles Matter / ZigBee (passerelle ou adaptateurs)
5. Scènes LED et notifications
6. Tests, CI/CD et conteneurisation
7. Bonus : assistant vocal, simulateurs
