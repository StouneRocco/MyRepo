// Même agrégation par heure que babas, appliquée au catalogue de salles Axel.
import scale from '../../shared/presence-scale.json' with {type:'json'};
import temperatureScale from '../../shared/temperature-scale.json' with {type:'json'};
const first=temperatureScale[0].temperature,last=temperatureScale.at(-1).temperature;
const stops=temperatureScale.map(stop=>({value:scale.minimum+(stop.temperature-first)/(last-first)*(scale.maximum-scale.minimum),color:stop.color}));
export const PRESENCE_MAXIMUM=scale.maximum;
export const PRESENCE_MINIMUM=scale.minimum;
export const presenceGradient=`linear-gradient(90deg,${stops.map(stop=>`rgb(${stop.color.join(',')}) ${(stop.value-scale.minimum)/(scale.maximum-scale.minimum)*100}%`).join(',')})`;
export function presenceColor(value){
  if(!Number.isFinite(value)||value<=0)return 'none';
  value=Math.max(scale.minimum,Math.min(scale.maximum,value));
  for(let i=1;i<stops.length;i++){
    const low=stops[i-1],high=stops[i];
    if(value<=high.value){
      const ratio=(value-low.value)/(high.value-low.value);
      return `rgb(${low.color.map((v,j)=>Math.round(v+(high.color[j]-v)*ratio)).join(',')})`;
    }
  }
}

export function badgeageRooms(plan,frame,hour='all') {
  if(!plan||!frame)return [];
  return plan.rooms.map(room=>{
    const data=frame.rooms[room.code];
    return {...room,count:hour==='all'?(data?.total??0):(data?.hours?.[Number(hour)]??0),
      hours:data?.hours??Array(24).fill(0)};
  });
}

export function badgeageSelection(rooms,frame,selected,hour='all') {
  const selectedRoom=rooms.find(room=>room.id===selected);
  return {selectedRoom,
    total:hour==='all'?(frame?.total??0):(frame?.hourTotals?.[Number(hour)]??0),
    maximum:Math.max(0,...rooms.map(room=>room.count)),
    distribution:selectedRoom?.hours??frame?.hourTotals??Array(24).fill(0)};
}

export function nextPresenceHour(hour) {return (Number(hour)+1)%24;}

export function presenceSummary(distribution) {
  const total=distribution.reduce((sum,value)=>sum+value,0);
  return {total,mean:total/24,peak:Math.max(0,...distribution)};
}

export function presenceHourLabel(hour) {return `${String(hour).padStart(2,'0')}:00`;}
