import { useEffect, useRef, useState } from 'react';
import { createCalibrationSender } from './calibrationSender';

const corners = () => [[0, 0], [1, 0], [1, 1], [0, 1]];
const labels = ['Haut gauche', 'Haut droit', 'Bas droit', 'Bas gauche'];
function controls(data) {
  return {mode:data.mode, corners:data.corners, showGuide:data.showGuide,
    ...(data.sourceCorners ? {sourceCorners:data.sourceCorners} : {}),
    ...(data.initialCorners ? {initialCorners:data.initialCorners} : {})};
}

export default function ProjectionCalibration({ request, onSuccess, token }) {
  const [open, setOpen] = useState(false), [settings, setSettings] = useState(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [ready, setReady] = useState(false);
  const [preview, setPreview] = useState(null), [previewError, setPreviewError] = useState('');
  const liveSettings = useRef(settings); liveSettings.current = settings;
  const planCorners = useRef(corners()), confirmed = useRef(0), serverRevision = useRef(-1);
  const svg = useRef(null), trigger = useRef(null), closeButton = useRef(null), dragging = useRef(null);
  const requestRef = useRef(request), sender = useRef(null), timer = useRef(null), revision = useRef(0), draft = useRef(null);
  requestRef.current = request;
  if (!sender.current) sender.current = createCalibrationSender(value => requestRef.current('calibration-settings', value));
  useEffect(() => () => { clearTimeout(timer.current); revision.current++; }, []);
  useEffect(() => {
    if (!open) return;
    let active = true, refresh, objectUrl;
    const controller = new AbortController();
    async function update() {
      try {
        const response = await fetch('/api/projection-preview', {headers:{Authorization:`Bearer ${token}`},signal:controller.signal,cache:'no-store'});
        if (!response.ok) throw new Error('Aperçu du projecteur indisponible.');
        const blob = await response.blob();
        if (!active) return;
        const previousUrl = objectUrl;
        objectUrl = URL.createObjectURL(blob); setPreview(objectUrl); setPreviewError('');
        if (previousUrl) URL.revokeObjectURL(previousUrl);
      } catch (err) { if (active) setPreviewError(err.message); }
      finally { if (active) refresh = setTimeout(update, 120); }
    }
    update();
    return () => {active=false; controller.abort(); clearTimeout(refresh); if(objectUrl)URL.revokeObjectURL(objectUrl);};
  }, [open, token]);
  function transmitLive(next, version) {
    sender.current({...next, persist:false}).then(data => {
      if (revision.current !== version) return;
      confirmed.current = version;
      serverRevision.current = data.settingsRevision ?? -1;
      setReady(data.automaticReady); setError(''); setNotice('Projection mise à jour en direct.'); onSuccess();
    }).catch(err => { if (revision.current === version) { setError(err.message); setNotice(''); } });
  }
  function edit(next) {
    draft.current = next; setSettings(next); setError('');
    revision.current++;
    setNotice('Mise à jour de la projection…');
    if (timer.current === null) timer.current = setTimeout(() => {
      timer.current = null; transmitLive(draft.current, revision.current);
    }, 60);
  }
  useEffect(() => {
    if (!open) return;
    closeButton.current?.focus();
    const escape = event => { if (event.key === 'Escape') close(); };
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, [open]);
  function close() {
    if (timer.current !== null && draft.current) {
      clearTimeout(timer.current); timer.current = null; transmitLive(draft.current, revision.current);
    }
    setOpen(false); trigger.current?.focus();
  }
  async function show() {
    setOpen(true); setBusy(true); setSettings(null); setError(''); setNotice('');
    try {
      const data = await request('calibration-settings');
      draft.current = null;
      planCorners.current = data.planCorners || corners();
      serverRevision.current = data.settingsRevision ?? -1;
      confirmed.current = revision.current;
      const next = controls(data);
      setSettings(next);
      if (next.mode === 'manual') edit({ ...next, showGuide: true });
      setReady(data.automaticReady);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  function changeCorner(index, axis, value) {
    if (!Number.isFinite(value)) return;
    const current = draft.current || settings;
    edit({ ...current, corners: current.corners.map((point, i) =>
      i === index ? point.map((coordinate, j) => j === axis ? value : coordinate) : point) });
  }
  async function changeMode() {
    setBusy(true); setError(''); clearTimeout(timer.current); timer.current=null; revision.current++;
    try {
      const data = await sender.current({action:settings.mode==='manual'?'resume-automatic':'adjust-automatic'});
      const next = controls(data);
      draft.current=next; setSettings(next); confirmed.current=revision.current;
      setReady(data.automaticReady);
      setNotice(next.mode==='manual'?'Alignement automatique figé : ajuste uniquement les coins du plan.':'Tracking automatique repris.');
    } catch(err) {setError(err.message);}
    finally {setBusy(false);}
  }
  async function apply(next = settings, automatic = false) {
    next = { ...next, showGuide: false };
    setBusy(true); setError(''); setNotice('');
    clearTimeout(timer.current); timer.current = null; revision.current++;
    try {
      const data = await sender.current({...next, persist:true});
      serverRevision.current = data.settingsRevision ?? -1;
      confirmed.current = revision.current; draft.current = next;
      setSettings(next); setReady(data.automaticReady);
      if (automatic) { await request('calibrate', {}); setReady(false); }
      setNotice(automatic ? 'Calibration automatique lancée. Ferme le panneau une fois les repères détectés.' : 'Calibration enregistrée : seules les couleurs des salles sont projetées.');
      onSuccess();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  function move(event) {
    if (dragging.current === null || busy) return;
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(svg.current.getScreenCTM().inverse());
    const index = dragging.current;
    const current = draft.current || settings;
    edit({ ...current, corners: current.corners.map((p, i) => i === index
      ? [Math.max(-.5, Math.min(1.5, point.x)), Math.max(-.5, Math.min(1.5, point.y))] : p) });
  }
  return <>
    <button ref={trigger} className="secondary" onClick={show}>Calibration</button>
    {open && <div className="calibration-backdrop" onClick={event => { if (event.target === event.currentTarget) close(); }}>
      <section className="calibration-panel" role="dialog" aria-modal="true" aria-labelledby="calibration-title"
        onKeyDown={event => {
          if (event.key !== 'Tab') return;
          const buttons = [...event.currentTarget.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled)')];
          const first = buttons[0], last = buttons[buttons.length-1];
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
        }}>
        <div className="calibration-heading"><h2 id="calibration-title">Alignement de la projection</h2><button ref={closeButton} className="secondary" onClick={close} aria-label="Fermer la calibration">×</button></div>
        {busy && !settings && <p>Chargement des réglages…</p>}
        {settings && <>
          <button className="secondary" disabled={busy} onClick={changeMode}>{settings.mode==='manual'?'Revenir au tracking automatique':'Ajuster manuellement le plan calibré'}</button>
          <p>{settings.mode === 'manual'
            ? 'Le plan est affiché à la position obtenue automatiquement. Le tracking est figé pendant le réglage. Comme dans ProjoManuel, seul le point rouge saisi se déplace.'
            : 'Calibre automatiquement, puis ajuste le plan à partir de cet alignement. Les poignées encadrent le plan, pas l’écran du projecteur.'}</p>
          {settings.mode === 'automatic' && <p>{ready ? 'Un alignement automatique est disponible.' : 'Lance la calibration automatique et laisse la caméra détecter le marqueur projeté puis les quatre repères de la maquette.'}</p>}
          <svg ref={svg} className="calibration-preview" viewBox="-0.05 -0.05 1.1 1.1" preserveAspectRatio="none" role="img" aria-label="Image réellement envoyée au projecteur avec quatre points rouges déplaçables"
            onPointerMove={move} onPointerUp={() => { dragging.current = null; }} onPointerCancel={() => { dragging.current = null; }} onLostPointerCapture={() => {dragging.current=null;}}>
            <rect x="0" y="0" width="1" height="1" fill="#152e3c" stroke="#8fa5ad" strokeWidth=".005"/>
            {preview && <image href={preview} x="0" y="0" width="1" height="1" preserveAspectRatio="none" pointerEvents="none"/>}
            {settings.mode==='manual' && <polygon points={settings.corners.map(p => p.join(',')).join(' ')} fill="none" stroke="#ffb933" strokeWidth=".003" pointerEvents="none"/>}
            {settings.mode==='manual' && settings.corners.map((point, index) => <g key={index}>
              <ellipse role="button" tabIndex="0" aria-label={`Déplacer le coin ${labels[index].toLowerCase()}`} cx={point[0]} cy={point[1]} rx=".018" ry=".032" fill="#ff3333" stroke="white" strokeWidth=".003"
                onKeyDown={event => {
                  const direction = {ArrowLeft:[0,-1], ArrowRight:[0,1], ArrowUp:[1,-1], ArrowDown:[1,1]}[event.key];
                  if (!direction || busy) return;
                  event.preventDefault();
                  changeCorner(index, direction[0], point[direction[0]] + direction[1]*(event.shiftKey?10:1)/(direction[0]===0?1919:1079));
                }} onPointerDown={event => {
                if (busy) return;
                event.preventDefault(); event.stopPropagation();
                draft.current = settings;
                dragging.current = index; event.currentTarget.setPointerCapture(event.pointerId);
              }}/>
              <text x={point[0]} y={point[1]-.04} textAnchor="middle" fill="white" fontSize=".035">{['HG', 'HD', 'BD', 'BG'][index]}</text>
            </g>)}
          </svg>
          {previewError && <p className="error" role="alert">{previewError}</p>}
          {settings.mode==='manual' && <>
          <div className="calibration-coordinates">{settings.corners.map((point, index) => <fieldset key={index} disabled={busy}>
            <legend>{labels[index]}</legend>{['X (%)', 'Y (%)'].map((label, axis) => <label key={axis}>{label}<input type="number" min="-50" max="150" step="0.1" value={Math.round(point[axis]*10000)/100}
              onChange={event => { if (event.target.value !== '') changeCorner(index, axis, Number(event.target.value)/100); }}/></label>)}
          </fieldset>)}</div>
          <label className="calibration-guide"><input type="checkbox" disabled={busy} checked={settings.showGuide} onChange={event => {
            edit({ ...settings, showGuide: event.target.checked });
          }}/> Projeter les contours et les repères de réglage</label>
          <div className="calibration-actions">
            <button disabled={busy} onClick={() => apply()}>{busy ? 'Sauvegarde…' : 'Enregistrer les réglages'}</button>
            <button className="secondary" disabled={busy} onClick={() => edit({ ...settings, corners:(settings.initialCorners || settings.corners).map(p=>[...p]) })}>Reprendre l’alignement automatique initial</button>
          </div>
          <p>Les points rouges encadrent uniquement le plan. Déplacer un point déforme le plan et laisse les trois autres points fixes. Enregistrer conserve l’alignement et retire automatiquement le plan et les repères de la projection.</p>
          </>}
          {settings.mode==='automatic' && <button className="secondary" disabled={busy} onClick={() => apply(settings,true)}>Relancer la calibration automatique</button>}
        </>}
        {error && <p className="error" role="alert">{error} <button className="secondary" disabled={busy} onClick={show}>Réessayer</button></p>}
        {notice && <p role="status">{notice}</p>}
      </section>
    </div>}
  </>;
}
