import { useEffect, useMemo, useRef, useState } from 'react';
import { createViewSync } from './viewSync';
import { api } from './api';
import AppHeader from './AppHeader';
import RoomPicker from './RoomPicker';
import ProjectionCalibration from './ProjectionCalibration';
import {badgeageRooms,badgeageSelection,presenceSummary,presenceHourLabel,presenceColor,PRESENCE_MAXIMUM,PRESENCE_MINIMUM,presenceGradient} from './presence';

function fmt(value) {
  return new Intl.NumberFormat('fr-FR',{maximumFractionDigits:1}).format(value ?? 0);
}

export default function BadgeagesDashboard({ session, logout, onSelect, onMetric }) {
  const canControl=session.role!=='viewer';
  const [plans, setPlans] = useState([]);
  const [floor, setFloor] = useState(3);
  const [days, setDays] = useState([]);
  const [day, setDay] = useState('');
  const [hour, setHour] = useState(0);
  const [playing,setPlaying]=useState(false);
  const [frame, setFrame] = useState(null);
  const [selected, setSelected] = useState(null);
  const [showRoomLabels, setShowRoomLabels] = useState(false);
  const [error, setError] = useState('');
  const [loadingDays, setLoadingDays] = useState(true);
  const [loadingFrame,setLoadingFrame]=useState(false);
  const [ready,setReady]=useState(false);
  const [projection,setProjection]=useState(null);
  const view=useRef({floor:3,day:'',minute:0,playing:false,roomId:null,metric:'presence'});
  const sync=useRef(null);
  function applyView(data){
    view.current={...view.current,...data};
    setFloor(data.floor);setDay(data.day);setHour(Math.floor(data.minute/60));
    setPlaying(data.playing);setSelected(data.roomId);setReady(true);setProjection(data);
    if(data.metric)onMetric(data.metric);
  }
  if(!sync.current)sync.current=createViewSync(body=>api('view-state',session.token,body),applyView,
    error=>{if(error.status===401)logout();else setError(`Synchronisation interrompue : ${error.message}`);});
  function changeView(patch){
    if(!canControl)return;
    applyView({...view.current,...patch});sync.current.change(patch);
  }
  useEffect(()=>{
    let active=true,timer;
    async function refresh(){await sync.current.refresh();if(active)timer=setTimeout(refresh,document.hidden?3000:500);}
    refresh();
    return()=>{active=false;clearTimeout(timer);sync.current.dispose();};
  },[session.token]);

  useEffect(() => {
    let active = true;
    api('plans', session.token)
      .then(data => { if (active) setPlans(data); })
      .catch(err => { if (active) {if(err.status===401)logout();else setError(err.message);} });
    return () => { active = false; };
  }, [session.token]);

  useEffect(() => {
    let active = true;
    if(!ready)return;
    setDays([]); setFrame(null);
    setLoadingDays(true); setError('');
    api(`badgeages/days/${floor}`, session.token)
      .then(data => {
        if (!active) return;
        setDays(data);
        if(data.length&&!data.includes(view.current.day)&&canControl&&view.current.metric==='presence')
          changeView({day:data[0],minute:0,playing:false});
        if (!data.length) setError('Aucun badgeage trouvé pour cet étage.');
      })
      .catch(err => { if (active) {if(err.status===401)logout();else setError(err.message);} })
      .finally(() => { if (active) setLoadingDays(false); });
    return () => { active = false; };
  }, [floor, session.token, ready]);

  useEffect(() => {
    if (!day) { setFrame(null); setLoadingFrame(false); return; }
    let active = true;
    setFrame(null); setError(''); setLoadingFrame(true);
    api(`badgeages/day/${floor}/${day}`, session.token)
      .then(data => { if (active) setFrame(data); })
      .catch(err => { if (active) {if(err.status===401)logout();else setError(err.message);} })
      .finally(()=>{if(active)setLoadingFrame(false);});
    return () => { active = false; };
  }, [floor, day, session.token]);

  const plan = plans.find(item => item.floor === floor);
  const currentFrame=frame?.floor===floor&&frame?.day===day?frame:null;
  const rooms=useMemo(()=>badgeageRooms(plan,currentFrame,hour),[plan,currentFrame,hour]);
  const {selectedRoom,total,distribution}=badgeageSelection(rooms,currentFrame,selected,hour);
  const bounds=plan?.bounds||[0,0,800,600];
  const loading=loadingDays||loadingFrame;
  const stats=presenceSummary(distribution);
  const activeRooms=rooms.filter(room=>room.count>0).length;
  const hourLabel=presenceHourLabel(hour);
  function chooseHour(value){changeView({playing:false,minute:Number(value)*60});}
  function chooseRoom(roomId){changeView({roomId});}


  return <main className="dashboard presence-dashboard">
    <AppHeader section="presence" onSelect={onSelect} session={session} logout={logout}/>
    <section className="thermal-workspace">
      <div className="thermal-controls">
        <label>Étage
          <select disabled={!canControl||!ready} value={floor} onChange={event => changeView({floor:Number(event.target.value),roomId:null,playing:false,minute:0})}>
            <option value={3}>N3</option><option value={4}>N4</option>
          </select>
        </label>
        <label>Journée
          <input type="date" value={day} min={days[0]} max={days[days.length-1]} disabled={!days.length||!canControl}
            onChange={event=>{
              if(days.includes(event.target.value))changeView({day:event.target.value,minute:0,playing:false});
              else if(event.target.value)setError('Aucun badgeage disponible pour cette journée.');
            }}/>
        </label>
        <label className="heat-switch"><input type="checkbox" checked={showRoomLabels} onChange={event => setShowRoomLabels(event.target.checked)}/> Code et nom des salles</label>
        <div className="projection-state">{floor!==3?'N4 en consultation · projection N3 uniquement':projection?.available?'Projection des badgeages':projection?.projectionError||'Connexion au projecteur…'}</div>
        <ProjectionCalibration disabled={!canControl} token={session.token}
          request={(path,body)=>api(path,session.token,body)} onSuccess={()=>sync.current.refresh()}/>
      </div>
      <div className="thermal-body">
        <section className="plan-view">
          <div className="plan-heading">
            <h2>Plan N{floor}</h2><span>{day ? day.split('-').reverse().join('/') : '—'} · {hourLabel}</span>
          </div>
          <div className="map">
            {plan && <svg viewBox={bounds.join(' ')} role="group" aria-label={`Badgeages des salles du niveau N${floor}`}>
              {rooms.map(room => {
                const x = room.points.reduce((sum, point) => sum + point[0], 0) / room.points.length;
                const y = room.points.reduce((sum, point) => sum + point[1], 0) / room.points.length;
                const width = Math.max(...room.points.map(point => point[0])) - Math.min(...room.points.map(point => point[0]));
                const height = Math.max(...room.points.map(point => point[1])) - Math.min(...room.points.map(point => point[1]));
                const font = Math.max(.6, Math.min(width / 5, height / 4, bounds[2] / 70));
                const color = presenceColor(room.count);
                return <g key={room.id}>
                  <polygon points={room.points.map(point => point.join(',')).join(' ')}
                    className={`room ${selected===room.id?'selected':''}`} style={{fill:color}}
                    role="button" tabIndex="0" aria-label={`${room.code}, ${fmt(room.count)} badgeages`}
                    aria-pressed={selected === room.id}
                    onClick={() => chooseRoom(room.id)}
                    onKeyDown={event => { if (['Enter',' '].includes(event.key)) { event.preventDefault(); chooseRoom(room.id); } }}>
                    <title>{room.code} · {room.name} · {fmt(room.count)} badgeages</title>
                  </polygon>
                  {showRoomLabels && <><text x={x} y={y-font*1.15} textAnchor="middle" style={{fontSize: font*.68, fontWeight: 700, pointerEvents: 'none'}}>{room.code}</text><text x={x} y={y-font*.42} textAnchor="middle" style={{fontSize: font*.58, pointerEvents: 'none'}}>{room.name}</text></>}
                  <text className="room-temperature" x={x} y={y+font*.8} textAnchor="middle" style={{fontSize: font, pointerEvents: 'none'}}>{fmt(room.count)}</text>
                </g>;
              })}
              <image href={`/plans/structure/N${floor}.svg`} x="0" y="0" width="800" height="600" preserveAspectRatio="none" pointerEvents="none" aria-hidden="true" />
            </svg>}
          </div>
          <div className="heat-legend"><span>{PRESENCE_MINIMUM}</span><div className="legend-gradient" style={{background:presenceGradient}}/><span>{PRESENCE_MAXIMUM} badgeages / heure</span></div>
        </section>
        <aside className="room-detail">
          <RoomPicker rooms={plan?.rooms||[]} selected={plan?.rooms.find(room=>room.id===selected)||null}
            onSelect={room=>chooseRoom(room?.id||null)} disabled={!currentFrame||!canControl}/>
          <div className="detail-heading">
            <span className="eyebrow">{selectedRoom?'SALLE SÉLECTIONNÉE':'VUE GLOBALE'}</span>
            <h2>{selectedRoom?.name||`Étage N${floor}`}</h2>
            <p>{selectedRoom?.code||`${activeRooms}/${rooms.length} salles avec un badgeage à cet horaire`}</p>
          </div>
          <div className="temperature-current">
            <strong>{currentFrame?fmt(selectedRoom?selectedRoom.count:total):'—'} <small>badgeages</small></strong>
            <p>{selectedRoom?'Passages dans la salle':'Passages dans l’étage'} · {hourLabel} – {String(hour).padStart(2,'0')}:59<br/>
              {currentFrame?'Comptage des passages enregistrés':loading?'Chargement des données…':'Aucune journée chargée'}</p>
          </div>
          <div className="temperature-stats">
            <div><span>Total du jour</span><b>{currentFrame?fmt(stats.total):'—'}</b></div>
            <div><span>Moyenne / heure</span><b>{currentFrame?fmt(stats.mean):'—'}</b></div>
            <div><span>Pic horaire</span><b>{currentFrame?fmt(stats.peak):'—'}</b></div>
          </div>
          <p className="detail-caption">{selectedRoom?'Évolution de la salle':'Évolution de l’étage'} · {day?day.split('-').reverse().join('/'):'—'}</p>
          <div className="presence-chart" role="group" aria-label="Badgeages enregistrés par heure ; choisir une barre pour filtrer le plan">
            {distribution.map((value,index,values)=><button key={index} type="button" className="presence-bar"
              disabled={!currentFrame||!canControl} aria-pressed={hour===index}
              aria-label={`${String(index).padStart(2,'0')} h : ${fmt(value)} badgeages`}
              title={`${String(index).padStart(2,'0')} h : ${fmt(value)}`}
              style={{height:`${Math.max(2,value/Math.max(1,...values)*100)}%`}}
              onClick={()=>chooseHour(index)}/>)}
          </div>
          <div className="presence-chart-labels" aria-hidden="true"><span>00 h</span><span>12 h</span><span>23 h</span></div>
          <details><summary>Historique de la journée</summary><div className="history-table"><table>
            <thead><tr><th>Horaire</th><th>Badgeages</th></tr></thead>
            <tbody>{distribution.map((value,index)=><tr key={index}><td>{presenceHourLabel(index)}</td><td>{currentFrame?fmt(value):'—'}</td></tr>)}</tbody>
          </table></div></details>
          {selectedRoom&&<button className="secondary" disabled={!canControl} onClick={()=>chooseRoom(null)}>Revenir à la vue globale</button>}
          <p className="detail-caption">Le total et les statistiques portent sur la journée ; le nombre principal correspond à l’heure choisie.</p>
        </aside>
      </div>
      <section className="timeline">
        <div className="timeline-top">
          <button disabled={!currentFrame||!canControl} className={playing?'pause':''} onClick={()=>changeView({playing:!playing})}>{playing?'Ⅱ Pause':'▶ Lire la journée'}</button>
          <div><b>{hourLabel}</b><span>{playing?'Lecture en boucle · 1 heure par étape':'Déplacez le curseur pour explorer la journée'}</span></div>
          <button className="secondary" disabled={!currentFrame||!canControl} onClick={()=>chooseHour(0)}>Recommencer</button>
        </div>
        <input aria-label="Horaire de présence" type="range" min="0" max="23" step="1" value={hour} disabled={!currentFrame||!canControl} onChange={event=>chooseHour(event.target.value)}/>
        <div className="time-ticks">{['00:00','06:00','12:00','18:00','23:00'].map(value=><span key={value}>{value}</span>)}</div>
      </section>
      <div className="workspace-note" aria-live="polite">{error&&<span className="error" role="alert">{error}</span>}<span>Comptage des badgeages, pas du nombre de personnes présentes. Le mode, la date, l’heure et la salle sont partagés avec les autres appareils et la projection N3.</span></div>
    </section>
  </main>;
}
