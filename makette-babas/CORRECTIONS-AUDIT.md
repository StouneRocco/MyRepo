# Corrections de l'audit — 20 octobre 2026

## Ajout du 22 octobre : présence issue de `babas`

Le module de consultation des badgeages et le fichier `ressources/badgeages.csv`
ont été repris de `babas` (`d78aa8e`) et adaptés à l'application Axel corrigée.
L'intégration conserve son frontend, ses plans, son authentification, sa
synchronisation thermique et sa calibration. Le module Présence dispose de
filtres locaux étage/jour/heure, d'un plan coloré, d'une sélection de salle et
d'un histogramme horaire. Il ne commande pas la projection thermique.

Le lecteur réutilise le catalogue de plans existant, ne dépend pas d'Internet
et invalide ses agrégats lorsque le fichier local change. Les totaux du fichier
fourni sont réconciliés dans les tests ; aucune personne unique ni occupation
instantanée n'est déduite des passages.

Validation de l'intégration : **102 tests réussis** (59 backend, 28 récepteur,
15 JavaScript), compilation réussie et parcours navigateur sur une instance
isolée : connexion fictive, passage Températures/Présence, plans N3/N4,
sélection d'une salle et filtre horaire. Aucun compte ou réglage réel n'a été
modifié pour ces essais.

## Livraison du 20 octobre

Cette livraison prolonge l'audit du commit `6296441`. Le tableau distingue les corrections réalisées des chantiers partiels ; une modification logicielle ne vaut pas validation physique sur la maquette.

## Changements livrés

- Le pilote survit aux erreurs MongoDB/réseau, sauvegarde avant de publier une modification et renvoie la vue toutes les deux secondes. La lecture est mise en pause au redémarrage, ses écritures sont espacées de cinq secondes et « Réessayer » force un nouvel envoi.
- Un diagnostic du récepteur distingue caméra, rendu, calibration et visibilité des marqueurs. Les exceptions du pilote sont journalisées. La disponibilité du rendu est surveillée ; la connexion HDMI et l'image physiquement projetée restent des contrôles matériels.
- Les commandes rapides sont fusionnées par champ, une seule lecture de synchronisation est en vol et les appels API expirent après dix secondes. La page signale une perte de synchronisation et réduit son polling lorsqu'elle est masquée.
- La calibration web transmet une révision attendue : un réglage devenu ancien est rejeté avec un conflit au lieu d'écraser les autres coins. La fermeture du panneau retire le plan/guide ; les déplacements restent temporaires tant que « Enregistrer » n'est pas utilisé. Le retour automatique est sauvegardé et son état de préparation est actualisé.
- Les quatre observations ArUco doivent provenir d'une même image et former un quadrilatère cohérent. Un repère masqué ne contribue plus avec une ancienne position. Les quatre pertes sont signalées ; la détection inutile en manuel est supprimée.
- Les mesures numériques sont séparées de l'activation de la heatmap. La moyenne indique sa couverture, les statistiques précisent leur période et la règle du créneau de cinq minutes est affichée.
- Les heures inexistantes au passage à l'heure d'été ne sont plus interpolées. L'import refuse les heures locales inexistantes ou ambiguës sans offset explicite. La double heure d'automne n'a pas encore de représentation séparée dans l'interface.
- Les caches de journées et du calendrier expirent après trente secondes ; l'interface recharge ses données toutes les trente secondes. Un import devient visible sans redémarrage, généralement sous trente secondes côté projection et jusqu'à environ une minute côté interface.
- L'import propose analyse sans écriture, rapport JSON avec empreinte SHA-256, couverture mois/salle et exemples de lignes rejetées, choix de feuille XLSX et remplacement explicite des mesures existantes. Le comportement par défaut reste la conservation des valeurs déjà importées.
- L'inscription ferme après création du premier compte. Les comptes existants conservent leurs droits ; les nouvelles inscriptions volontairement ouvertes créent des lecteurs. Les commandes sont protégées côté serveur et désactivées dans l'interface des lecteurs. Les sessions sont révocables par compte, les comptes supprimés/désactivés sont refusés et les tentatives de connexion sont limitées.
- Les API refusent les formats d'entrée inattendus, retournent des erreurs JSON et de véritables 404 sous `/api`. Les exceptions MongoDB deviennent des 503. La taille des requêtes et les identifiants/mots de passe sont bornés ; une clé JWT trop courte est refusée.
- Le lanceur affiche son dossier/commit, attend MongoDB, reconstruit toujours l'interface, évite un deuxième backend, conserve les journaux du récepteur et arrête uniquement celui qu'il a créé. Un récepteur déjà lancé est conservé et doit être redémarré séparément après mise à jour.
- Le proxy Vite détecte la configuration HTTPS locale ; sa vérification TLS reste activée. Les erreurs d'installation PWA sont affichées. Un port 5080 occupé ne bloque plus le serveur principal.
- Sauvegarde/restauration BSON via JSON compressé ; restauration autorisée uniquement dans une autre base vide. Aucun export des clés privées n'est effectué par cette commande.
- Vite, son plugin, source-map-js, Flask, PyMongo, PyJWT et requests ont été mis à jour. Les contrôles `npm audit` et `pip-audit` des versions installées ne signalent plus de vulnérabilité connue au moment du contrôle.
- Une CI GitHub exécute les tests Python/JavaScript et la compilation ; des tests couvrent les pannes, pertes de repères, conflits de calibration, droits et restauration.

