// Une seule requête à la fois ; les mouvements intermédiaires sont remplacés
// par la dernière position pour que le projecteur ne prenne pas de retard.
export function createCalibrationSender(transmit) {
  let running = false, pending = null;
  async function drain() {
    if (running) return;
    running = true;
    try {
      while (pending) {
        const next = pending; pending = null;
        try {
          const result = await transmit(next.value);
          next.waiters.forEach(({resolve}) => resolve(result));
        } catch (error) {
          next.waiters.forEach(({reject}) => reject(error));
        }
      }
    } finally { running = false; }
  }
  return value => new Promise((resolve, reject) => {
    const waiters = [...(pending?.waiters || []), {resolve, reject}];
    pending = {value, waiters};
    drain();
  });
}
