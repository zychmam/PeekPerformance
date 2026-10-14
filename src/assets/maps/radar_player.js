"use strict";
const D = JSON.parse(document.getElementById("data").textContent);
const el = id => document.getElementById(id);
const canvas = el("radar"), ctx = canvas.getContext("2d"), image = el("mapImage");
const seek = el("seek"), play = el("play"), timeLabel = el("time");
canvas.width = D.width || 1024; canvas.height = D.height || 1024;
let time = D.start, playing = false, previous = null;
seek.max = D.duration;
el("quality").textContent = `Próbkowanie: ${D.sample_seconds.toFixed(2)} s. Rzuty: ${(D.throws || []).length} · tory granatów: ${(D.projectiles || []).length}. Przy lukach pozycje znikają zamiast przeskakiwać między odległymi próbkami.${D.projectile_status === "unavailable" ? " Tory lotu nie są dostępne w tym kontekście." : ""}`;
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
function flashRemaining(player,t) {
  if (player.death!==null && player.death!==undefined && t>=player.death) return 0;
  const sampleIndex=upperTime(player.samples,t,s=>s[0]);
  if (sampleIndex && player.samples[sampleIndex-1][4]===false) return 0;
  const intervals=player.flash_intervals || [];
  const index=upperTime(intervals,t,s=>s[0]);
  return index && t<intervals[index-1][1] ? intervals[index-1][1]-t : 0;
}
const grenadeTracks = (D.projectiles || []).slice().sort((a,b) => a.start-b.start);
function upperTime(items, t, getTime) {
  let low=0, high=items.length;
  while (low<high) { const mid=(low+high)>>1; if (getTime(items[mid])<=t) low=mid+1; else high=mid; }
  return low;
}
function activeProjectiles(t) {
  const limit=upperTime(grenadeTracks,t,p=>p.start), result=[];
  for (let i=0;i<limit;i++) if (t<grenadeTracks[i].end) result.push(grenadeTracks[i]);
  return result;
}
function projectileAt(p,t) {
  if (t<p.start || t>=p.end) return null;
  const i=upperTime(p.samples,t,s=>s[0]);
  if (!i) return null;
  const a=p.samples[i-1], b=p.samples[i], result=a.slice();
  if (t-a[0]>p.max_gap) return null;
  if (b && b[0]>a[0] && b[0]-a[0]<=p.max_gap) {
    const f=(t-a[0])/(b[0]-a[0]);
    for (let axis=1;axis<=3;axis++) result[axis]+=f*(b[axis]-a[axis]);
  }
  if (D.level_ranges && D.level_ranges.length) {
    const levels=D.level_ranges.filter(l=>(l.z_min===null || result[3]>=l.z_min)
      && (l.z_max===null || result[3]<l.z_max));
    result[4]=levels.length===1 ? levels[0].id : null;
  }
  return result;
}
function grenadeStyle(kind) {
  return ({Flash:["F","#fef08a"],HE:["H","#fb923c"],Smoke:["S","#cbd5e1"],
    "Ogień":["M","#fb7185"],Decoy:["D","#c4b5fd"]})[kind] || ["G","#ffffff"];
}
function grenadeIcon(x,y,kind,radius=8) {
  const [letter,color]=grenadeStyle(kind);
  ctx.fillStyle="#10151f"; ctx.strokeStyle=color; ctx.lineWidth=2.5;
  ctx.beginPath(); ctx.arc(x,y,radius,0,Math.PI*2); ctx.fill(); ctx.stroke();
  ctx.font="bold 12px system-ui"; ctx.textAlign="center"; ctx.textBaseline="middle";
  ctx.fillStyle=color; ctx.fillText(letter,x,y+0.5);
  ctx.textAlign="start"; ctx.textBaseline="alphabetic";
}
function drawGrenades(t) {
  if (!el("grenades").checked) return;
  const selectedOnly=el("selectedGrenades").checked;
  for (const p of activeProjectiles(t)) {
    if (selectedOnly && !p.selected) continue;
    const s=projectileAt(p,t);
    if (!s || !onLevel({level_id:s[4]})) continue;
    const color=p.team===2 ? "#fbbf24" : p.team===3 ? "#60a5fa" : "#e2e8f0";
    const points=p.samples.filter(a=>a[0]>=t-0.55 && a[0]<=t);
    points.push(s);
    ctx.strokeStyle=color; ctx.lineWidth=p.selected ? 3.5 : 2.5;
    ctx.beginPath(); let previousPoint=null;
    for (const a of points) {
      if (!onLevel({level_id:a[4]})) { previousPoint=null; continue; }
      const [x,y]=point(a[1],a[2]);
      if (previousPoint && a[0]-previousPoint[0]<=p.max_gap) ctx.lineTo(x,y);
      else ctx.moveTo(x,y);
      previousPoint=a;
    }
    ctx.stroke();
    const [x,y]=point(s[1],s[2]); grenadeIcon(x,y,p.kind);
  }
  for (const event of D.throws || []) {
    const age=t-event.time;
    if (age<0 || age>=0.55 || !onLevel(event) || (selectedOnly && !event.selected)) continue;
    const [x,y]=point(event.x,event.y), alpha=1-age/0.55;
    ctx.strokeStyle=`rgba(255,255,255,${alpha})`; ctx.lineWidth=2.5;
    ctx.beginPath(); ctx.arc(x,y,15+age*28,0,Math.PI*2); ctx.stroke();
    grenadeIcon(x+19,y+15,event.kind,9);
    ctx.font="bold 13px system-ui"; ctx.fillStyle="#ffffff";
    ctx.strokeStyle="#10151f"; ctx.lineWidth=3;
    ctx.strokeText("RZUT",x+31,y+20); ctx.fillText("RZUT",x+31,y+20);
  }
}
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
  drawGrenades(time);
  D.players.forEach((p,i) => {
    const s = sampleAt(p,time,el("smooth").checked), node = playerNodes[i];
    const dead = p.death !== null && time >= p.death;
    const flash=el("flashes").checked ? flashRemaining(p,time) : 0;
    node.textContent = s ? `${p.name} · ${s[6] === null ? "?" : s[6]} HP · ${s[9]}${s[7] ? " ★" : ""}` : `${p.name} · ${dead ? "nie żyje" : "brak pozycji / nie żyje"}`;
    if (flash>0) node.textContent+=` · FLASH ${flash.toFixed(1)} s`;
    node.style.color = s ? (s[5] === 2 ? "#fbbf24" : "#60a5fa") : "#94a3b8";
    if (!s || (D.level_id && s[10] !== undefined && s[10] !== D.level_id)) return;
    const [x,y] = point(s[1],s[2]);
    ctx.fillStyle = s[5] === 2 ? "#f59e0b" : "#3b82f6";
    ctx.beginPath(); ctx.arc(x,y,p.selected ? 10 : 8,0,Math.PI*2); ctx.fill();
    if (p.selected) { ctx.strokeStyle = "#22d3ee"; ctx.lineWidth = 3; ctx.stroke(); }
    if (flash>0) {
      ctx.save();
      ctx.beginPath(); ctx.arc(x,y,16,0,Math.PI*2);
      ctx.strokeStyle="#10151f"; ctx.lineWidth=5; ctx.stroke();
      ctx.setLineDash([4,3]); ctx.strokeStyle="#ffffff"; ctx.lineWidth=3; ctx.stroke();
      ctx.restore();
      ctx.font="bold 12px system-ui"; ctx.textAlign="center";
      ctx.strokeStyle="#10151f"; ctx.lineWidth=3; ctx.strokeText("FLASH",x,y+29);
      ctx.fillStyle="#ffffff"; ctx.fillText("FLASH",x,y+29);
      ctx.textAlign="start";
    }
    if (s[8] !== null) { const angle = -s[8]*Math.PI/180; ctx.strokeStyle = s[5] === 2 ? "#f59e0b" : "#3b82f6"; ctx.lineWidth = 3;
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
el("grenades").onchange = draw; el("selectedGrenades").onchange = draw;
el("flashes").onchange = draw;
document.addEventListener("visibilitychange",() => { if (document.hidden) pause(); });
function animate(now) {
  const wasPlaying = playing;
  if (playing && previous !== null) { time = Math.min(D.duration,time+(now-previous)/1000*Number(el("speed").value)); if (time >= D.duration) pause(); }
  previous = playing ? now : null;
  if (wasPlaying) draw();
  requestAnimationFrame(animate);
}
image.onload = draw; draw(); requestAnimationFrame(animate);