## Suivi des 33 constats

| Audit | État de cette livraison | Limite ou prochaine étape |
|---|---|---|
| A01 | Corrigé et testé | Verrou encore conservé pendant certaines écritures MongoDB |
| A02 | Corrigé côté protocole et testé | Vérifier arrêt/reprise sur le projecteur réel |
| A03 | Partiel | Lanceur amélioré ; supervision permanente et nettoyage OpenCV après crash à compléter |
| A04 | À faire | Serveur de développement et pilote unique en mémoire ; ne pas déployer plusieurs workers |
| A05 | Partiel | Diagnostics et logs ; rotation et classification exhaustive à compléter |
| A06 | Corrigé et testé | Mesurer la latence réelle en Wi-Fi dégradé |
| A07 | À faire | Les opérateurs conservent la règle « dernière commande reçue » ; pas de réservation du pilote |
| A08 | Partiel | Sauvegarde espacée et reprise en pause ; GET active encore le pilote |
| A09 | Corrigé côté calcul et testé | Recette physique de masquage des quatre repères |
| A10 | Corrigé pour le client web mis à jour et testé | Anciens clients sans révision restent compatibles ; pas de réservation exclusive |
| A11 | Corrigé dans le parcours de fermeture | Valider tactile/Échap ; fermeture brutale de l'onglet sans nettoyage encore possible |
| A12 | Corrigé et testé pour la persistance | Essai de redémarrage avec matériel à effectuer |
| A13 | À faire | Profils optiques/écrans et calibration de la caméra PC |
| A14 | Partiel | Détection supprimée en manuel ; profilage et caches de rendu restants |
| A15 | Corrigé et testé | Vérification visuelle finale sur projection |
| A16 | Partiel | Heures inexistantes supprimées ; double heure d'automne toujours fusionnée dans la grille |
| A17 | Clarifié | La règle reste dernière valeur du créneau, pas strictement dernière observation antérieure à t |
| A18 | Partiel | Couverture et période explicites ; décision métier sur pondération/seuil minimal restante |
| A19 | Partiel | Rapports et remplacement explicite ; pas de registre transactionnel/provenance complète ni rapport après interruption |
| A20 | Corrigé par expiration bornée | Une invalidation immédiate par version d'import serait plus précise |
| A21 | Partiel | Calendrier mis en cache ; performances réelles et validation des jours disponibles restantes |
| A22 | Partiel | Limite N3 explicitée ; validation automatique catalogue/base à ajouter |
| A23 | Corrigé et testé | Inscription contrôlée, lecteurs/opérateurs ; pas d'administration graphique |
| A24 | Corrigé pour les cas audités et testé | Pas de schéma formel exhaustif de toutes les routes historiques |
| A25 | Partiel | Révocation/compte/claims renforcés ; JWT reste dans localStorage |
| A26 | Partiel | Lanceur ne dépend plus du config TLS ; adresse stable, renouvellement et vérification mkcert restants |
| A27 | Corrigé pour les versions contrôlées | Refaire les audits périodiquement ; pas de garantie d'absence de toute vulnérabilité |
| A28 | Corrigé | Toujours lancer le dossier contenant les corrections |
| A29 | Partiel | Aller-retour testé sur échantillon BSON ; restauration complète et sauvegarde protégée des réglages/TLS à pratiquer |
| A30 | Partiel | CI et tests de régression ajoutés ; parcours navigateur automatisés restants |
| A31 | Corrigé dans la configuration | Node doit reconnaître le CA local ; voir README |
| A32 | Partiel | Erreurs réseau/installation explicites ; recette tactile/accessibilité et PWA réelle restante |
| A33 | Partiel | Tracking extrait et guides complétés ; restructuration plus large restante |

## Activation et validation

Validation locale de cette livraison : **92 tests réussis** (52 backend, 28 projection/récepteur, 12 JavaScript), compilation Vite réussie, `pip check` réussi, syntaxe du lanceur PowerShell validée et `git diff --check` sans erreur. `npm audit` et l'audit des paquets Python installés n'ont signalé aucune vulnérabilité connue après les mises à jour. La CI est ajoutée mais n'a pas encore été exécutée sur GitHub.

Les modifications sont dans le dossier de travail Codex. Le serveur précédemment lancé depuis `C:\Axel\School\ESEO I3\makette` utilise une autre copie : il ne reçoit pas automatiquement ces fichiers. L'ancienne instance backend de ce dossier de travail a été fermée pour libérer PyMongo pendant sa mise à jour ; les autres instances n'ont pas été remplacées par cet audit.

Pour charger cette version, arrêter le serveur et le récepteur précédents, puis utiliser les commandes de mise à jour du README depuis le dossier qui contient ces corrections. Backend et récepteur doivent être mis à jour ensemble, car le diagnostic utilise désormais `/health` sur le port 5001.

Les tests utilisent des bases simulées et un échantillon BSON temporaire ; aucun réimport des données réelles ni restauration de la base active n'a été effectué. Les essais physiques, la couverture exhaustive des six fichiers et la stabilité prolongée restent à faire selon la recette de l'audit initial.
