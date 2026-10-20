import BadgeagesDashboard from './BadgeagesDashboard';
import { useEffect, useRef, useState } from 'react';
import { temperatureColor, temperatureGradient, timeLabel, dailySummary, floorDailySeries } from './heatmap';
import ProjectionCalibration from './ProjectionCalibration';
import { createViewSync } from './viewSync';
import AppDisplay from './AppDisplay';

async function api(path, token, body) {
  const response = await fetch(`/api/${path}`, {
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
}

function Auth({ onAuth }) {
  const [mode, setMode] = useState('login');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    try { onAuth(await api(mode, null, Object.fromEntries(form))); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <div className="auth"><div className="auth-display"><AppDisplay/></div><form className="panel" onSubmit={submit}>
    <span className="eyebrow">ESEO · MAQUETTE CONNECTÉE</span>
    <h1>Explorez le bâtiment.</h1><p>Du plan à la maquette, retrouvez chaque salle.</p>
    <label>Identifiant<input name="username" autoComplete="username" required minLength={3} /></label>
    <label>Mot de passe<input name="password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required minLength={8} /></label>
    {error && <p role="alert" className="error">{error}</p>}
    <button disabled={busy}>{busy ? 'Connexion…' : mode === 'login' ? 'Se connecter' : 'Créer le compte'}</button>
    <button type="button" className="secondary" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>{mode === 'login' ? 'Créer un compte' : 'Se connecter'}</button>
  </form></div>;
}

function number(value) { return value == null ? '—' : new Intl.NumberFormat('fr-FR', {maximumFractionDigits:1}).format(value); }
function dayLabel(day) { return day ? day.split('-').reverse().join('/') : ''; }
function RoomPicker({ rooms, selected, onSelect, disabled }) {
  const label = room => room ? `${room.name} · ${room.code}` : 'Vue globale';
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const normalize = text => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const options = [null, ...rooms].filter(room => normalize(label(room)).includes(normalize(query)));
  useEffect(() => { setQuery(''); setOpen(false); setActive(0); }, [selected]);
  function pick(room) { onSelect(room); setQuery(''); setOpen(false); }
  return <div className="room-picker" onBlur={event => {
    if (!event.currentTarget.contains(event.relatedTarget)) { setOpen(false); setQuery(''); }
  }}>
    <label htmlFor="room-search">Choisir une salle</label>
    <div className="room-picker-input">
      <input id="room-search" role="combobox" aria-autocomplete="list" aria-expanded={open}
        aria-controls="room-options" aria-activedescendant={open && options[active] !== undefined ? `room-option-${active}` : undefined}
        disabled={disabled} value={open ? query : label(selected)} placeholder="Code ou nom…"
        onFocus={() => { setQuery(''); setActive(0); setOpen(true); }}
        onChange={event => { setQuery(event.target.value); setActive(0); setOpen(true); }}
        onKeyDown={event => {
          if (event.key === 'Escape') { setOpen(false); setQuery(''); }
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault(); setOpen(true);
            setActive(index => Math.max(0, Math.min(options.length - 1, index + (event.key === 'ArrowDown' ? 1 : -1))));
          }
          if (event.key === 'Enter' && open && options.length) { event.preventDefault(); pick(options[active]); }
        }}/>
      <button type="button" className="room-picker-toggle" aria-label="Afficher la liste des salles" disabled={disabled}
        onMouseDown={event => event.preventDefault()} onClick={() => { setQuery(''); setActive(0); setOpen(!open); }}>▾</button>
    </div>
    {open && <ul id="room-options" role="listbox" className="room-options">
      {options.map((room, index) => <li key={room?.id || 'global'} id={`room-option-${index}`} role="option"
        aria-selected={(room?.id || null) === (selected?.id || null)} className={index === active ? 'active' : ''}
        onMouseDown={event => event.preventDefault()} onMouseEnter={() => setActive(index)} onClick={() => pick(room)}>{label(room)}</li>)}
      {!options.length && <li className="room-no-match">Aucune salle trouvée</li>}
    </ul>}
  </div>;
}
function DayChart({ values, estimated, minute, label='Températures de la salle pendant la journée' }) {
  const stats = dailySummary(values);
  if (!stats.count) return <p>Aucune température disponible pour cette journée.</p>;
  const low = stats.min-.5, high = Math.max(stats.max+.5,low+1);
  const y = v => 104-(v-low)/(high-low)*78;
  const segments = []; let part=[];
  values.forEach((value,i) => { if(value==null) {if(part.length) segments.push(part);part=[];} else part.push([34+i/287*272,y(value)]); });
  if(part.length) segments.push(part);
  return <svg className="day-chart" viewBox="0 0 330 135" role="img" aria-label={label}>
    {[stats.min,stats.max].map((v,i)=><g key={i}><line x1="34" x2="306" y1={y(v)} y2={y(v)} stroke="#dce6e8"/><text x="29" y={y(v)+4} textAnchor="end">{number(v)}</text></g>)}
    {segments.map((points,i)=><polyline key={i} points={points.map(p=>p.join(',')).join(' ')} fill="none" stroke="#087d81" strokeWidth="2"/>)}
    {values.slice(1).map((value,i)=>value!=null&&values[i]!=null&&(estimated?.[i]||estimated?.[i+1])?<line key={`estimate-${i}`} x1={34+i/287*272} x2={34+(i+1)/287*272} y1={y(values[i])} y2={y(value)} stroke="#b66d0b" strokeWidth="3" strokeDasharray="3 2"/>:null)}
    <line x1={34+minute/1435*272} x2={34+minute/1435*272} y1="15" y2="108" stroke="#162d3d" strokeDasharray="3 3"/>
    <text x="34" y="129">00:00</text><text x="306" y="129" textAnchor="end">23:55</text>
  </svg>;
}
function Dashboard({ session, logout, onBadgeages }) {
  const [plans,setPlans]=useState([]),[floor,setFloor]=useState(3),[days,setDays]=useState([]),[day,setDay]=useState('');
  const [frame,setFrame]=useState(null),[minute,setMinute]=useState(0),[playing,setPlaying]=useState(false);
  const [interpolate,setInterpolate]=useState(true);
  const [heatmap,setHeatmap]=useState(true),[selected,setSelected]=useState(null);
  const [status,setStatus]=useState(null),[error,setError]=useState(''),[projectionError,setProjectionError]=useState('');
  const sync=useRef(null), plansRef=useRef(plans), view=useRef({floor:3,day:'',minute:0,playing:false,heatmap:true,interpolate:true,roomId:null});
  plansRef.current=plans;
  function applyView(data){
    view.current={...view.current,...data};
    setFloor(data.floor);setDay(data.day);setMinute(data.minute);setPlaying(data.playing);setHeatmap(data.heatmap);setInterpolate(data.interpolate);
    const room=plansRef.current.find(p=>p.floor===data.floor)?.rooms.find(r=>r.id===data.roomId)||null;
    setSelected(previous=>previous?.id===room?.id?previous:room);
    if('available' in data){setStatus(previous=>previous?.available===data.available?previous:{available:data.available});setProjectionError(data.projectionError||'');}
  }
  if(!sync.current)sync.current=createViewSync(body=>api('view-state',session.token,body),applyView,error=>failure(error));
  function changeView(patch){applyView({...view.current,...patch});sync.current.change(patch);}
  const plan=plans.find(p=>p.floor===floor),bucket=Math.floor(minute/5);
  function failure(err) { if(err.status===401) logout(); else setError(err.message); }
  useEffect(()=>{
    let active=true;
    async function refresh(){if(active)await sync.current.refresh();}
    refresh();const timer=setInterval(refresh,500);
    return()=>{active=false;clearInterval(timer);};
  },[session.token]);
  useEffect(()=>{
    let active=true;
    api('plans',session.token).then(data=>{if(active)setPlans(data);}).catch(err=>{if(active)failure(err);});
    return()=>{active=false;};
  },[session.token]);
  useEffect(()=>{
    let active=true;setDays([]);setFrame(null);setError('');
    api(`days/${floor}`,session.token).then(data=>{if(active)setDays(data);}).catch(err=>{if(active)failure(err);});
    return()=>{active=false;};
  },[floor,session.token]);
  useEffect(()=>{
    let active=true;setFrame(null);setError('');
    if(day)api(`day/${floor}/${day}`,session.token).then(data=>{if(active)setFrame(data);}).catch(err=>{if(active)failure(err);});
    return()=>{active=false;};
  },[day,floor,session.token]);
  function choose(room){changeView({roomId:room?.id||null});setProjectionError('');}
  const currentFrame=frame?.floor===floor&&frame?.day===day?frame:null;
  const series=(interpolate?currentFrame?.interpolated_series:currentFrame?.series)||currentFrame?.series;
  const estimated=interpolate?currentFrame?.estimated:null;
  const roomEstimated=selected?estimated?.[selected.id]:null;
  const rawValues=selected?currentFrame?.series[selected.id]||Array(288).fill(null):[];
  const gapCount=rawValues.filter(v=>v==null).length;
  const filledCount=roomEstimated?.filter(Boolean).length||0;
  const missingNow=plan?.rooms.filter(r=>series?.[r.id]?.[bucket]==null).length||0;
  const estimatedNow=plan?.rooms.filter(r=>estimated?.[r.id]?.[bucket]).length||0;
  const readings=plan?.rooms.map(room=>series?.[room.id]?.[bucket]??null)||[];
  const overall=dailySummary(readings);
  const floorSeries=floorDailySeries(series,plan?.rooms||[],estimated);
  const roomValues=selected?(series?.[selected.id]||Array(288).fill(null)):[];
  const stats=selected?dailySummary(roomValues):overall;
  const current=selected?roomValues[bucket]:overall.mean;
  return <main className="dashboard">
    <header><div><span className="brand">E /</span><b>ESEO <span className="muted">· Maquette thermique</span></b></div><div className="header-actions"><button className="secondary" onClick={onBadgeages}>Badgeages</button><AppDisplay/><button className="secondary" onClick={logout}>Déconnexion · {session.username}</button></div></header>
    <section className="thermal-workspace">
      <div className="thermal-controls">
        <label>Étage<select value={floor} onChange={e=>changeView({floor:Number(e.target.value),roomId:null,playing:false})}>{plans.map(p=><option key={p.floor} value={p.floor}>N{p.floor}</option>)}</select></label>
        <label>Journée<input type="date" value={day} min={days[0]} max={days[days.length-1]} disabled={!days.length} onChange={e=>{if(days.includes(e.target.value)){changeView({day:e.target.value,minute:0,playing:false});setError('');}else if(e.target.value){setError('Aucune donnée disponible pour cette journée.');}}}/></label>
        <label className="heat-switch"><input type="checkbox" checked={heatmap} onChange={e=>changeView({heatmap:e.target.checked})}/> Heatmap</label>
        <label className="heat-switch"><input type="checkbox" checked={interpolate} onChange={e=>changeView({interpolate:e.target.checked})}/> Combler les trous</label>
        <div className="projection-state"><span className={`status-dot ${status?.available?'online':''}`}/>{floor!==3?'N4 en consultation · projection N3 uniquement':status?.available?'Projecteur joignable':status?'Projecteur indisponible':'Connexion au projecteur…'}</div>
        <ProjectionCalibration token={session.token} request={(path, body) => api(path, session.token, body)} onSuccess={() => setStatus({available:true})}/>
      </div>
      <div className="thermal-body">
        <section className="plan-view"><div className="plan-heading"><h2>Plan N{floor}</h2><span>{dayLabel(day)} · {timeLabel(minute)}</span></div>
          <div className="map">{plan&&<svg viewBox={plan.bounds.join(' ')} role="group" aria-label={`Heatmap des salles de N${floor}`}>
            {plan.rooms.map(room=>{
              const value=series?.[room.id]?.[bucket]??null;
              const isEstimated=!!estimated?.[room.id]?.[bucket];
              const x=room.points.reduce((n,p)=>n+p[0],0)/room.points.length,y=room.points.reduce((n,p)=>n+p[1],0)/room.points.length;
              const width=Math.max(...room.points.map(p=>p[0]))-Math.min(...room.points.map(p=>p[0]));
              const height=Math.max(...room.points.map(p=>p[1]))-Math.min(...room.points.map(p=>p[1]));
              const font=Math.max(.6,Math.min(width/5,height/4,plan.bounds[2]/70));
              return <g key={room.id}><polygon points={room.points.map(p=>p.join(',')).join(' ')} style={{fill:heatmap?temperatureColor(value):selected?.id===room.id?'#ffe072':'#e6eef0'}} className={`room ${selected?.id===room.id?'selected':''}`} role="button" tabIndex="0" aria-label={`${room.code}, ${value==null?'sans mesure':`${number(value)} degrés${isEstimated?", valeur interpolée":""}`}`} aria-pressed={selected?.id===room.id} onClick={()=>choose(room)} onKeyDown={e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();choose(room);}}}><title>{room.code} · {room.name} · {value==null?'Sans mesure':`${number(value)} °C${isEstimated?" · Interpolée (relevé manquant)":" · Mesurée"}`}</title></polygon><text x={x} y={y-font*.55} style={{fontSize:font*.7}}>{room.code}</text><text className="room-temperature" x={x} y={y+font*.6} style={{fontSize:font}}>{value==null?'—':`${isEstimated?"≈ ":""}${number(value)}°C`}</text></g>;
            })}
            <image href={`/plans/structure/N${floor}.svg`} x="0" y="0" width="800" height="600" preserveAspectRatio="none" pointerEvents="none" aria-hidden="true" />
          </svg>}</div>
          <div className="heat-legend"><span>12 °C</span><div className="legend-gradient" style={{background:temperatureGradient}}/><span>30 °C</span><span className="missing-key"><i aria-hidden="true"/> Sans mesure</span></div>
        </section>
        <aside className="room-detail">
          <RoomPicker rooms={plan?.rooms || []} selected={selected} onSelect={choose} disabled={!plan}/>
          <div className="detail-heading"><span className="eyebrow">{selected?'SALLE SÉLECTIONNÉE':'VUE GLOBALE'}</span><h2>{selected?.name||`Étage N${floor}`}</h2><p>{selected?.code||`${overall.count} salles avec une température à cet horaire`}</p></div>
          <div className="temperature-current"><strong>{roomEstimated?.[bucket]?"≈ ":""}{number(current)} <small>°C</small></strong><p>{selected?'Température':'Moyenne des salles'} · {timeLabel(minute)}<br/>{selected?(roomEstimated?.[bucket]?"Interpolée · relevé manquant":current==null?"Sans mesure disponible":"Mesure d’origine"): `${estimatedNow} interpolées · ${missingNow} sans valeur`}</p></div>
          <div className="temperature-stats"><div><span>Minimum</span><b>{number(stats.min)}°C</b></div><div><span>Moyenne</span><b>{number(stats.mean)}°C</b></div><div><span>Maximum</span><b>{number(stats.max)}°C</b></div></div>
          {selected?<><p className="detail-caption">Évolution de la salle · {dayLabel(day)}</p><DayChart values={roomValues} estimated={roomEstimated} minute={minute}/><p>{288-gapCount} intervalles mesurés · {gapCount} sans mesure importée, dont {filledCount} interpolés. {gapCount-filledCount} restent sans valeur.</p><details><summary>Historique de la journée</summary><div className="history-table"><table><thead><tr><th>Horaire</th><th>Température / origine</th></tr></thead><tbody>{roomValues.map((value,i)=><tr key={i}><td>{timeLabel(i*5)}</td><td>{value==null?'Sans mesure':`${roomEstimated?.[i]?'≈ ':''}${number(value)} °C · ${roomEstimated?.[i]?'Interpolée':'Mesurée'}`}</td></tr>)}</tbody></table></div></details><button className="secondary" onClick={()=>choose(null)}>Revenir à la vue globale</button></>:<><p className="detail-caption">Moyenne de l’étage sur la journée · {dayLabel(day)}</p><DayChart values={floorSeries.values} estimated={floorSeries.estimated} minute={minute} label="Température moyenne de l’étage pendant la journée"/><p className="detail-caption">Moyenne calculée à chaque horaire sur les salles ayant une valeur. Les segments orange comprennent des valeurs interpolées.</p></>}
        </aside>
      </div>
      <section className="timeline">
        <div className="timeline-top"><button disabled={!frame} className={playing?'pause':''} onClick={()=>changeView({playing:!playing})}>{playing?'Ⅱ Pause':'▶ Lire la journée'}</button><div><b>{timeLabel(minute)}</b><span>{playing?'Lecture en boucle · 48 s / journée':'Déplacez le curseur pour explorer la journée'}</span></div><button className="secondary" disabled={!frame} onClick={()=>changeView({playing:false,minute:0})}>Recommencer</button></div>
        <input aria-label="Horaire de la journée" type="range" min="0" max="1435" step="5" value={minute} disabled={!frame} onChange={e=>changeView({playing:false,minute:Number(e.target.value)})}/>
        <div className="time-ticks">{['00:00','06:00','12:00','18:00','23:55'].map(t=><span key={t}>{t}</span>)}</div>
      </section>
      <div className="workspace-note" aria-live="polite">{error?<span className="error">{error}</span>:!day?'Aucune donnée disponible pour cet étage.':!currentFrame?null:<span>≈ / courbe orange pointillée : valeur interpolée entre deux mesures espacées de {frame.max_gap_minutes ?? 180} min maximum. {estimatedNow} salles interpolées et {missingNow} sans valeur à cet horaire. Les trous longs et les débuts/fins sans mesure restent blancs.</span>}{projectionError&&<span className="error">{projectionError} <button className="secondary retry-projection" onClick={()=>sync.current.refresh()}>Réessayer la projection</button></span>}</div>
    </section>
  </main>;
}
export default function App() {
  const [session, setSession] = useState(() => { try { return JSON.parse(localStorage.getItem('session')); } catch { return null; } });
  const [mode, setMode] = useState('temperatures');
  const logout = () => { localStorage.removeItem('session'); setSession(null); setMode('temperatures'); };
  if (!session) return <Auth onAuth={s => { localStorage.setItem('session', JSON.stringify(s)); setSession(s); }} />;
  return mode === 'badgeages'
    ? <BadgeagesDashboard session={session} logout={logout} onTemperatures={() => setMode('temperatures')} />
    : <Dashboard session={session} logout={logout} onBadgeages={() => setMode('badgeages')} />;
}
