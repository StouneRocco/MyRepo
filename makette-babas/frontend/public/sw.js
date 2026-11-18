// Les températures et les pages restent en réseau : ne jamais figer un ancien mois.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => {
  if (event.request.mode !== 'navigate') return;
  event.respondWith(fetch(event.request, {cache:'no-store'}).catch(() => new Response(
    '<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Maquette ESEO</title><body style="font-family:system-ui;padding:2rem"><h1>Serveur indisponible</h1><p>Connecte cet appareil au même réseau que le PC et vérifie que l’application est lancée.</p><button onclick="location.reload()">Réessayer</button></body></html>',
    {headers:{'Content-Type':'text/html; charset=utf-8'},status:503}
  )));
});
