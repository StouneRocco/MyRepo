import AppDisplay from './AppDisplay';

export default function AppHeader({section,onSelect,session,logout}) {
  return <header className="metric-header">
    <div className="metric-navigation">
      <span className="eyebrow">Donnée affichée</span>
      <div className="metric-switch" role="group" aria-label="Choisir la donnée à observer">
        {[['temperatures','Températures','°C'],['presence','Présence','Passages'],['electricity','Électricité','kWh']].map(([value,label,unit])=>
          <button key={value} type="button" aria-label={label} aria-pressed={section===value}
            onClick={()=>{if(section!==value)onSelect(value);}}>
            <span>{label}</span><small aria-hidden="true">{unit}</small>
          </button>)}
      </div>
    </div>
    <div className="header-actions"><AppDisplay/><button className="secondary" onClick={logout}>Déconnexion · {session.username}</button></div>
  </header>;
}
