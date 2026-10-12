"use strict";
const D = JSON.parse(document.getElementById("data").textContent);
const el = id => document.getElementById(id);
const canvas = el("radar"), ctx = canvas.getContext("2d"), image = el("mapImage");
const seek = el("seek"), play = el("play"), timeLabel = el("time");
canvas.width = D.width || 1024; canvas.height = D.height || 1024;
let time = D.start, playing = false, previous = null;
seek.max = D.duration;
el("quality").textContent = `Próbkowanie: ${D.sample_seconds.toFixed(2)} s. Przy lukach pozycje znikają zamiast przeskakiwać między odległymi próbkami.`;
const playerNodes = D.players.map(p => {
  const div = document.createElement("div"); div.className = "player";
  el("roster").appendChild(div); return div;
});
for (const event of D.events) {
  const option = document.createElement("option"); option.value = event.time;
  option.textContent = `${event.time.toFixed(2)} s · ${event.text}`; el("events").appendChild(option);
}
function point(x, y) { return [(x-D.map.pos_x)/D.map.scale, (D.map.pos_y-y)/D.map.scale]; }
function onLevel(effect) { return !D.level_id || effect.level_id === undefined || effect.level_id === D.level_id; }
function activeSmokes(t) { return (D.smokes || []).filter(s => onLevel(s) && s.start <= t && t < s.end); }
function activeShots(t) { return (D.shots || []).filter(s => onLevel(s) && s.time <= t && t-s.time < 0.10); }
function sampleAt(player, t, smooth) {
  if (player.death !== null && t >= player.death) return null;
  const samples = player.samples;
  let low = 0, high = samples.length;
  while (low < high) { const mid = (low+high)>>1; if (samples[mid][0] <= t) low = mid+1; else high = mid; }
  if (!low) return null;
  const a = samples[low-1], b = samples[low];
  const maxGap = Math.min(1, D.sample_seconds*1.5);
  if (!a[4] || t-a[0] > maxGap) return null;
  const result = a.slice();
  if (smooth && b && b[4] && b[5] === a[5] && b[0]-a[0] <= maxGap && b[0] > a[0]
      && Math.hypot(b[1]-a[1],b[2]-a[2]) < 300 && Math.abs((b[3]||0)-(a[3]||0)) < 100) {
    const fraction = (t-a[0])/(b[0]-a[0]);
    result[1] += fraction*(b[1]-a[1]); result[2] += fraction*(b[2]-a[2]);
  }
  return result;
}
function pause() { playing = false; previous = null; play.textContent = "▶ Odtwórz"; }
function jump(t) { pause(); time = Math.max(0,Math.min(D.duration,t)); draw(); }
function draw() {
  ctx.clearRect(0,0,canvas.width,canvas.height);
  if (image.complete && image.naturalWidth) ctx.drawImage(image,0,0,canvas.width,canvas.height);
  if (el("smokes").checked) for (const smoke of activeSmokes(time)) {
    const [x,y] = point(smoke.x,smoke.y), radius = smoke.radius/D.map.scale;
    const fade = Math.min(1,(time-smoke.start)/0.35+0.1,(smoke.end-time)/0.5);
    ctx.fillStyle = `rgba(190,202,214,${0.24*fade})`;
    ctx.beginPath(); ctx.arc(x,y,radius,0,Math.PI*2); ctx.fill();
    ctx.fillStyle = `rgba(203,213,225,${0.13*fade})`;
    ctx.beginPath(); ctx.arc(x,y,radius*0.72,0,Math.PI*2); ctx.fill();
    ctx.strokeStyle = `rgba(225,232,240,${0.5*fade})`; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(x,y,radius,0,Math.PI*2); ctx.stroke();
  }
  if (el("util").checked) for (const u of D.utility) {
    if (!onLevel(u) || u.time > time || time-u.time > 1) continue;
    const [x,y] = point(u.x,u.y); ctx.strokeStyle = "#e879f9"; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.moveTo(x-7,y-7); ctx.lineTo(x+7,y+7); ctx.moveTo(x-7,y+7); ctx.lineTo(x+7,y-7); ctx.stroke();
    ctx.fillStyle = "#fff"; ctx.font = "15px system-ui"; ctx.fillText(u.kind,x+10,y);
  }
  D.players.forEach((p,i) => {
    const s = sampleAt(p,time,el("smooth").checked), node = playerNodes[i];
    const dead = p.death !== null && time >= p.death;
    node.textContent = s ? `${p.name} · ${s[6] === null ? "?" : s[6]} HP · ${s[9]}${s[7] ? " ★" : ""}` : `${p.name} · ${dead ? "nie żyje" : "brak pozycji / nie żyje"}`;
    node.style.color = s ? (s[5] === 2 ? "#fbbf24" : "#60a5fa") : "#94a3b8";
    if (!s || (D.level_id && s[10] !== undefined && s[10] !== D.level_id)) return;
    const [x,y] = point(s[1],s[2]);
    ctx.fillStyle = s[5] === 2 ? "#f59e0b" : "#3b82f6";
    ctx.beginPath(); ctx.arc(x,y,p.selected ? 10 : 8,0,Math.PI*2); ctx.fill();
    if (p.selected) { ctx.strokeStyle = "white"; ctx.lineWidth = 3; ctx.stroke(); }
    if (s[8] !== null) { const angle = -s[8]*Math.PI/180; ctx.strokeStyle = ctx.fillStyle; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.moveTo(x,y); ctx.lineTo(x+22*Math.cos(angle),y+22*Math.sin(angle)); ctx.stroke(); }
    ctx.font = "bold 17px system-ui"; ctx.textAlign = "center";
    ctx.strokeStyle = "#10151f"; ctx.lineWidth = 4; ctx.strokeText(p.name,x,y-15);
    ctx.fillStyle = "white"; ctx.fillText(p.name,x,y-15);
    if (s[7]) { ctx.fillStyle = "#fb7185"; ctx.fillText("★",x+16,y+18); }
    ctx.textAlign = "start";
  });
  if (el("shots").checked) for (const shot of activeShots(time)) {
    const [x,y] = point(shot.x,shot.y), angle = -shot.yaw*Math.PI/180;
    const tipX = x+23*Math.cos(angle), tipY = y+23*Math.sin(angle);
    const alpha = (1-(time-shot.time)/0.10)*(shot.silenced ? 0.45 : 0.85);
    ctx.fillStyle = `rgba(255,218,145,${alpha*0.3})`;
    ctx.beginPath(); ctx.arc(tipX,tipY,6,0,Math.PI*2); ctx.fill();
    ctx.fillStyle = `rgba(255,241,198,${alpha})`;
    ctx.beginPath(); ctx.arc(tipX,tipY,2.5,0,Math.PI*2); ctx.fill();
    ctx.strokeStyle = `rgba(255,224,163,${alpha})`; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(tipX-3*Math.cos(angle),tipY-3*Math.sin(angle));
    ctx.lineTo(tipX+5*Math.cos(angle),tipY+5*Math.sin(angle)); ctx.stroke();
  }
  seek.value = time; timeLabel.textContent = `${time.toFixed(2)} / ${D.duration.toFixed(2)} s`;
  el("feed").textContent = D.events.filter(e => e.time <= time && time-e.time <= 4).map(e => `${e.time.toFixed(2)} s ${e.text}`).join(" · ");
}
play.onclick = () => { if (playing) { pause(); return; } if (time >= D.duration) time = 0; playing = true; previous = null; play.textContent = "⏸ Pauza"; };
seek.oninput = () => jump(Number(seek.value));
el("back").onclick = () => jump(time-0.25); el("next").onclick = () => jump(time+0.25);
el("events").onchange = () => { if (el("events").value !== "") jump(Number(el("events").value)); };
el("smooth").onchange = draw; el("util").onchange = draw;
el("smokes").onchange = draw; el("shots").onchange = draw;
document.addEventListener("visibilitychange",() => { if (document.hidden) pause(); });
function animate(now) {
  const wasPlaying = playing;
  if (playing && previous !== null) { time = Math.min(D.duration,time+(now-previous)/1000*Number(el("speed").value)); if (time >= D.duration) pause(); }
  previous = playing ? now : null;
  if (wasPlaying) draw();
  requestAnimationFrame(animate);
}
image.onload = draw; draw(); requestAnimationFrame(animate);
