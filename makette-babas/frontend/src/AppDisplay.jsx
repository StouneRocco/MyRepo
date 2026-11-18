import {useEffect,useState} from 'react';

export default function AppDisplay(){
  const [prompt,setPrompt]=useState(null),[fullscreen,setFullscreen]=useState(false),[error,setError]=useState('');
  useEffect(()=>{
    const install=event=>{event.preventDefault();setPrompt(event);};
    const installed=()=>setPrompt(null);
    const change=()=>setFullscreen(!!document.fullscreenElement);
    window.addEventListener('beforeinstallprompt',install);
    window.addEventListener('appinstalled',installed);
    document.addEventListener('fullscreenchange',change);
    return()=>{window.removeEventListener('beforeinstallprompt',install);window.removeEventListener('appinstalled',installed);document.removeEventListener('fullscreenchange',change);};
  },[]);
  async function install(){try{setError('');await prompt.prompt();await prompt.userChoice;setPrompt(null);}catch{setError('Installation indisponible. Ouvre cette adresse HTTPS dans Chrome puis utilise son menu Installer l’application.');}}
  async function toggle(){
    try{setError('');if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}
    catch{setError('Le navigateur ne permet pas le plein écran ici.');}
  }
  return <div className="app-display">
    {prompt&&<button className="secondary" onClick={install}>Installer l’application</button>}
    {document.fullscreenEnabled&&<button className="secondary" onClick={toggle}>{fullscreen?'Quitter le plein écran':'Plein écran'}</button>}
    {error&&<span role="alert">{error}</span>}
  </div>;
}
