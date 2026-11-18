import {useEffect,useState} from 'react';

export default function RoomPicker({ rooms, selected, onSelect, disabled }) {
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
