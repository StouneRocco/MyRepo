"""Swagger UI et contrat OpenAPI, servis localement sans CDN."""
import json
from pathlib import Path

from flask import abort, jsonify, render_template, send_from_directory

SPEC_PATH=Path(__file__).with_name('openapi.json')
ASSETS={'swagger-ui.css','swagger-ui-bundle.js','LICENSE','NOTICE'}


def register_api_docs(app,dist):
    @app.get('/api/openapi.json')
    def openapi_spec():
        return jsonify(json.loads(SPEC_PATH.read_text(encoding='utf-8')))

    @app.get('/api/docs',strict_slashes=False)
    def swagger_docs():
        return render_template('api_docs.html')

    @app.get('/api/docs/assets/<filename>')
    def swagger_asset(filename):
        if filename not in ASSETS:
            abort(404)
        directory=Path(dist).resolve()/'swagger'
        if not (directory/filename).is_file():
            return jsonify(error='Fichiers Swagger absents. Exécute npm ci puis npm run build dans frontend.'),503
        return send_from_directory(directory,filename)
