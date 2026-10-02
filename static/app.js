let settingsModal;

const $ = id => document.getElementById(id);

function fmt(v, digits=2) {
  return v === null || v === undefined ? "—" : Number(v).toFixed(digits);
}
function powerName(v) {
  return ["MIN","LOW","HIGH","MAX"][Number(v)] || "?";
}
function showMessage(text, ok=true) {
  const el = $("message");
  el.className = "alert " + (ok ? "alert-success" : "alert-danger");
  el.textContent = text;
  el.classList.remove("d-none");
  setTimeout(() => el.classList.add("d-none"), 3500);
}
function setCell(id, text) { $(id).textContent = text; }

function batteryPercent(voltage) {
  if (!Number.isFinite(Number(voltage)) || Number(voltage) <= 0.6) return 0;
  voltage = Number(voltage);
  const curve = [[3.00,0],[3.30,5],[3.50,10],[3.60,20],[3.70,40],
    [3.80,60],[3.90,75],[4.00,85],[4.10,95],[4.20,100]];
  if (voltage <= curve[0][0]) return 0;
  if (voltage >= curve[curve.length-1][0]) return 100;
  for (let i=1;i<curve.length;i++) {
    const [v1,p1] = curve[i], [v0,p0] = curve[i-1];
    if (voltage <= v1) return Math.round(p0 + (voltage-v0)*(p1-p0)/(v1-v0));
  }
  return 100;
}

function renderNodes(nodes, stats) {
  const host = $("nodeBlocks");
  const entries = Object.entries(nodes || {}).sort((a,b) => Number(a[0])-Number(b[0]));
  if (!entries.length) {
    host.innerHTML = '<section class="panel"><div class="panel-title">Dane stacji</div><div class="text-secondary">Oczekiwanie na dane z nadajników…</div></section>';
    return;
  }
  host.innerHTML = entries.map(([id,d]) => {
    const n = (stats.nodes || {})[id] || {};
    const age = Math.max(0, (Date.now()/1000) - d.received_at).toFixed(1);
    const metric = (label,value,unit="") => `<div class="metric"><span>${label}</span><strong>${value}</strong><small>${unit}</small></div>`;
    const hasIna = !!(d.status & 0x10);
    const batteryV = Number(d.ina1_voltage || 0);
    const batteryPct = batteryPercent(batteryV);
    const rows = [1,2,3].map(i => `<tr><td>CH${i}</td><td>${fmt(d[`ina${i}_voltage`])} V</td><td>${fmt(d[`ina${i}_current`],3)} A</td><td>${fmt(d[`ina${i}_voltage`]*d[`ina${i}_current`],3)} W</td></tr>`).join("");
    return `<section class="panel mb-3"><div class="panel-title"><span><i class="bi bi-cloud-sun"></i> WeatherLink Station · Node ID ${id}</span><span>${age} s · sekwencja ${d.sequence}</span></div>
      <div class="sensor-grid">${metric("AHT20 temperatura",fmt(d.aht_temperature),"°C")}${metric("Wilgotność",fmt(d.aht_humidity),"%")}${metric("BMP280 temperatura",fmt(d.bmp_temperature),"°C")}${metric("Ciśnienie",fmt(d.bmp_pressure/100),"hPa")}${metric("DS18B20",(d.status&4)?fmt(d.ds_temperature):"N/A","°C")}${metric("Światło / ADC",(d.status&8)?d.light:"N/A")}</div>
      <div class="battery-card mt-3"><div><span>Bateria · INA CH1</span><strong>${hasIna ? `${batteryPct}%` : "N/A"}</strong></div><div class="battery-track"><div class="battery-level" style="width:${hasIna ? batteryPct : 0}%"></div></div><small>${hasIna ? `${fmt(batteryV)} V · Li-ion/LiPo 1S` : "Brak odczytu INA3221"}</small></div>
      <div class="panel-title mt-3"><span><i class="bi bi-lightning-charge"></i> INA3221 · Node ID ${id}</span></div><div class="table-responsive"><table class="table table-dark table-sm align-middle mb-0"><thead><tr><th>Kanał</th><th>Napięcie</th><th>Prąd</th><th>Moc</th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="panel-title mt-3"><span><i class="bi bi-activity"></i> Diagnostyka · Node ID ${id}</span></div><div class="stats-grid"><div><span>Pakiety</span><b>${n.packets||0}</b></div><div><span>Utracone</span><b>${n.lost||0}</b></div><div><span>Ostatnia sekwencja</span><b>${n.last_sequence??"—"}</b></div></div></section>`;
  }).join("") + `<div class="text-secondary small mb-3">Błędy CRC: ${stats.crc_errors||0} · błędy formatu/odbioru: ${stats.packet_errors||0} (liczniki wspólne; uszkodzony pakiet nie pozwala wiarygodnie odczytać Node ID).</div>`;
}

