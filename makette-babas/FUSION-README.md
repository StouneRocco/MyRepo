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


## Prévision électrique intégrée

La prévision électrique est désormais accessible directement depuis l'espace **Électricité**, via le sélecteur **Consommation / Prévision IA**. En mode Prévision IA, le modèle calcule automatiquement le profil horaire pour la date et l'étage sélectionnés, puis colore le même plan par salle. Le changement de date ou d'étage relance le calcul ; il n'y a plus de page ni d'onglet séparé pour la prédiction.

### Affichage électrique automatique selon la date

L'onglet **Électricité** conserve une seule interface. À chaque changement de date, le frontend lit les bornes `first` et `last` des mesures électriques importées : une date comprise dans cette période affiche les mesures historiques ; une date antérieure ou postérieure déclenche automatiquement `/api/predictions/electricity` et affiche les prévisions directement sur le plan. Aucun sous-onglet « Consommation / Prévision » n'est nécessaire.

Le modèle de prévision doit être généré à partir de la base BOS configurée avec `python training/train_electricity.py` (après import des données électriques).
