"""Une vue partagée et un seul pilote de projection pour tous les appareils."""
import threading
import time
import logging
import os
import json
from pathlib import Path
from functools import lru_cache

from flask import jsonify, request
from pymongo.errors import PyMongoError
from temperature_day import load_plans, daily_frame, day_bounds
from badgeage_views import BadgeageData, CSV_PATH
from electrical_views import electrical_frame
import sqlite3
PRESENCE_MAXIMUM = json.loads((Path(__file__).resolve().parent.parent/'shared'/'presence-scale.json').read_text(encoding='utf-8'))['maximum']
ELECTRICITY_MAXIMUM = json.loads((Path(__file__).resolve().parent.parent/'shared'/'electricity-scale.json').read_text(encoding='utf-8'))['maximum']


class SharedView:
    def __init__(self, collection, measurements, receiver, http):
        self.collection, self.measurements = collection, measurements
        self.receiver, self.http = receiver, http
        self.plans = load_plans()
        self.badgeages = BadgeageData(os.getenv('BADGEAGES_FILE') or CSV_PATH, self.plans)
        self.lock = threading.RLock()
        self.active = False
        self.error = None
        self.available = False
        self.last_tick = time.monotonic()
        self.rendered = -1
        self.last_send = 0
        self.last_save = 0
        self.stop_event = threading.Event()
        self.worker = None
        self.receiver_status = None
        self.last_health = 0
        self.state = dict(floor=3, day='2026-01-01', minute=0, playing=False,
                          heatmap=True, interpolate=True, roomId=None, metric='temperatures', revision=0)
        stored = collection.find_one({'_id':'shared'})
        if isinstance(stored, dict):
            try:
                self.state.update(self.validate({k:v for k,v in stored.items() if k in self.state and k!='revision'}))
            except (ValueError, TypeError):
                pass
            if type(stored.get('revision')) is int:
                self.state['revision'] = max(0, stored['revision'])+1
        # Une lecture ne reprend jamais implicitement une animation après redémarrage.
        self.state['playing'] = False
        self._frame = lru_cache(maxsize=16)(lambda floor, day, epoch: daily_frame(measurements, self.plans[floor], day))
        self.frame = lambda floor, day: self._frame(floor, day, int(time.monotonic()//30))

    def validate(self, patch):
        if not isinstance(patch,dict) or not patch or set(patch)-set(self.state) or 'revision' in patch:
            raise ValueError('Réglages de consultation invalides.')
        state = {**self.state, **patch}
        if type(state['floor']) is not int or state['floor'] not in self.plans:
            raise ValueError('Étage inconnu.')
        day_bounds(state['day'])
        if state['metric'] not in ('temperatures', 'presence', 'electricity'):
            raise ValueError('Donnée affichée inconnue.')
        if type(state['minute']) is not int or not 0 <= state['minute'] <= 1435 or state['minute']%5:
            raise ValueError('Horaire invalide.')
        if state['metric'] in ('presence', 'electricity') and state['minute'] % 60:
            raise ValueError('La donnée est affichée par heure entière.')
        if any(type(state[key]) is not bool for key in ('playing','heatmap','interpolate')):
            raise ValueError('Option invalide.')
        if state['roomId'] is not None and state['roomId'] not in {r['id'] for r in self.plans[state['floor']]['rooms']}:
            raise ValueError('Salle inconnue pour cet étage.')
        return patch

    def snapshot(self):
        with self.lock:
            return {**self.state, 'available':self.available, 'projectionError':self.error,
                    'receiverStatus':self.receiver_status}

    def update(self, patch):
        with self.lock:
            if isinstance(patch, dict) and patch.get('metric') in ('temperatures', 'presence', 'electricity') and patch['metric'] != self.state['metric']:
                patch = {**patch, 'playing': False}
                if patch['metric'] in ('presence', 'electricity'):
                    patch['minute'] = (patch.get('minute', self.state['minute']) // 60) * 60 if type(patch.get('minute', self.state['minute'])) is int else patch.get('minute')
            patch = self.validate(patch)
            candidate = {**self.state, **patch, 'revision': self.state['revision']+1}
            self.collection.replace_one({'_id':'shared'}, {'_id':'shared', **candidate}, upsert=True)
            self.state = candidate
            self.active = True
            self.last_tick = time.monotonic()
            return self.snapshot()

    def tick(self, now):
        with self.lock:
            interval = 1.0 if self.state['metric'] in ('presence', 'electricity') else .5
            if self.active and self.state['playing'] and now-self.last_tick >= interval:
                minute = self.state['minute']
                step = 60 if self.state['metric'] in ('presence', 'electricity') else 15
                minute = 0 if minute+step >= 1440 else minute+step
                candidate = {**self.state, 'minute':minute, 'revision':self.state['revision']+1}
                if now-self.last_save >= 5:
                    self.collection.replace_one({'_id':'shared'}, {'_id':'shared', **candidate}, upsert=True)
                    self.last_save = now
                self.state = candidate
                # Un cycle lent ne doit pas faire sauter les créneaux intermédiaires.
                self.last_tick = now

    def project(self, state):
        # N4 reste consultable ; la maquette physique représente N3.
        plan = self.plans[3]
        if state.get('metric') == 'electricity':
            hour = state['minute']//60
            try:
                frame = electrical_frame(3, state['day'])
                values = {code: item['hours'][hour] for code, item in frame['rooms'].items() if item['hours'][hour] is not None}
            except (OSError, sqlite3.Error, ValueError):
                values = {}
            room = next((r for r in plan['rooms'] if r['id']==state['roomId']), None) if state['floor']==3 else None
            context = dict(day=state['day'], minute=hour*60, metric='electricity', scaleMax=ELECTRICITY_MAXIMUM,
                           dataAvailable=bool(values), roomCode=room['code'] if room else None)
            response = self.http.post(self.receiver+'/project-temperatures', json={
                'temperatures': values, 'heatmap': state['heatmap'], 'context': context,
                'roomId': room['id'] if room else None}, timeout=3)
            response.raise_for_status()
            return
        if state.get('metric') == 'presence':
            frame = self.badgeages.day(3, state['day'])
            hour = state['minute']//60
            values = {r['code']: frame['rooms'][r['code']]['hours'][hour] for r in plan['rooms']} if frame else {}
            room = next((r for r in plan['rooms'] if r['id']==state['roomId']), None) if state['floor']==3 else None
            context = dict(day=state['day'], minute=hour*60, metric='presence',
                           scaleMax=PRESENCE_MAXIMUM, dataAvailable=frame is not None,
                           roomCode=room['code'] if room else None)
            response = self.http.post(self.receiver+'/project-temperatures', json={
                'temperatures':values, 'heatmap':state['heatmap'], 'context':context,
                'roomId':room['id'] if room else None}, timeout=3)
            response.raise_for_status()
            return
        frame = self.frame(3,state['day'])
        series = frame['interpolated_series'] if state['interpolate'] else frame['series']
        bucket = state['minute']//5
        values = {r['code']:series[r['id']][bucket] for r in plan['rooms'] if series[r['id']][bucket] is not None}
        room = next((r for r in plan['rooms'] if r['id']==state['roomId']),None) if state['floor']==3 else None
        daily = [v for v in series[room['id']] if v is not None] if room else []
        context = dict(day=state['day'], minute=state['minute'], roomCode=room['code'] if room else None,
                       estimated=[r['code'] for r in plan['rooms'] if state['interpolate'] and frame['estimated'][r['id']][bucket]],
                       roomStats=dict(min=min(daily) if daily else None, max=max(daily) if daily else None,
                                      mean=sum(daily)/len(daily) if daily else None))
        response = self.http.post(self.receiver+'/project-temperatures',json={
            'temperatures':values, 'heatmap':state['heatmap'], 'context':context,
            'roomId':room['id'] if room else None},timeout=3)
        response.raise_for_status()

    def start(self):
        with self.lock:
            if self.worker is None or not self.worker.is_alive():
                self.stop_event.clear()
                self.worker = threading.Thread(target=self.run, daemon=True, name='projection-driver')
                self.worker.start()

    def run(self):
        while not self.stop_event.is_set():
            try:
                self.tick(time.monotonic())
                state = self.snapshot()
                # Le renvoi périodique détecte les arrêts et restaure un récepteur redémarré.
                if self.active and (state['revision']!=self.rendered or self.error or time.monotonic()-self.last_send >= 2):
                    self.project(state)
                    if time.monotonic()-self.last_health >= 2:
                        health = self.http.get(self.receiver+'/health',timeout=2)
                        health.raise_for_status()
                        details = health.json()
                        if isinstance(details,dict):
                            age = details.get('renderAgeSeconds')
                            if age is None or age > 5:
                                raise RuntimeError('Boucle de rendu arrêtée ou non initialisée')
                            with self.lock:
                                self.receiver_status = details
                        self.last_health = time.monotonic()
                    with self.lock:
                        self.available, self.error, self.rendered = True, None, state['revision']
                        self.last_send = time.monotonic()
            except Exception as error:
                logging.exception('Échec du cycle de projection')
                with self.lock:
                    self.available = False
                    self.error = ('MongoDB indisponible. Nouvelle tentative automatique.' if isinstance(error, PyMongoError)
                                  else 'Projection indisponible. Vérifie le récepteur ; nouvelle tentative automatique.')
                self.stop_event.wait(1)
            self.stop_event.wait(.1)


def register_shared_view(app, view, auth):
    @app.route('/api/view-state', methods=['GET','POST'])
    @auth
    def view_state():
        try:
            if request.method=='POST':
                return jsonify(view.update(request.get_json(silent=True)))
            with view.lock:
                view.active = True
            return jsonify(view.snapshot())
        except (ValueError, TypeError):
            return jsonify(error='Réglages de consultation invalides.'),400
        except PyMongoError:
            return jsonify(error='MongoDB indisponible. Modification non enregistrée.'),503

    @app.post('/api/projection-retry')
    @auth
    def projection_retry():
        with view.lock:
            view.rendered = -1
            view.active = True
        return jsonify(status='retry-requested'),202