async function refresh() {
  try {
    const r = await fetch("/api/status", {cache:"no-store"});
    const s = await r.json();
    const d = s.last_data;

    $("rxDot").className = s.connected ? "online" : "offline";
    $("rxStatus").textContent = s.connected ? "NRF online" : (s.error || "NRF oczekuje");

    const st=s.stats || {};
    renderNodes(s.nodes, st);

    const c=s.config.nrf;
    setCell("nrfAddress", c.address);
    setCell("nrfChannel", c.channel);
    setCell("nrfPower", powerName(c.power));
    setCell("nrfAck", c.auto_ack ? "ON" : "OFF");

    const m=s.mqtt;
    $("mqttBadge").textContent=m.enabled ? (m.connected ? "ONLINE" : "OFFLINE") : "OFF";
    $("mqttBadge").className="badge " + (m.connected ? "bg-success" : "bg-secondary");
    setCell("mqttBroker", `${m.host}:${m.port}`);
    setCell("mqttTopic", m.base_topic);

    const o=s.oled;
    $("oledBadge").textContent=o.available ? "ONLINE" : (o.enabled ? "OFFLINE" : "OFF");
    $("oledBadge").className="badge " + (o.available ? "bg-success" : "bg-secondary");
    setCell("oledState", o.available ? (o.sleeping ? "Wygaszony" : "Dostępny") : "Niedostępny");
  } catch(e) {
    $("rxStatus").textContent="Błąd WebUI";
  }
}

async function openSettings() {
  const r=await fetch("/api/config");
  const c=await r.json();
  const n=c.nrf, m=c.mqtt, o=c.oled;
  $("ce").value=n.ce_pin; $("csn").value=n.csn_pin; $("channel").value=n.channel;
  $("address").value=n.address; $("power").value=n.power; $("autoAck").checked=n.auto_ack;
  $("mqttEnabled").checked=m.enabled; $("mqttHost").value=m.host; $("mqttPort").value=m.port;
  $("mqttTopicBase").value=m.base_topic; $("mqttUser").value=m.username; $("mqttPass").value="";
  $("mqttQos").value=m.qos; $("mqttRetain").checked=m.retain;
  $("oledEnabled").checked=o.enabled; $("oledBus").value=o.i2c_bus; $("oledAddress").value=o.address; $("oledSeconds").value=o.page_seconds;
  $("oledSaverEnabled").checked=o.screen_saver_enabled ?? true; $("oledOnSeconds").value=o.screen_on_seconds ?? 300; $("oledOffSeconds").value=o.screen_off_seconds ?? 60;
  settingsModal ||= new bootstrap.Modal($("settingsModal"));
  settingsModal.show();
}

async function saveSettings(restart=false) {
  const body={
    nrf:{ce_pin:+$("ce").value,csn_pin:+$("csn").value,channel:+$("channel").value,address:$("address").value,power:+$("power").value,auto_ack:$("autoAck").checked},
    mqtt:{enabled:$("mqttEnabled").checked,host:$("mqttHost").value,port:+$("mqttPort").value,base_topic:$("mqttTopicBase").value,username:$("mqttUser").value,password:$("mqttPass").value,qos:+$("mqttQos").value,retain:$("mqttRetain").checked},
    oled:{enabled:$("oledEnabled").checked,i2c_bus:+$("oledBus").value,address:$("oledAddress").value,page_seconds:+$("oledSeconds").value,screen_saver_enabled:$("oledSaverEnabled").checked,screen_on_seconds:+$("oledOnSeconds").value,screen_off_seconds:+$("oledOffSeconds").value}
  };
  const r=await fetch("/api/config",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const x=await r.json();
  showMessage(x.ok ? x.message : x.error, !!x.ok);
  if (x.ok) {
    settingsModal.hide();
    if (restart) await restartGateway();
    else refresh();
  }
}

async function restartGateway() {
  await fetch("/api/restart",{method:"POST"});
  showMessage("Gateway jest restartowany.");
}

async function mqttTest() {
  const r=await fetch("/api/mqtt/test",{method:"POST"});
  const x=await r.json();
  showMessage(x.message || x.error, !!x.ok);
}
async function oledTest() {
  const r=await fetch("/api/oled/test",{method:"POST"});
  const x=await r.json();
  showMessage(x.message || x.error, !!x.ok);
}

refresh();
setInterval(refresh, 1000);
