import { useEffect, useMemo, useState } from 'react';
import FloorPlan from './FloorPlan';
import plan from '../../shared/plan-n3.json';

async function request(path, token) {
  const response = await fetch(`/api/${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Erreur lors du calcul des prédictions.');
  return data;
}
function fmt(value) {
  return value == null ? '—' : `${new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 }).format(value)} °C`;
}
function dateLabel(value) {
  return new Date(`${value}T12:00:00`).toLocaleDateString('fr-FR', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' });
}
function defaultDate() {
  const now = new Date();
  const year = now.getFullYear();
  return `${year}-07-01`;
}
export default function PredictionDashboard({ session, onBack, logout, onShowTemperatures }) {
  const [rooms, setRooms] = useState([]);
  const [room, setRoom] = useState('');
  const [date, setDate] = useState(defaultDate());
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [hour, setHour] = useState(12);
  const [selectedPlanRoom, setSelectedPlanRoom] = useState('');

  async function load(chosenDate = date, chosenRoom = room) {
    if (!chosenDate) { setError('Choisis une date entre juillet et décembre.'); return; }
    const month = Number(chosenDate.slice(5, 7));
    if (month < 7 || month > 12) { setError('Choisis une date entre juillet et décembre.'); return; }
    setBusy(true); setError(''); setData(null);
    try {
      const query = new URLSearchParams({ date: chosenDate, ...(chosenRoom ? { room: chosenRoom } : {}) });
      const result = await request(`predictions/temperatures?${query}`, session.token);
      setData(result);
      setRooms(previous => [...new Set([...previous, ...result.predictions.map(item => item.room)])].sort());
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  useEffect(() => { load(defaultDate(), ''); }, [session.token]);
  const rows = data?.predictions || [];
  const planTemperatures = useMemo(() => {
    const result = {};
    for (const item of rows) {
      const point = item.hourly?.[hour];
      const value = point?.temperature ?? item.temperature;
      const match = plan.rooms.find(r => r.code === item.room || r.name === item.room || r.id === item.room);
      if (match && Number.isFinite(value)) result[match.code] = value;
    }
    return result;
  }, [rows, hour]);
  const selectedRow = rows.find(item => item.room === selectedPlanRoom) || rows[0];
  const chartValues = selectedRow?.hourly || [];
  const chartMin = Math.min(...chartValues.map(p => p.temperature).filter(Number.isFinite), 0);
  const chartMax = Math.max(...chartValues.map(p => p.temperature).filter(Number.isFinite), 1);
  const chartRange = Math.max(1, chartMax - chartMin);
  const chartPoints = chartValues.map((p, i) => `${30 + i * 24},${125 - ((p.temperature - chartMin) / chartRange) * 95}`).join(' ');
  return <main className="prediction-page">
    <header><div><span className="brand">E /</span><b>ESEO <span className="muted">· Prédiction thermique</span></b></div>
      <div className="header-actions"><button className="secondary" onClick={onBack}>Retour aux températures</button><button className="secondary" onClick={logout}>Déconnexion · {session.username}</button></div>
    </header>
    <section className="prediction-content">
      <div className="prediction-intro"><span className="eyebrow">MACHINE LEARNING · MÉTÉO</span><h1>Prévoir une journée</h1>
        <p>Choisis une date de juillet à décembre. Le modèle utilise les mesures de janvier à juin de ton fichier et les données météo Open-Meteo. Une seule journée est calculée à la demande.</p>
      </div>
      <div className="prediction-controls">
        <label>Journée à prévoir<input type="date" value={date} min={`${new Date().getFullYear()}-07-01`} max={`${new Date().getFullYear()}-12-31`}
          onChange={e => { setDate(e.target.value); setData(null); setError(''); }} /></label>
        <label>Salle<select value={room} onChange={e => { setRoom(e.target.value); setData(null); }}><option value="">Toutes les salles</option>{rooms.map(name => <option key={name} value={name}>{name}</option>)}</select></label>
        <button onClick={() => load()} disabled={busy}>{busy ? 'Calcul de la journée…' : 'Calculer la prévision'}</button>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {busy && <p>Calcul d'une seule journée… La première demande peut nécessiter le chargement du fichier et de la météo historique.</p>}
      {!busy && data && <>
        <div className="prediction-meta"><span>Journée : {dateLabel(date)}</span><span>Historique : {data.history_start || '—'} → {data.history_end || '—'}</span><span>Météo : {data.weather_mode}</span></div>
        <button className="show-predictions-button" onClick={() => onShowTemperatures?.(data, date)}>Afficher ces estimations dans l’onglet Températures</button>
        <section className="prediction-visuals">
          <div className="prediction-panel">
            <div className="prediction-panel-heading"><div><h2>Plan thermique · N3</h2><p>Couleurs et valeurs à {String(hour).padStart(2, '0')} h 00</p></div><span className="prediction-tag">ESTIMATIONS</span></div>
            <FloorPlan selected={selectedPlanRoom} disabled={true} onSelect={setSelectedPlanRoom} temperatures={planTemperatures} />
            <div className="prediction-legend"><span>Froid</span><i /><span>Chaud</span><small>Les salles sans correspondance de nom restent sans valeur.</small></div>
          </div>
          <div className="prediction-panel">
            <div className="prediction-panel-heading"><div><h2>Évolution sur 24 h</h2><p>{selectedRow?.room || 'Sélectionne une salle dans la liste'}</p></div></div>
            <label className="prediction-room-select">Salle suivie<select value={selectedRow?.room || ''} onChange={e => setSelectedPlanRoom(e.target.value)}>{rows.map(item => <option key={item.room} value={item.room}>{item.room}</option>)}</select></label>
            <svg className="prediction-chart" viewBox="0 0 620 160" role="img" aria-label="Courbe des températures estimées de 0 à 23 heures">
              {[0,1,2,3].map(i => <g key={i}><line x1="30" x2="582" y1={30+i*30} y2={30+i*30} stroke="#dce5e8" strokeDasharray="4 4"/><text x="4" y={34+i*30} fontSize="10" fill="#60747d">{(chartMax - i*chartRange/3).toFixed(1)}°</text></g>)}
              {chartValues.length > 0 && <polyline points={chartPoints} fill="none" stroke="#16848b" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round"/>}
              {chartValues.map((p,i) => <g key={p.hour}><circle cx={30+i*24} cy={125-((p.temperature-chartMin)/chartRange)*95} r={hour===i?5:2.5} fill={hour===i?'#d97706':'#16848b'}/>{i%3===0 && <text x={30+i*24} y="148" textAnchor="middle" fontSize="10" fill="#60747d">{String(i).padStart(2,'0')}h</text>}</g>)}
            </svg>
            <p className="prediction-chart-note">Profil horaire estimé à partir des écarts horaires observés dans l'historique, recentré sur la moyenne journalière prédite.</p>
          </div>
        </section>
        <section className="prediction-timeline"><label htmlFor="prediction-hour">Heure affichée sur le plan : <strong>{String(hour).padStart(2, '0')} h 00</strong></label><input id="prediction-hour" type="range" min="0" max="23" step="1" value={hour} onChange={e => setHour(Number(e.target.value))}/><div className="prediction-hour-labels"><span>00 h</span><span>06 h</span><span>12 h</span><span>18 h</span><span>23 h</span></div></section>
        <div className="prediction-table-wrap"><table className="prediction-table"><thead><tr><th>Salle</th><th>Date</th><th>Moyenne journalière estimée</th><th>Profil horaire</th><th>Météo extérieure moyenne</th><th>Min / max ext.</th></tr></thead>
          <tbody>{rows.map((item, i) => <tr key={`${item.room}-${item.date}-${i}`}><td>{item.room}</td><td>{dateLabel(item.date)}</td><td><strong>{fmt(item.temperature)}</strong><small className="prediction-tag">Estimation IA · moyenne journalière</small></td><td><small>24 points horaires estimés</small><strong>{fmt(item.hourly?.[hour]?.temperature)}</strong></td><td>{fmt(item.weather?.mean)}</td><td>{fmt(item.weather?.min)} / {fmt(item.weather?.max)}</td></tr>)}
            {!rows.length && <tr><td colSpan="6">Aucune prédiction disponible. Vérifie le fichier source et la connexion à Open-Meteo.</td></tr>}</tbody></table>
        </div>
      </>}
      <p className="prediction-footnote">Pour une date située à plus de 15 jours dans le futur, Open-Meteo ne peut pas fournir une prévision météo exacte : le système utilise alors une moyenne climatique du mois. Le résultat est une estimation de la température moyenne de chaque salle sur la journée, le profil horaire est une estimation dérivée des écarts horaires historiques et ne constitue pas une mesure réelle ni une prévision horaire indépendante.</p>
    </section>
  </main>;
}
