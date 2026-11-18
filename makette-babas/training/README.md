# Entraînement des modèles de température

Ce dossier contient les scripts d'entraînement, séparés du démarrage de l'application.

Depuis la racine du projet, après installation des dépendances backend :

```powershell
# Windows
backend/.venv/Scripts/python.exe training/train_models.py

# Ou, si Python est installé dans le PATH
python training/train_models.py
```

Le script lit en priorité le fichier défini par `TEMPERATURE_CSV` (par exemple
`ressources/temperature_clean.csv`), sinon `ressources/temperature_clean.xlsx`, récupère les observations météo historiques auprès d'Open-Meteo,
ne conserve que les salles dont le code commence par `03` ou `04` (3e et 4e
étages), puis entraîne un Random Forest par salle disposant d'au moins 10
journées exploitables. Toutes les autres salles sont ignorées. Les profils
horaires sauvegardés sont également limités à ces deux étages. Le script
évalue les modèles sur la partie chronologiquement la plus récente des données,
puis sauvegarde les modèles dans `trained_models/`. Les modèles précédents sont conservés ; le manifeste actif est remplacé uniquement lorsque le nouvel entraînement est terminé.

L'application ne lance jamais ce script automatiquement. Au démarrage du backend,
elle charge en mémoire les modèles `.joblib` référencés par `trained_models/manifest.json`.
Les demandes de prédiction réutilisent ces modèles sans réentraînement. Si un modèle
individuel manque, la prédiction utilise la moyenne des 21 dernières journées connues
(ou moins si l'historique est court).

Pour réentraîner après ajout de mesures, relancer la commande. Le manifeste n'est
mis à jour qu'à la fin de l'entraînement. Les fichiers `.joblib` doivent provenir
d'une source de confiance : leur chargement peut exécuter du code.


Les moyennes météo mensuelles sont également calculées pendant l'entraînement et
enregistrées dans `trained_models/manifest.json`. Ainsi, une prédiction à plus de
15 jours n'effectue pas de téléchargement d'archive pluriannuelle.
Les réponses météo unitaires sont mises en cache dans `trained_models/weather_cache/`.
