// Run the actual client script with a minimal DOM/canvas; no browser dependency.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const payload = {
  start: 0, duration: 1, sample_seconds: 0.25,
  map: {pos_x: 0, pos_y: 100, scale: 1}, utility: [], events: [],
  smokes: [{start:0.1,end:0.6,x:0,y:0,radius:144}],
  shots: [{time:0.2,x:0,y:0,yaw:0,silenced:false}],
  throws: [{time:0.1,x:0,y:0,kind:'Flash',name:'Player',selected:true}],
  projectiles: [{start:0.1,end:0.5,kind:'Flash',team:2,selected:true,max_gap:0.15,
    samples:[[0.1,0,0,0],[0.2,10,0,0],[0.3,10,10,0],[0.4,10,20,0]]}],
  players: [{name: '<script>test</script>', selected: true, death: 0.4,
    flash_intervals:[[0.1,0.3],[0.35,0.8]],
    samples: [[0,0,0,0,true,2,100,false,0,'A'],
      [0.25,40,0,0,true,2,70,false,0,'A'],
      [0.5,80,0,0,true,2,50,false,0,'A']]}]
};
const nodes = new Map();
const calls=[];
const ctx = new Proxy({}, {get: (_,key) => (...args) => calls.push([key,...args]), set: () => true});
function element(id) {
  if (!nodes.has(id)) nodes.set(id,{textContent:'',value:'1',checked:false,
    appendChild(){},style:{},getContext:()=>ctx,complete:false,naturalWidth:0});
  return nodes.get(id);
}
element('data').textContent = JSON.stringify(payload);
const sandbox = {document:{getElementById:element,createElement:()=>({style:{}}),
  addEventListener(){}},requestAnimationFrame(){},console};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('src/assets/maps/radar_player.js','utf8'),sandbox);
const run = code => vm.runInContext(code,sandbox);
assert.equal(run('activeSmokes(0.09).length'),0);
assert.equal(run('activeSmokes(0.1).length'),1);
assert.equal(run('activeSmokes(0.6).length'),0);
assert.equal(run('activeShots(0.19).length'),0);
assert.equal(run('activeShots(0.2).length'),1);
assert.equal(run('activeShots(0.31).length'),0);
assert.equal(run('flashRemaining(D.players[0],0.09)'),0);
assert.ok(Math.abs(run('flashRemaining(D.players[0],0.1)')-0.2)<1e-9);
assert.equal(run('flashRemaining(D.players[0],0.3)'),0);
assert.ok(run('flashRemaining(D.players[0],0.35)')>0);
assert.equal(run('flashRemaining(D.players[0],0.4)'),0);
assert.equal(run('flashRemaining({...D.players[0],death:null,samples:[[0.1,0,0,0,false]]},0.2)'),0);
calls.length=0; run('el("flashes").checked=true;jump(0.2)');
assert.ok(calls.some(c=>c[0]==='fillText' && c[1]==='FLASH'));
assert.ok(calls.some(c=>c[0]==='setLineDash' && JSON.stringify(c[1])==='[4,3]'));
assert.match(run('playerNodes[0].textContent'),/FLASH 0.1 s/);
calls.length=0;run('jump(0.3)');
assert.ok(!calls.some(c=>c[0]==='fillText' && c[1]==='FLASH'));
assert.doesNotMatch(run('playerNodes[0].textContent'),/FLASH/);
calls.length=0;run('jump(0.2)');
assert.ok(calls.some(c=>c[0]==='fillText' && c[1]==='FLASH')); // Backwards seek restores state.
calls.length=0;run('el("flashes").checked=false;jump(0.2)');
assert.ok(!calls.some(c=>c[0]==='fillText' && c[1]==='FLASH'));
assert.equal(run('activeProjectiles(0.09).length'),0);
assert.equal(run('activeProjectiles(0.1).length'),1);
assert.equal(run('activeProjectiles(0.5).length'),0);
assert.ok(Math.abs(run('projectileAt(D.projectiles[0],0.15)[1]')-5)<1e-9);
assert.ok(Math.abs(run('projectileAt(D.projectiles[0],0.25)[2]')-5)<1e-9);
assert.equal(run('projectileAt({...D.projectiles[0],samples:[[0.1,0,0,0],[0.4,100,0,0]]},0.3)'),null);
run('el("grenades").checked=true;jump(0.2)');
assert.ok(calls.some(c=>c[0]==='fillText' && c[1]==='F'));
assert.ok(calls.some(c=>c[0]==='fillText' && c[1]==='RZUT'));
calls.length=0; run('jump(0)');
assert.ok(!calls.some(c=>c[0]==='fillText' && (c[1]==='F' || c[1]==='RZUT')));
calls.length=0; run('el("grenades").checked=false;jump(0.2)');
assert.ok(!calls.some(c=>c[0]==='fillText' && c[1]==='F'));
run('el("smokes").checked=true;el("shots").checked=true;jump(0.2)');
run('jump(0)');
assert.equal(run('sampleAt(D.players[0],0.125,false)[1]'),0);
assert.equal(run('sampleAt(D.players[0],0.125,true)[1]'),20);
assert.equal(run('sampleAt(D.players[0],0.4,true)'),null); // Exact kill time.
assert.equal(run('sampleAt({...D.players[0],death:null,samples:[D.players[0].samples[0]]},0.8,true)'),null);
run('el("next").onclick()'); assert.equal(run('time'),0.25);
run('el("back").onclick()'); assert.equal(run('time'),0);
run('play.onclick();animate(0);animate(250)'); assert.equal(run('time'),0.25);
run('play.onclick();animate(500)'); assert.equal(run('time'),0.25); // Pause.
run('el("speed").value="2";play.onclick();animate(1000);animate(1250)');
assert.equal(run('time'),0.75);
run('animate(1500)'); assert.equal(run('time'),1);
assert.equal(run('playing'),false);
assert.match(element('time').textContent,/1.00 \/ 1.00/); // Last frame drawn.
run('seek.value="0.125";seek.oninput()'); assert.equal(run('time'),0.125);
run('el("events").value="0.5";el("events").onchange()'); assert.equal(run('time'),0.5);
console.log('Radar playback controls, gaps, interpolation, death and final frame: PASS');
