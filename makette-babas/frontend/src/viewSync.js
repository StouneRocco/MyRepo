export function createViewSync(request, apply, failure) {
  let pending=0, revision=-1, chain=Promise.resolve();
  const accept=data=>{if(!pending && data.revision>=revision){revision=data.revision;apply(data);}};
  return {
    async refresh(){try{accept(await request());}catch(error){failure(error);}},
    change(patch){
      pending++;
      chain=chain.then(()=>request(patch)).then(data=>{pending--;accept(data);},error=>{pending--;failure(error);});
      return chain;
    },
  };
}
