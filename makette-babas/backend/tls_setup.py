"""Distribution du seul certificat PUBLIC pour installer l'autorité locale."""
import hashlib
import json
import os
import ssl
from pathlib import Path

from flask import Flask, send_file, render_template_string


def load_tls_settings(directory=None, environ=None):
    """Même configuration pour python app.py et le lanceur, quel que soit le dossier courant."""
    directory = Path(directory) if directory is not None else Path(__file__).resolve().parent / '.tls'
    environ = os.environ if environ is None else environ
    certificate, key = environ.get('TLS_CERT_FILE'), environ.get('TLS_KEY_FILE')
    explicit = bool(certificate or key)
    if explicit:
        if not certificate or not key:
            raise RuntimeError('TLS_CERT_FILE et TLS_KEY_FILE doivent être définis ensemble.')
    else:
        certificate, key = directory/'server-cert.pem', directory/'server-key.pem'
        if not certificate.exists() and not key.exists():
            return {'certificate':None,'key':None,'ca':None,'host':'localhost'}
        if not certificate.exists() or not key.exists():
            raise RuntimeError('Configuration HTTPS incomplète dans backend/.tls. Relance setup-https.ps1.')
    certificate, key = Path(certificate).resolve(), Path(key).resolve()
    if not certificate.is_file() or not key.is_file():
        raise RuntimeError('Le certificat HTTPS ou sa clé est introuvable. Vérifie TLS_CERT_FILE et TLS_KEY_FILE.')
    ca, host = environ.get('TLS_CA_FILE'), environ.get('TLS_PUBLIC_HOST')
    if not explicit:
        public_ca=directory/'maquette-ca.crt'
        if public_ca.is_file():
            ca=str(public_ca.resolve())
        config=directory/'config.json'
        if not host and config.is_file():
            host=json.loads(config.read_text(encoding='utf-8-sig')).get('hostAddress')
    return {'certificate':str(certificate),'key':str(key),'ca':ca,'host':host or 'localhost'}


def certificate_fingerprint(path):
    der = ssl.PEM_cert_to_DER_cert(Path(path).read_text(encoding='ascii'))
    digest = hashlib.sha256(der).hexdigest().upper()
    return ':'.join(digest[index:index+2] for index in range(0,len(digest),2))


def create_certificate_app(certificate, host):
    certificate = Path(certificate).resolve()
    app = Flask('installation-certificat')
    fingerprint = certificate_fingerprint(certificate)

    @app.get('/')
    def instructions():
        return render_template_string('''<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Installer Maquette ESEO</title>
<style>body{font:16px system-ui;max-width:700px;margin:40px auto;padding:20px;color:#18313c}a{color:#087d81}code{word-break:break-all}</style>
<h1>Installer Maquette ESEO</h1>
<ol><li><a href="/maquette-ca.crt">Télécharger le certificat public du PC</a>.</li>
<li>Dans les paramètres Android, rechercher « Installer un certificat », puis choisir « Certificat CA » et sélectionner <b>maquette-ca.crt</b>.
Cela ajoute l'autorité locale de ce PC aux certificats reconnus par la tablette.</li>
<li>Fermer puis rouvrir Chrome et accéder à <a href="https://{{ host }}:5000/">https://{{ host }}:5000</a>.</li>
<li>Dans le menu Chrome, choisir « Installer l'application », puis ouvrir cette nouvelle icône.</li></ol>
<p>Empreinte SHA-256 du certificat, à comparer avec celle affichée sur le PC :</p><code>{{ fingerprint }}</code>
<p>Cette page sert uniquement le certificat public. Les clés privées restent sur le PC.</p></html>''',host=host,fingerprint=fingerprint)

    @app.get('/maquette-ca.crt')
    def public_certificate():
        return send_file(certificate,mimetype='application/x-x509-ca-cert',as_attachment=True,download_name='maquette-ca.crt')

    @app.after_request
    def prevent_cache(response):
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        return response

    return app
