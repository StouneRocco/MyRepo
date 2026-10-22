const parisDate = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Europe/Paris", year: "numeric", month: "2-digit", day: "2-digit",
});
const parisClock = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Europe/Paris", year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
});

export function parisDay(timestamp) {
  const parts = Object.fromEntries(parisDate.formatToParts(timestamp).map(({ type, value }) => [type, value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export function dayTimestamp(day, minute) {
  const [year, month, date] = day.split("-").map(Number);
  const wallTime = Date.UTC(year, month - 1, date, 0, minute);
  let timestamp = wallTime;
  // Convertit l'heure de Paris en UTC indépendamment du fuseau du navigateur.
  for (let i = 0; i < 2; i++) {
    const parts = Object.fromEntries(parisClock.formatToParts(timestamp).map(({ type, value }) => [type, value]));
    const parisTime = Date.UTC(+parts.year, +parts.month - 1, +parts.day, +parts.hour, +parts.minute, +parts.second);
    timestamp += wallTime - parisTime;
  }
  return timestamp;
}
