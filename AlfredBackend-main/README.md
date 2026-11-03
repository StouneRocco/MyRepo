# Projet SI & Infra → Alfred

*Home manager projet*

### Problem: Make home automation ecosystems easier and more customizable (home automation in general)

## Features

- Device management with protocols (Matter, ZigBee)
- Basic functions for actuators and sensor displays
- 1D scene management system for LED synchronization (potential to upgrade to 2D or 3D)
- Visualization of rooms with devices inside
- Authentication system with roles → user, home_manager, admin, admin_reader
- Household (home) management system
- Voice assistant (bonus)
- Device simulators to test before buying (bonus)
- Smart notifications
- Responsive design

---

## Technical guide

### Naming convention

| Cas | Convention | Exemple |
| --- | --- | --- |
| Types, membres publics, fichiers, dossiers, projets, namespaces | PascalCase | `EquipeService`, `MonApp.Bll.Services` |
| Interfaces, méthodes async, booléens | Préfixe `I` / suffixe `Async` / `Is`·`Has`·`Can` | `IEquipeService`, `ObtenirEquipeAsync()`, `IsActive` |
| Paramètres et variables locales | camelCase | `equipeId`, `nombreEquipes` |
| Champs privés | `_camelCase` | `_equipeRepository` |

---

## Requirements

- donet 10 or older
- C# 14 or older
