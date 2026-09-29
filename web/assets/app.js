
const API_BASE = "";

function toggleMenu(){
  const menu = document.querySelector(".nav-links");
  if(menu) menu.classList.toggle("open");
}

async function loadActiveEvent(){
  const nameEl = document.getElementById("event-name");
  const countEl = document.getElementById("participant-count");
  const statusEl = document.getElementById("event-status");
  const button = document.getElementById("register-event-btn");
  if(!nameEl || !countEl) return;

  try{
    const response = await fetch(`${API_BASE}/event_participant_count`, {cache:"no-store"});
    if(!response.ok) throw new Error("Unable to load event data.");
    const data = await response.json();

    const events = Array.isArray(data.events) ? data.events : [];
    if(!events.length){
      nameEl.textContent = "No Active Event";
      countEl.textContent = "0";
      if(statusEl) statusEl.textContent = "No event is currently available.";
      if(button) button.style.display = "none";
      return;
    }

    // Use the first non-archived event returned by the existing backend endpoint.
    const event = events[0];
    nameEl.textContent = event.event_name || "Event";
    countEl.textContent = Number(event.participant_count || 0).toLocaleString();
    if(statusEl) statusEl.textContent = "Registration is available";
    if(button) button.href = `register.html?event_id=${encodeURIComponent(event.event_id)}`;
  }catch(error){
    console.error(error);
    nameEl.textContent = "Event Information";
    countEl.textContent = "—";
    if(statusEl) statusEl.textContent = "Unable to load live event data.";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadActiveEvent();

  document.querySelectorAll(".nav-links a").forEach(link => {
    link.addEventListener("click", () => {
      const menu = document.querySelector(".nav-links");
      if(menu) menu.classList.remove("open");
    });
  });
});
