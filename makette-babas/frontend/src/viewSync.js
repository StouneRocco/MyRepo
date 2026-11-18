// Un envoi en vol et une seule intention suivante, fusionnée par champ.
export function createViewSync(request, apply, failure) {
  let revision=-1, queued=null, saving=false, polling=null, disposed=false;
  const accept=data=>{if(!disposed&&!saving&&!queued&&data.revision>=revision){revision=data.revision;apply(data);}};
  async function drain(){
    saving=true;
    try{
      while(queued&&!disposed){
        const next=queued;queued=null;
        try{
          const data=await request(next.patch);
          saving=!!queued;accept(data);saving=true;
          next.waiters.forEach(resolve=>resolve());
        }catch(error){if(!disposed)failure(error);next.waiters.forEach(resolve=>resolve());}
      }
    }finally{saving=false;}
  }
  return {
    refresh(){
      if(disposed)return Promise.resolve();
      if(polling)return polling;
      polling=Promise.resolve().then(()=>request()).then(accept,error=>{if(!disposed)failure(error);}).finally(()=>{polling=null;});
      return polling;
    },
    change(patch){
      if(disposed)return Promise.resolve();
      return new Promise(resolve=>{
        queued={patch:{...queued?.patch,...patch},waiters:[...(queued?.waiters||[]),resolve]};
        if(!saving)drain();
      });
    },
    dispose(){disposed=true;queued?.waiters.forEach(resolve=>resolve());queued=null;},
  };
}
