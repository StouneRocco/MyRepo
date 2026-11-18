import scale from '../../shared/temperature-scale.json' with { type: 'json' };
const minTemperature = scale[0].temperature;
const temperatureRange = scale[scale.length - 1].temperature - minTemperature;
export const temperatureGradient = `linear-gradient(90deg,${scale.map(stop =>
  `rgb(${stop.color.join(',')}) ${(stop.temperature - minTemperature) / temperatureRange * 100}%`
).join(',')})`;
export function temperatureColor(value) {
  if (value == null || !Number.isFinite(value)) return '#ffffff';
  value = Math.max(scale[0].temperature, Math.min(scale[scale.length-1].temperature, value));
  for (let i=1; i<scale.length; i++) {
    const a=scale[i-1], b=scale[i];
    if (value<=b.temperature) {
      const ratio=(value-a.temperature)/(b.temperature-a.temperature);
      return `rgb(${a.color.map((v,k)=>Math.round(v+(b.color[k]-v)*ratio)).join(',')})`;
    }
  }
}
export function timeLabel(minute) { return `${String(Math.floor(minute/60)).padStart(2,'0')}:${String(minute%60).padStart(2,'0')}`; }
export function nextMinute(minute,step=15) { return minute+step>=1440 ? 0 : minute+step; }
export function dailySummary(values) {
  const valid=values.filter(v=>v!=null&&Number.isFinite(v));
  return {count:valid.length,min:valid.length?Math.min(...valid):null,max:valid.length?Math.max(...valid):null,mean:valid.length?valid.reduce((a,b)=>a+b,0)/valid.length:null};
}

export function floorDailySeries(series,rooms,estimated={}) {
  const values=Array(288).fill(null), flags=Array(288).fill(false), counts=Array(288).fill(0);
  for(let bucket=0;bucket<288;bucket++){
    let sum=0;
    for(const room of rooms){
      const value=series?.[room.id]?.[bucket];
      if(value==null||!Number.isFinite(value))continue;
      sum+=value;counts[bucket]++;
      if(estimated?.[room.id]?.[bucket])flags[bucket]=true;
    }
    if(counts[bucket])values[bucket]=sum/counts[bucket];
  }
  return {values,estimated:flags,counts};
}
