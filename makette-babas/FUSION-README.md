# Fusion des trois versions

Cette archive combine les trois projets fournis.

## Base et fonctionnalités conservées
- Base applicative et améliorations communes : `makette-Axel.zip` (branche la plus complète pour l'interface de navigation).
- Fonctionnalités de présence/badgeages, températures, projection, synchronisation de vue et électricité.
- Prévisions thermiques : moteur de prédiction entraîné de Makette Babas installé dans `backend/temperature_prediction.py` (module réellement importé par Flask), modèles `.joblib` chargés au démarrage, profils horaires et affichage des prédictions rétablis dans le plan de températures.
- Suite de tests générale et documentation d'audit reprises de `makette-main.zip`.

## Lancement
Consulter `README.md` pour la procédure habituelle. Installer les dépendances Python de `backend/requirements.txt` et celles du frontend avec `npm ci` dans `frontend/`.

La prédiction est intégrée à la vue « Températures ». Pour une date absente des mesures réelles, l'application utilise les modèles Random Forest entraînés une seule fois avec `training/train_models.py`. Les valeurs horaires sont des estimations dérivées du profil historique, pas des mesures.

## Vérifications réalisées
- Syntaxe Python vérifiée sur les fichiers backend, projector et shared.
- Le lanceur de tests Python a été démarré, mais les tests nécessitant Flask n'ont pas pu s'exécuter dans l'environnement de préparation car Flask n'y était pas installé. Les tests indépendants exécutés par le lanceur ont réussi.
- La compilation frontend n'a pas été validée ici : l'installation npm a été interrompue par la limite de temps de l'environnement.
- Les trois archives d'origine ne sont pas modifiées.
