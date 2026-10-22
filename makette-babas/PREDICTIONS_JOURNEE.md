# Prévision d'une journée (juillet à décembre)

La page **Prédictions IA** permet de choisir une date unique entre juillet et décembre, éventuellement une salle, puis de cliquer sur **Calculer la prévision**. La page ne charge plus automatiquement la liste des jours manquants et ne calcule plus plusieurs jours à la fois.

## Sources utilisées
- Historique local : `ressources/temperature_clean.csv` s'il existe, sinon `ressources/temperature_clean.xlsx`.
- Pour imposer un CSV précis dans PowerShell avant de lancer l'application :
  `$env:TEMPERATURE_CSV = (Resolve-Path "C:\chemin\vers\temperature_clean.csv").Path`
- Météo : Open-Meteo. Pour les dates passées, l'API d'archives est utilisée. Pour les 15 prochains jours, la prévision météo est utilisée. Au-delà, l'application utilise une climatologie moyenne du mois issue des archives météo ; ce n'est pas une prévision météo exacte.

## Lancement
Reprends les étapes d'installation déjà utilisées puis relance `start-pc.ps1`. Si le backend est déjà ouvert, arrête-le avec `Ctrl+C` et redémarre-le. Dans le navigateur, fais `Ctrl+F5` pour forcer le chargement de la nouvelle interface.

La sortie correspond à une **température moyenne estimée par salle pour la journée**, et non à une courbe heure par heure. La première requête peut être plus lente, car elle doit lire et agréger le fichier historique et récupérer les données météo ; les appels météo sont ensuite mis en cache pendant la durée de vie du backend.

## Nouveau : profil horaire estimé et plan thermique

La réponse de `/api/predictions/temperatures` comprend désormais `hourly`, une liste de 24 valeurs horaires par salle. Le profil est calculé à partir des écarts entre les températures horaires observées et la moyenne de leur journée dans l'historique, puis recentré pour conserver la moyenne journalière prédite par le modèle.

Dans l'interface, la frise 00 h–23 h permet de parcourir le profil et de mettre à jour le plan thermique N3 ainsi que la valeur horaire du tableau. Une courbe affiche le profil estimé de la salle choisie.

**Important :** les points horaires sont des estimations dérivées du profil historique, pas des mesures en direct ni une prédiction météo/thermique indépendante pour chaque heure. Les salles sont reliées au plan lorsque leur nom correspond au code, au nom ou à l'identifiant d'une salle du plan N3. Les autres salles restent dans le tableau sans coloration sur ce plan.
