// Run the actual client script with a minimal DOM/canvas; no browser dependency.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const payload = {
  start: 0, duration: 1, sample_seconds: 0.25,
  map: {pos_x: 0, pos_y: 100, scale: 1}, utility: [], events: [],
  smokes: [{start:0.1,end:0.6,x:0,y:0,radius:144}],
  shots: [{time:0.2,x:0,y:0,yaw:0,silenced:false}],
  players: [{name: '<script>test</script>', selected: true, death: 0.4,
    samples: [[0,0,0,0,true,2,100,false,0,'A'],
      [0.25,40,0,0,true,2,70,false,0,'A'],
      [0.5,80,0,0,true,2,50,false,0,'A']]}]
};
const nodes = new Map();
const ctx = new Proxy({}, {get: () => () => {}, set: () => true});
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
