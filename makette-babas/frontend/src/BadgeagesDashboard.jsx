import { useEffect, useMemo, useState } from 'react';

async function badgeageApi(path, token) {
  const response = await fetch(`/api/${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Erreur lors du chargement des badgeages.');
  return data;
}

function fmt(value) {
  return new Intl.NumberFormat('fr-FR').format(value || 0);
}

export default function BadgeagesDashboard({ session, logout, onTemperatures }) {
  const [plans, setPlans] = useState([]);
  const [floor, setFloor] = useState(3);
  const [days, setDays] = useState([]);
  const [day, setDay] = useState('');
  const [hour, setHour] = useState('all');
  const [frame, setFrame] = useState(null);
  const [selected, setSelected] = useState(null);
  const [showRoomLabels, setShowRoomLabels] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    badgeageApi('plans', session.token)
      .then(data => { if (active) setPlans(data); })
      .catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [session.token]);

  useEffect(() => {
    let active = true;
    setDays([]); setDay(''); setFrame(null); setSelected(null);
    setLoading(true); setError('');
    badgeageApi(`badgeages/days/${floor}`, session.token)
      .then(data => {
        if (!active) return;
        setDays(data);
        setDay(data[0] || '');
        if (!data.length) setError('Aucun badgeage trouvé pour cet étage.');
      })
      .catch(err => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [floor, session.token]);

  useEffect(() => {
    if (!day) { setFrame(null); return; }
    let active = true;
    setFrame(null); setError('');
    badgeageApi(`badgeages/day/${floor}/${day}`, session.token)
      .then(data => { if (active) setFrame(data); })
      .catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [floor, day, session.token]);

  const plan = plans.find(item => item.floor === floor);
  const rooms = useMemo(() => {
    if (!plan || !frame) return [];
    return plan.rooms.map(room => ({
      ...room,
      count: hour === 'all'
        ? (frame.rooms[room.code]?.total || 0)
        : (frame.rooms[room.code]?.hours[Number(hour)] || 0),
      hours: frame.rooms[room.code]?.hours || Array(24).fill(0),
    }));
  }, [plan, frame, hour]);
  const selectedRoom = rooms.find(room => room.id === selected);
  const total = hour === 'all' ? (frame?.total || 0) : (frame?.hourTotals?.[Number(hour)] || 0);
  const maximum = Math.max(1, ...rooms.map(room => room.count));
  const bounds = plan?.bounds || [0, 0, 800, 600];

  return <main className="dashboard">
    <header>
      <div><span className="brand">E /</span><b>ESEO <span className="muted">· Badgeages</span></b></div>
      <div className="header-actions">
        <button className="secondary" onClick={onTemperatures}>Températures</button>
        <button className="secondary" onClick={logout}>Déconnexion · {session.username}</button>
      </div>
    </header>
    <section className="thermal-workspace">
      <div className="thermal-controls">
        <label>Étage
          <select value={floor} onChange={event => setFloor(Number(event.target.value))}>
            <option value={3}>N3</option><option value={4}>N4</option>
          </select>
        </label>
        <label>Journée
          <select value={day} disabled={!days.length} onChange={event => setDay(event.target.value)}>
            {days.map(value => <option key={value} value={value}>{value.split('-').reverse().join('/')}</option>)}
          </select>
        </label>
        <label>Heure
          <select value={hour} onChange={event => setHour(event.target.value)}>
            <option value="all">Toute la journée</option>
            {Array.from({length: 24}, (_, index) => <option key={index} value={index}>{String(index).padStart(2,'0')} h – {String(index).padStart(2,'0')} h 59</option>)}
          </select>
        </label>
        <label className="heat-switch"><input type="checkbox" checked={showRoomLabels} onChange={event => setShowRoomLabels(event.target.checked)}/> Code et nom des salles</label>
        <div className="projection-state">{loading ? 'Chargement des badgeages…' : `${fmt(total)} badgeages`}</div>
      </div>
      <div className="thermal-body">
        <section className="plan-view">
          <div className="plan-heading">
            <h2>Plan N{floor}</h2><span>{day ? day.split('-').reverse().join('/') : '—'}</span>
          </div>
          <div className="map">
            {plan && <svg viewBox={bounds.join(' ')} role="group" aria-label={`Badgeages des salles du niveau N${floor}`}>
              {rooms.map(room => {
                const x = room.points.reduce((sum, point) => sum + point[0], 0) / room.points.length;
                const y = room.points.reduce((sum, point) => sum + point[1], 0) / room.points.length;
                const width = Math.max(...room.points.map(point => point[0])) - Math.min(...room.points.map(point => point[0]));
                const height = Math.max(...room.points.map(point => point[1])) - Math.min(...room.points.map(point => point[1]));
                const font = Math.max(.6, Math.min(width / 5, height / 4, bounds[2] / 70));
                const ratio = room.count / maximum;
                const color = room.count === 0 ? '#edf2f4' : `rgb(${Math.round(223-215*ratio)},${Math.round(241-116*ratio)},${Math.round(239-110*ratio)})`;
                return <g key={room.id}>
                  <polygon points={room.points.map(point => point.join(',')).join(' ')}
                    style={{ fill: color, cursor: 'pointer', stroke: selected === room.id ? '#162d3d' : '#fff', strokeWidth: selected === room.id ? 2 : 0.7 }}
                    role="button" tabIndex="0" aria-label={`${room.code}, ${fmt(room.count)} badgeages`}
                    aria-pressed={selected === room.id}
                    onClick={() => setSelected(room.id)}
                    onKeyDown={event => { if (['Enter',' '].includes(event.key)) { event.preventDefault(); setSelected(room.id); } }}>
                    <title>{room.code} · {room.name} · {fmt(room.count)} badgeages</title>
                  </polygon>
                  {showRoomLabels && <><text x={x} y={y-font*1.15} textAnchor="middle" style={{fontSize: font*.68, fontWeight: 700, pointerEvents: 'none'}}>{room.code}</text><text x={x} y={y-font*.42} textAnchor="middle" style={{fontSize: font*.58, pointerEvents: 'none'}}>{room.name}</text></>}
                  <text className="room-temperature" x={x} y={y+font*.8} textAnchor="middle" style={{fontSize: font, pointerEvents: 'none'}}>{fmt(room.count)}</text>
                </g>;
              })}
              <image href={`/plans/structure/N${floor}.svg`} x="0" y="0" width="800" height="600" preserveAspectRatio="none" pointerEvents="none" aria-hidden="true" />
            </svg>}
          </div>
          <div className="heat-legend"><span>0</span><div className="legend-gradient" style={{background: 'linear-gradient(90deg, #dff1ef, #087d81)'}}/><span>{fmt(maximum)} badgeages</span></div>
        </section>
        <aside className="room-detail">
          <span className="eyebrow">{selectedRoom ? 'SALLE SÉLECTIONNÉE' : 'ACTIVITÉ DU NIVEAU'}</span>
          <h2>{selectedRoom ? selectedRoom.name : `Niveau N${floor}`}</h2>
          <p>{selectedRoom ? selectedRoom.code : `${rooms.length} salles sur le plan`}</p>
          <div className="temperature-current">
            <strong>{fmt(selectedRoom ? selectedRoom.count : total)}</strong>
            <p>{hour === 'all' ? 'Badgeages sur la journée' : `Badgeages entre ${String(hour).padStart(2,'0')} h et ${String(hour).padStart(2,'0')} h 59`}</p>
          </div>
          <h3>Répartition par heure</h3>
          <div style={{display: 'flex', alignItems: 'end', gap: 3, height: 145, margin: '12px 0 22px'}}>
            {(selectedRoom ? selectedRoom.hours : frame?.hourTotals || Array(24).fill(0)).map((value, index, values) =>
              <div key={index} title={`${String(index).padStart(2,'0')} h : ${fmt(value)}`}
                style={{flex: 1, height: `${Math.max(2, value / Math.max(1, ...values) * 100)}%`, background: hour !== 'all' && Number(hour) === index ? '#162d3d' : '#087d81', borderRadius: '3px 3px 0 0', minWidth: 0}} />
            )}
          </div>
          {selectedRoom && <button className="secondary" onClick={() => setSelected(null)}>Voir tout le niveau</button>}
          <p className="detail-caption">{error || (frame ? 'Données agrégées par salle et par heure. Les badgeages individuels ne sont pas affichés.' : 'Chargement des données…')}</p>
        </aside>
      </div>
      <div className="workspace-note">{error ? <span className="error">{error}</span> : 'Données du mois de mars, regroupées par niveau, jour, salle et heure.'}</div>
    </section>
  </main>;
}
