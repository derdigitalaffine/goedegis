import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import './style.css';

const el = (id) => document.getElementById(id);
const api = async (path, options={}) => {
  const r = await fetch('/control/'+path, {headers:{'Content-Type':'application/json'},...options});
  if (!r.ok) throw new Error((await r.text()).slice(0,300));
  return r.json();
};
const message = (s) => {el('status').textContent=s;};
const style = {version:8,sources:{},layers:[{id:'background',type:'background',paint:{'background-color':'#e4e9ed'}}]};
const map = new maplibregl.Map({container:'map',style,center:[9.1,48.7],zoom:7,attributionControl:true});
map.addControl(new maplibregl.NavigationControl(),'top-right');
map.addControl(new maplibregl.ScaleControl(),'bottom-right');
const shapes={type:'FeatureCollection',features:[]};
let points=[];
map.on('load',()=>{
  map.addSource('areas',{type:'geojson',data:shapes});
  map.addLayer({id:'areas-fill',type:'fill',source:'areas',paint:{'fill-color':'#1684cb','fill-opacity':.22}});
  map.addLayer({id:'areas-outline',type:'line',source:'areas',paint:{'line-color':'#126aaf','line-width':2}});
  map.addSource('draft',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
  map.addLayer({id:'draft-line',type:'line',source:'draft',paint:{'line-color':'#ef8b28','line-width':3}});
  refresh();
});
let drawing=false;
el('draw').onclick=()=>{drawing=true;points=[];message('Polygon: Punkte auf Karte anklicken, anschließend „Gebiet speichern“.');};
el('clear').onclick=()=>{drawing=false;points=[];updateDraft();message('Zeichnung zurückgesetzt');};
map.on('click',(e)=>{if(!drawing)return;points.push([e.lngLat.lng,e.lngLat.lat]);updateDraft();});
function updateDraft(){
  if(!map.getSource('draft'))return;
  map.getSource('draft').setData({type:'FeatureCollection',features:points.length>1?[{type:'Feature',geometry:{type:'LineString',coordinates:points},properties:{}}]:[]});
}
el('save').onclick=async()=>{
  if(points.length<3){message('Mindestens drei Eckpunkte zeichnen');return;}
  const coordinates=[...points,points[0]];
  try{
    await api('areas',{method:'POST',body:JSON.stringify({name:el('area-name').value||'Neues Gebiet',geojson:{type:'Polygon',coordinates:[coordinates]},zoom_min:Number(el('zmin').value),zoom_max:Number(el('zmax').value),layers:el('area-layers').value.split(',').map(x=>x.trim()).filter(Boolean),osm_tags:el('area-tags').value.split(',').map(x=>x.trim()).filter(Boolean)})});
    points=[];drawing=false;updateDraft();await refresh();message('Gebiet gespeichert');
  }catch(e){message(e.message);}
};
async function refresh(){
  try{
    const cfg=await api('config');
    shapes.features=cfg.areas.map(a=>({type:'Feature',geometry:a.geojson.type==='Feature'?a.geojson.geometry:a.geojson,properties:{name:a.name}}));
    if(map.getSource('areas'))map.getSource('areas').setData(shapes);
    el('areas').innerHTML='';
    cfg.areas.forEach(a=>{const row=document.createElement('div');row.className='item';const name=document.createElement('span');name.textContent=a.name;const del=document.createElement('button');del.textContent='Löschen';del.onclick=async()=>{await api('areas/'+encodeURIComponent(a.id),{method:'DELETE'});refresh();};row.append(name,del);el('areas').append(row);});
    el('cache-area').innerHTML='';
    cfg.areas.forEach(a=>{const o=document.createElement('option');o.value=a.id;o.textContent=a.name;el('cache-area').append(o);});
    el('cache-source').innerHTML='';
    cfg.sources.filter(s=>s.cache_allowed && ['wms','wmts','xyz'].includes(s.kind)).forEach(s=>{const o=document.createElement('option');o.value=s.id;o.textContent=s.name;el('cache-source').append(o);});
    el('sources').innerHTML='';
    cfg.sources.forEach(s=>{const row=document.createElement('div');row.className='item';const name=document.createElement('span');name.textContent=s.name+' · '+s.kind;const del=document.createElement('button');del.textContent='Löschen';del.onclick=async()=>{await api('sources/'+encodeURIComponent(s.id),{method:'DELETE'});refresh();};row.append(name,del);if(['wms','wmts','wfs'].includes(s.kind)){const check=document.createElement('button');check.textContent='Layer prüfen';check.onclick=async()=>{try{const result=await api('sources/'+encodeURIComponent(s.id)+'/capabilities');message((result.title||s.name)+': '+result.layers.slice(0,8).join(', '));}catch(e){message(e.message);}};row.append(check);}el('sources').append(row);});
  }catch(e){message(e.message);}
}
el('source-form').onsubmit=async(e)=>{
  e.preventDefault();
  try{await api('sources',{method:'POST',body:JSON.stringify({name:el('source-name').value,url:el('source-url').value,kind:el('source-kind').value,layer:el('source-layer').value,cache_allowed:el('source-cache').checked})});await refresh();message('Quelle gespeichert');}catch(e){message(e.message);}
};
el('search-form').onsubmit=async(e)=>{
  e.preventDefault();
  try{
    const r=await fetch('/nominatim/search?q='+encodeURIComponent(el('search').value)+'&format=json&limit=5');
    if(!r.ok)throw new Error('Nominatim nicht verfügbar: Modul geocoding starten');
    const results=await r.json();el('results').innerHTML='';
    results.forEach(p=>{const b=document.createElement('button');b.textContent=p.display_name;b.onclick=()=>map.flyTo({center:[Number(p.lon),Number(p.lat)],zoom:14});el('results').append(b);});
  }catch(e){message(e.message);}
};
el('route').onclick=async()=>{
  try{
    const from=el('from').value.split(',').map(Number),to=el('to').value.split(',').map(Number);
    if(from.length!==2||to.length!==2||[...from,...to].some(n=>!Number.isFinite(n)))throw Error('Koordinaten als lon,lat eingeben');
    const profile=el('profile').value;
    const req={locations:[{lon:from[0],lat:from[1]},{lon:to[0],lat:to[1]}],costing:profile,directions_options:{units:'kilometers'}};
    const r=await fetch('/routing/route?json='+encodeURIComponent(JSON.stringify(req)));
    if(!r.ok)throw Error('Routing-Modul nicht verfügbar');
    const data=await r.json();
    message('Route: '+data.trip.summary.length.toFixed(1)+' km · '+Math.round(data.trip.summary.time/60)+' min');
  }catch(e){message(e.message);}
};
el('tile-style').onclick=async()=>{
  const url='/tiles/styles/basic/style.json';
  try{const r=await fetch(url);if(!r.ok)throw Error('Kein Tile-Style gefunden. MBTiles und Style konfigurieren.');const s=await r.json();map.setStyle(s);message('Lokaler Kartenstil geladen');}catch(e){message(e.message);}
};
el('queue').onclick=async()=>{
  try{const type=el('job-type').value;const url=el('job-url').value;await api('jobs',{method:'POST',body:JSON.stringify({type,payload:{url,table:el('job-table').value},priority:Number(el('priority').value)})});message('Job eingereiht');loadJobs();}catch(e){message(e.message);}
};
async function loadJobs(){
  try{const list=await api('jobs');el('jobs').innerHTML='';list.slice(0,30).forEach(j=>{const d=document.createElement('div');d.className='item';const label=document.createElement('span');label.textContent=j.type+' · '+j.state+' · '+j.progress+'% · '+j.message;d.append(label);const actions=j.state==='running'?['cancel']:j.state==='paused'?['resume','cancel']:['queued','retry_wait'].includes(j.state)?['pause','cancel']:['failed','cancelled'].includes(j.state)?['retry']:[];actions.forEach(action=>{const b=document.createElement('button');b.textContent={pause:'Pause',resume:'Weiter',cancel:'Abbruch',retry:'Erneut'}[action];b.onclick=async()=>{try{await api('jobs/'+encodeURIComponent(j.id)+'/'+action,{method:'POST'});loadJobs();}catch(e){message(e.message);}};d.append(b);});el('jobs').append(d);});const r=await api('resources');el('resources').textContent='CPU '+r.cpu_percent+'% · RAM '+r.memory_percent+'% · Datenträger '+(r.disk_used/1e9).toFixed(1)+' GB';}catch(e){message(e.message);}
}
el('refresh').onclick=()=>{refresh();loadJobs();};
loadJobs();

el('cache-start').onclick=async()=>{
  try{
    if(!el('cache-area').value||!el('cache-source').value)throw Error('Gebiet und cachefähige Quelle auswählen');
    const payload={area_id:el('cache-area').value,source_id:el('cache-source').value,max_tiles:Number(el('cache-limit').value)};
    await api('jobs',{method:'POST',body:JSON.stringify({type:'tile_prewarm',payload,priority:5})});
    message('Cache-Auftrag gestartet');loadJobs();
  }catch(e){message(e.message);}
};
let offlineLayer=null;
el('apply-style').onclick=()=>{
  try{
    const color=el('background-color').value;
    if(map.getLayer('background'))map.setPaintProperty('background','background-color',color);
    const sourceId=el('cache-source').value;
    if(offlineLayer && map.getLayer(offlineLayer))map.removeLayer(offlineLayer);
    if(map.getSource('offline-raster'))map.removeSource('offline-raster');
    if(sourceId){
      map.addSource('offline-raster',{type:'raster',tiles:[location.origin+'/control/cache/'+encodeURIComponent(sourceId)+'/{z}/{x}/{y}.png'],tileSize:256});
      offlineLayer='offline-raster-layer';
      map.addLayer({id:offlineLayer,type:'raster',source:'offline-raster',layout:{visibility:el('layer-visible').checked?'visible':'none'},paint:{'raster-opacity':Number(el('layer-opacity').value)/100}},'areas-fill');
    }
    message('Lokaler Kartenstil aktualisiert');
  }catch(e){message(e.message);}
};
