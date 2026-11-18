import { useEffect, useRef } from "react";
import source from "../../ressources/plan_N3_Structure_modifie.svg?raw";
import plan from "../../shared/plan-n3.json";
import scale from "../../shared/temperature-scale.json";

function temperatureColor(value) {
  if (!Number.isFinite(value)) return "white";
  value = Math.max(scale[0].temperature, Math.min(scale[scale.length - 1].temperature, value));
  for (let i = 1; i < scale.length; i++) {
    const low = scale[i - 1], high = scale[i];
    if (value <= high.temperature) {
      const ratio = (value - low.temperature) / (high.temperature - low.temperature);
      return `rgb(${low.color.map((channel, index) => Math.round(channel + (high.color[index] - channel) * ratio)).join(",")})`;
    }
  }
}

const document = new DOMParser().parseFromString(source, "image/svg+xml");
const svg = document.documentElement;
const [x0, y0, x1, y1] = plan.svgBounds;
svg.setAttribute("viewBox", `${x0 - 2} ${y0 - 2} ${x1 - x0 + 4} ${y1 - y0 + 4}`);
svg.setAttribute("aria-label", "Plan du niveau N3 : sélectionner une salle");
svg.querySelectorAll('[data-selectable="true"]').forEach((room) => {
  room.setAttribute("tabindex", "0");
  room.setAttribute("role", "button");
  room.setAttribute("aria-label", `${room.dataset.roomCode} — ${room.dataset.roomName}`);
});
svg.querySelectorAll('.ifc-space-code').forEach((code) => {
  const room = plan.rooms.find((room) => room.id === code.dataset.roomId);
  if (!room) return;
  const temperature = code.cloneNode(true);
  temperature.removeAttribute("style");
  temperature.setAttribute("class", "room-temperature");
  temperature.setAttribute("data-room-code", room.code);
  temperature.setAttribute("y", Number(code.getAttribute("y")) + 1.6);
  temperature.textContent = "-- °C";
  code.parentNode.appendChild(temperature);
});
const markup = svg.outerHTML;

export default function FloorPlan({ selected, disabled, onSelect, temperatures = {} }) {
  const ref = useRef(null);
  useEffect(() => {
    ref.current.querySelectorAll('[data-selectable="true"]').forEach((room) => {
      room.classList.toggle("selected", room.dataset.spaceId === selected);
      room.setAttribute("aria-pressed", String(room.dataset.spaceId === selected));
      room.setAttribute("aria-disabled", String(disabled));
      room.setAttribute("tabindex", disabled ? "-1" : "0");
    });
  }, [selected, disabled]);
  useEffect(() => {
    ref.current.querySelectorAll('[data-selectable="true"]').forEach((room) => {
      room.style.fill = temperatureColor(temperatures[room.dataset.roomCode]);
    });
    ref.current.querySelectorAll('.room-temperature').forEach((label) => {
      const value = temperatures[label.dataset.roomCode];
      label.textContent = Number.isFinite(value) ? `${value.toFixed(1)} °C` : "-- °C";
    });
  }, [temperatures]);
  const select = (event) => {
    const room = event.target.closest('[data-selectable="true"]');
    if (room && !disabled) onSelect(room.dataset.spaceId);
  };
  return (
    <div ref={ref} className="floor-plan" onClick={select} onKeyDown={(event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        select(event);
      }
    }} dangerouslySetInnerHTML={{ __html: markup }} />
  );
}
