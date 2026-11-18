export async function api(path, token, body) {
  const timeoutMs=String(path).startsWith('predictions/temperatures') ? 60000 : 10000;
  const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),timeoutMs);
  try {
  const response = await fetch(`/api/${path}`, {
    signal:controller.signal,
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.headers.get('content-type')?.includes('application/json')) {
    throw new Error(`Le backend ne reconnaît pas /api/${path}. Arrêtez le backend avec Ctrl+C, relancez backend/app.py depuis le dossier makette, puis actualisez avec Ctrl+F5.`);
  }
  const data = await response.json();
  if (!response.ok) throw Object.assign(new Error(data.error || 'Erreur serveur'), { status: response.status });
  return data;
  } catch(error) {
    if(error.name==='AbortError')throw new Error('Le serveur met trop de temps à répondre. Vérifie la connexion au PC.');
    throw error;
  } finally {clearTimeout(timer);}
}
