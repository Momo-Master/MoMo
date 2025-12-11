async function fetchLite(){
  try{
    const r = await fetch('/api/metrics-lite');
    if(!r.ok) return;
    const j = await r.json();
    document.getElementById('mode').textContent = j.mode;
    document.getElementById('hs').textContent = j.handshakes ?? 0;
    document.getElementById('rot').textContent = j.rotations ?? 0;
    document.getElementById('temp').textContent = j.temp ?? '-';
  }catch(e){/* noop */}
}
setInterval(fetchLite, 5000);
fetchLite();


