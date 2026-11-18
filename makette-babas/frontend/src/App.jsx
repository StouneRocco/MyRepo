import AppHeader from './AppHeader';
import RoomPicker from './RoomPicker';
import BadgeagesDashboard from './BadgeagesDashboard';
import ElectricityDashboard from './ElectricityDashboard';
import { api } from './api';
import { useEffect, useRef, useState } from 'react';
import { temperatureColor, temperatureGradient, timeLabel, dailySummary, floorDailySeries } from './heatmap';
import ProjectionCalibration from './ProjectionCalibration';
import { createViewSync } from './viewSync';
import AppDisplay from './AppDisplay';


function Auth({ onAuth }) {
  const [mode, setMode] = useState('login');
  const [registrationOpen,setRegistrationOpen]=useState(false);
  useEffect(()=>{api('config').then(data=>setRegistrationOpen(data.registrationOpen)).catch(()=>{});},[]);
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
    <button hidden={!registrationOpen} type="button" className="secondary" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>{mode === 'login' ? 'Créer un compte' : 'Se connecter'}</button>
  </form></div>;
}

function number(value) { return value == null ? '—' : new Intl.NumberFormat('fr-FR', {maximumFractionDigits:1}).format(value); }
function dayLabel(day) { return day ? day.split('-').reverse().join('/') : ''; }

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
function Dashboard({ session, logout, onSelect, onMetric }) {
  const canControl=session.role!=='viewer';
  const [plans,setPlans]=useState([]),[floor,setFloor]=useState(3),[days,setDays]=useState([]),[day,setDay]=useState('');
  const [frame,setFrame]=useState(null),[minute,setMinute]=useState(0),[playing,setPlaying]=useState(false);
  const [predictionData,setPredictionData]=useState(null),[predictionLoading,setPredictionLoading]=useState(false);
  const [interpolate,setInterpolate]=useState(true);
  const [heatmap,setHeatmap]=useState(true),[selected,setSelected]=useState(null);
  const [status,setStatus]=useState(null),[error,setError]=useState(''),[projectionError,setProjectionError]=useState('');
  const [connectionError,setConnectionError]=useState('');
  const sync=useRef(null), plansRef=useRef(plans), view=useRef({floor:3,day:'',minute:0,playing:false,heatmap:true,interpolate:true,roomId:null});
  plansRef.current=plans;
  function applyView(data){
    if(data.metric)onMetric(data.metric);
    view.current={...view.current,...data};
    setFloor(data.floor);setDay(data.day);setMinute(data.minute);setPlaying(data.playing);setHeatmap(data.heatmap);setInterpolate(data.interpolate);
    const room=plansRef.current.find(p=>p.floor===data.floor)?.rooms.find(r=>r.id===data.roomId)||null;
    setSelected(previous=>previous?.id===room?.id?previous:room);
    if('available' in data){setStatus({available:data.available,details:data.receiverStatus});setProjectionError(data.projectionError||'');}
  }
  if(!sync.current)sync.current=createViewSync(body=>api('view-state',session.token,body),data=>{applyView(data);setConnectionError('');},error=>{if(error.status===401)logout();else setConnectionError(`Synchronisation interrompue : ${error.message}`);});
  useEffect(()=>()=>sync.current?.dispose(),[]);
  function changeView(patch){applyView({...view.current,...patch});sync.current.change(patch);}
  const plan=plans.find(p=>p.floor===floor),bucket=Math.floor(minute/5);
  function failure(err) { if(err.status===401) logout(); else setError(err.message); }
  useEffect(()=>{
    let active=true;
    let timer;
    async function refresh(){
      if(!active)return;
      await sync.current.refresh();
      if(active)timer=setTimeout(refresh,document.hidden?3000:500);
    }
    refresh();
    return()=>{active=false;clearTimeout(timer);};
  },[session.token]);
  useEffect(()=>{
    let active=true;
    api('plans',session.token).then(data=>{if(active)setPlans(data);}).catch(err=>{if(active)failure(err);});
    return()=>{active=false;};
  },[session.token]);
  useEffect(()=>{
    let active=true,timer;setDays([]);setFrame(null);setError('');
    const refresh=()=>api(`days/${floor}`,session.token).then(data=>{if(active)setDays(data);}).catch(err=>{if(active)failure(err);}).finally(()=>{if(active)timer=setTimeout(refresh,30000);});
    refresh();return()=>{active=false;clearTimeout(timer);};
  },[floor,session.token]);
  useEffect(()=>{
    let active=true,timer;setFrame(null);setError('');
    const refresh=()=>api(`day/${floor}/${day}`,session.token).then(data=>{if(active)setFrame(data);}).catch(err=>{if(active)failure(err);}).finally(()=>{if(active)timer=setTimeout(refresh,30000);});
    if(day)refresh();return()=>{active=false;clearTimeout(timer);};
  },[day,floor,session.token]);
  function choose(room){if(!canControl)return;changeView({roomId:room?.id||null});setProjectionError('');}
  const currentFrame=frame?.floor===floor&&frame?.day===day?frame:null;
  const predictionSeries={};
  for(const item of (predictionData?.predictions||[])){
    const match=plan?.rooms.find(r=>r.code===item.room||r.name===item.room||r.id===item.room);
    if(!match)continue;
    predictionSeries[match.id]=Array.from({length:288},(_,i)=>{
      const point=item.hourly?.[Math.floor(i/12)];
      const value=point?.temperature??item.temperature;
      return Number.isFinite(value)?value:null;
    });
  }
  const predictionValues={};
  for(const [roomId,values] of Object.entries(predictionSeries)){
    const value=values[bucket];
    if(Number.isFinite(value))predictionValues[roomId]=value;
  }
  const showingPredictions=!!predictionData&&predictionData.date===day&&Object.keys(predictionValues).length>0;
  const series=(interpolate?currentFrame?.interpolated_series:currentFrame?.series)||currentFrame?.series;
  const estimated=interpolate?currentFrame?.estimated:null;
  const roomEstimated=selected?(showingPredictions?Array(288).fill(true):estimated?.[selected.id]):null;
  const rawValues=selected?currentFrame?.series[selected.id]||Array(288).fill(null):[];
  const gapCount=rawValues.filter(v=>v==null).length;
  const filledCount=roomEstimated?.filter(Boolean).length||0;
  const missingNow=plan?.rooms.filter(r=>series?.[r.id]?.[bucket]==null).length||0;
  const estimatedNow=plan?.rooms.filter(r=>estimated?.[r.id]?.[bucket]).length||0;
  const readings=plan?.rooms.map(room=>(showingPredictions?predictionSeries[room.id]?.[bucket]:series?.[room.id]?.[bucket])??null)||[];
  const overall=dailySummary(readings);
  const floorSeries=floorDailySeries(series,plan?.rooms||[],estimated);
  const displayFloorSeries=showingPredictions?{values:Array.from({length:288},(_,i)=>{
    const vals=plan?.rooms.map(room=>predictionSeries[room.id]?.[i]).filter(Number.isFinite)||[];
    return vals.length?vals.reduce((a,b)=>a+b,0)/vals.length:null;
  }),estimated:Array(288).fill(true)}:floorSeries;
  const roomValues=selected?(showingPredictions?(predictionSeries[selected.id]||Array(288).fill(null)):(series?.[selected.id]||Array(288).fill(null))):[];
  const stats=selected?dailySummary(roomValues):overall;
  const current=selected?roomValues[bucket]:overall.mean;
  return <main className="dashboard">
    <AppHeader section="temperatures" onSelect={onSelect} session={session} logout={logout}/>
    <section className="thermal-workspace">
      <div className="thermal-controls">
        <label>Étage<select disabled={!canControl} value={floor} onChange={e=>changeView({floor:Number(e.target.value),roomId:null,playing:false})}>{plans.map(p=><option key={p.floor} value={p.floor}>N{p.floor}</option>)}</select></label>
        <label>Journée<input type="date" value={day} disabled={!canControl} onChange={async e=>{
          const chosen=e.target.value;if(!chosen)return;
          changeView({day:chosen,minute:0,playing:false});setError('');setPredictionData(null);
          if(days.includes(chosen))return;
          setPredictionLoading(true);setError('Calcul des estimations en cours…');
          try{const result=await api(`predictions/temperatures?${new URLSearchParams({date:chosen})}`,session.token);setPredictionData({...result,date:chosen});setError('');}
          catch(err){setError(err.message||'Impossible de calculer cette journée.');}
          finally{setPredictionLoading(false);}
        }}/></label>
        <label className="heat-switch"><input type="checkbox" disabled={!canControl} checked={heatmap} onChange={e=>changeView({heatmap:e.target.checked})}/> Heatmap</label>
        <label className="heat-switch"><input type="checkbox" disabled={!canControl} checked={interpolate} onChange={e=>changeView({interpolate:e.target.checked})}/> Combler les trous</label>
        <div className="projection-state"><span className={`status-dot ${status?.available?'online':''}`}/>{floor!==3?'N4 en consultation · projection N3 uniquement':status?.available?(status.details?.mode==='manual'?'Projection manuelle':status.details?.cameraAvailable===false?'Caméra indisponible':!status.details?.automaticReady?'Calibration en cours':status.details?.visibleMarkers<4?'Repères masqués · pose conservée':'Projection automatique'):status?'Projecteur indisponible':'Connexion au projecteur…'}</div>
        <ProjectionCalibration disabled={!canControl} token={session.token} request={(path, body) => api(path, session.token, body)} onSuccess={() => sync.current.refresh()}/>
      </div>
      <div className="thermal-body">
        <section className="plan-view"><div className="plan-heading"><h2>Plan N{floor}</h2><span>{dayLabel(day)} · {timeLabel(minute)}</span></div>
          <div className="map">{plan&&<svg viewBox={plan.bounds.join(' ')} role="group" aria-label={`Heatmap des salles de N${floor}`}>
            {plan.rooms.map(room=>{
              const value=showingPredictions?(predictionValues[room.id]??null):(series?.[room.id]?.[bucket]??null);
              const isEstimated=showingPredictions?value!=null:!!estimated?.[room.id]?.[bucket];
              const x=room.points.reduce((n,p)=>n+p[0],0)/room.points.length,y=room.points.reduce((n,p)=>n+p[1],0)/room.points.length;
              const width=Math.max(...room.points.map(p=>p[0]))-Math.min(...room.points.map(p=>p[0]));
              const height=Math.max(...room.points.map(p=>p[1]))-Math.min(...room.points.map(p=>p[1]));
              const font=Math.max(.6,Math.min(width/5,height/4,plan.bounds[2]/70));
              return <g key={room.id}><polygon points={room.points.map(p=>p.join(',')).join(' ')} style={{fill:heatmap?temperatureColor(value):selected?.id===room.id?'#ffe072':'#e6eef0'}} className={`room ${selected?.id===room.id?'selected':''}`} role="button" tabIndex="0" aria-label={`${room.code}, ${value==null?'sans mesure':`${number(value)} degrés${isEstimated?(showingPredictions?", valeur prédite":", valeur interpolée"):""}`}`} aria-pressed={selected?.id===room.id} onClick={()=>choose(room)} onKeyDown={e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();choose(room);}}}><title>{room.code} · {room.name} · {value==null?'Sans mesure':`${number(value)} °C${isEstimated?(showingPredictions?" · Prédiction IA":" · Interpolée (relevé manquant)"):" · Mesurée"}`}</title></polygon><text x={x} y={y-font*.55} style={{fontSize:font*.7}}>{room.code}</text><text className="room-temperature" x={x} y={y+font*.6} style={{fontSize:font}}>{value==null?'—':`${isEstimated?"≈ ":""}${number(value)}°C`}</text></g>;
            })}
            <image href={`/plans/structure/N${floor}.svg`} x="0" y="0" width="800" height="600" preserveAspectRatio="none" pointerEvents="none" aria-hidden="true" />
          </svg>}</div>
          <div className="heat-legend"><span>12 °C</span><div className="legend-gradient" style={{background:temperatureGradient}}/><span>30 °C</span><span className="missing-key"><i aria-hidden="true"/> Sans mesure</span></div>
        </section>
        <aside className="room-detail">
          <RoomPicker rooms={plan?.rooms || []} selected={selected} onSelect={choose} disabled={!plan||!canControl}/>
          <div className="detail-heading"><span className="eyebrow">{selected?'SALLE SÉLECTIONNÉE':'VUE GLOBALE'}</span><h2>{selected?.name||`Étage N${floor}`}</h2><p>{selected?.code||`${overall.count}/${plan?.rooms.length||0} salles avec une température à cet horaire`}</p></div>
          <div className="temperature-current"><strong>{(showingPredictions||roomEstimated?.[bucket])?"≈ ":""}{number(current)} <small>°C</small></strong><p>{selected?'Température':'Moyenne des salles disponibles'} · {timeLabel(minute)}<br/> {showingPredictions?`Estimation IA · ${predictionData.date}`:selected?(roomEstimated?.[bucket]?"Interpolée · relevé manquant":current==null?"Sans mesure disponible":"Mesure d’origine"): `${estimatedNow} interpolées · ${missingNow} sans valeur`}</p></div>
          <div className="temperature-stats"><div><span>Minimum {selected?'du jour':'à cet horaire'}</span><b>{number(stats.min)}°C</b></div><div><span>Moyenne {selected?'du jour':'à cet horaire'}</span><b>{number(stats.mean)}°C</b></div><div><span>Maximum {selected?'du jour':'à cet horaire'}</span><b>{number(stats.max)}°C</b></div></div>
          {selected?<><p className="detail-caption">Évolution de la salle · {dayLabel(day)}</p><DayChart values={roomValues} estimated={showingPredictions?Array(288).fill(true):roomEstimated} minute={minute} label={showingPredictions?"Profil horaire prédit":"Températures de la salle pendant la journée"}/><p>{showingPredictions?"Profil horaire estimé à partir des écarts historiques par salle. Il ne s’agit pas de mesures réelles.":`${288-gapCount} intervalles mesurés · ${gapCount} sans mesure importée, dont ${filledCount} interpolés. ${gapCount-filledCount} restent sans valeur.`}</p><details><summary>Historique de la journée</summary><div className="history-table"><table><thead><tr><th>Horaire</th><th>Température / origine</th></tr></thead><tbody>{roomValues.map((value,i)=><tr key={i}><td>{timeLabel(i*5)}</td><td>{value==null?'Sans mesure':`${roomEstimated?.[i]?'≈ ':''}${number(value)} °C · ${showingPredictions?'Prédiction IA':roomEstimated?.[i]?'Interpolée':'Mesurée'}`}</td></tr>)}</tbody></table></div></details><button className="secondary" onClick={()=>choose(null)}>Revenir à la vue globale</button></>:<><p className="detail-caption">Moyenne de l’étage sur la journée · {dayLabel(day)}</p><DayChart values={displayFloorSeries.values} estimated={displayFloorSeries.estimated} minute={minute} label="Température moyenne de l’étage pendant la journée"/><p className="detail-caption">{showingPredictions?"Moyenne des prédictions horaires des salles disponibles. La courbe est estimée, pas mesurée.":"Moyenne calculée à chaque horaire sur les salles ayant une valeur. Les segments orange comprennent des valeurs interpolées."}</p></>}
        </aside>
      </div>
      <section className="timeline">
        <div className="timeline-top"><button disabled={(!frame&&!showingPredictions)||predictionLoading||!canControl} className={playing?'pause':''} onClick={()=>changeView({playing:!playing})}>{playing?'Ⅱ Pause':'▶ Lire la journée'}</button><div><b>{timeLabel(minute)}</b><span>{playing?'Lecture en boucle · 48 s / journée':'Déplacez le curseur pour explorer la journée'}</span></div><button className="secondary" disabled={(!frame&&!showingPredictions)||predictionLoading||!canControl} onClick={()=>changeView({playing:false,minute:0})}>Recommencer</button></div>
        <input aria-label="Horaire de la journée" type="range" min="0" max="1435" step="5" value={minute} disabled={(!frame&&!showingPredictions)||predictionLoading||!canControl} onChange={e=>changeView({playing:false,minute:Number(e.target.value)})}/>
        <div className="time-ticks">{['00:00','06:00','12:00','18:00','23:55'].map(t=><span key={t}>{t}</span>)}</div>
      </section>
      <div className="workspace-note" aria-live="polite">{showingPredictions&&<span>≈ Valeurs estimées par le modèle Random Forest ; profil horaire reconstruit à partir de l’historique, pas des mesures réelles.</span>}{!canControl&&<span>Mode consultation : un opérateur pilote la vue partagée et la projection.</span>}{connectionError&&<span className="error" role="alert">{connectionError} · Les données affichées peuvent être anciennes.</span>}{error?<span className="error">{error}</span>:!day?'Aucune donnée disponible pour cet étage.':!currentFrame?null:<span>{frame.invalid_minutes?.includes(minute)&&'Cet horaire n’existe pas ce jour-là (changement d’heure). '}{frame.aggregation}. ≈ / courbe orange pointillée : valeur interpolée entre deux mesures espacées de {frame.max_gap_minutes ?? 180} min maximum. {estimatedNow} salles interpolées et {missingNow} sans valeur à cet horaire. Les trous longs et les débuts/fins sans mesure restent blancs.</span>}{projectionError&&<span className="error">{projectionError} <button className="secondary retry-projection" onClick={()=>api('projection-retry',session.token,{}).then(()=>sync.current.refresh()).catch(failure)}>Réessayer la projection</button></span>}</div>
    </section>
  </main>;
}
export default function App() {
  const [session, setSession] = useState(() => { try { return JSON.parse(localStorage.getItem('session')); } catch { return null; } });
  const [section,setSection]=useState('temperatures');
  const [navigationError,setNavigationError]=useState('');
  async function switchMetric(metric){
    if(metric==='predictions'){setSection('temperatures');return;}
    try {
      const data=await api('view-state',session.token,{metric,playing:false,...(['presence','electricity'].includes(metric)?{heatmap:true}:{})});
      setNavigationError('');setSection(data.metric);
    } catch(error) {if(error.status===401)logout();else setNavigationError(error.message);}
  }
  const logout = () => { localStorage.removeItem('session'); setSession(null); setSection('temperatures'); };
  if(!session)return <Auth onAuth={s=>{localStorage.setItem('session',JSON.stringify(s));setSession(s);}}/>;
  return <>{navigationError&&<p className="error" role="alert">{navigationError}</p>}{section==='electricity'
    ? <ElectricityDashboard session={session} logout={logout} onSelect={switchMetric} onMetric={setSection}/>
    : section==='presence'
    ? <BadgeagesDashboard session={session} logout={logout} onMetric={setSection} onSelect={switchMetric}/>
    : <Dashboard session={session} logout={logout} onMetric={setSection} onSelect={switchMetric}/>}</>;
}
