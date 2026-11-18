export function availableMonths(days){return [...new Set(days.map(day=>day.slice(0,7)))].sort();}
export function dayInMonth(days,month,current){
  const candidates=days.filter(day=>day.startsWith(month+'-'));
  if(!candidates.length)return null;
  const sameDay=month+'-'+current.slice(8,10);
  return candidates.includes(sameDay)?sameDay:candidates[0];
}
export function monthLabel(month){return new Intl.DateTimeFormat('fr-FR',{month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(month+'-01T12:00:00Z'));}
