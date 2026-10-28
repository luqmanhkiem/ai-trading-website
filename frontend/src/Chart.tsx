import {useEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {Maximize2,Minimize2,RotateCcw} from 'lucide-react';
import {candleWindow,zoomBars,priceZoom,axisDragScale} from './chartView';
import type {Candle,Signal,AnalysisFrame} from './types';
import {money,date} from './format';
export function Chart({bars,label,setup,frame}:{bars:Candle[];label:string;setup?:Signal;frame?:AnalysisFrame}){
  const [layers,setLayers]=useState({zones:true,gaps:true,structure:true,sweeps:false,swings:false});
  const [hover,setHover]=useState<number|null>(null);
  const [count,setCount]=useState(64),[offset,setOffset]=useState(0),[vertical,setVertical]=useState(0),[scale,setScale]=useState(1),[expanded,setExpanded]=useState(false);
  const [canvasSize,setCanvasSize]=useState({width:900,height:285});
  const svgRef=useRef<SVGSVGElement>(null),shellRef=useRef<HTMLDivElement>(null),expandRef=useRef<HTMLButtonElement>(null);
  const drag=useRef<{x:number;y:number;offset:number;vertical:number;axis:boolean;scale:number;size:number;width:number;height:number}|null>(null);
  const view=candleWindow(bars.length,count,offset);
  const data=bars.slice(view.start,view.end), width=canvasSize.width,height=canvasSize.height,pad=16,right=76;
  useEffect(()=>{
    if(!svgRef.current)return;
    const svg=svgRef.current,observer=new ResizeObserver(()=>{const r=svg.getBoundingClientRect();if(r.width>0&&r.height>0)setCanvasSize({width:Math.max(300,Math.round(r.width)),height:Math.max(180,Math.round(r.height))})});
    observer.observe(svg);return()=>observer.disconnect();
  },[expanded,bars.length===0]);
  function reset(){setCount(64);setOffset(0);setVertical(0);setScale(1);setHover(null)}
  useEffect(()=>{
    const svg=svgRef.current;if(!svg)return;
    const wheel=(event:WheelEvent)=>{
      event.preventDefault();setHover(null);
      const bounds=svg.getBoundingClientRect(),axis=(event.clientX-bounds.left)/bounds.width>(width-right)/width;
      const direction=Math.sign(event.deltaY||event.deltaX);
      if(!direction)return;
      if(axis){if(event.ctrlKey||event.metaKey)setScale(v=>priceZoom(v*(direction>0?1.15:1/1.15)));else setVertical(v=>v+direction*.1)}
      else if(event.shiftKey||Math.abs(event.deltaX)>Math.abs(event.deltaY))setOffset(v=>candleWindow(bars.length,count,v+direction*Math.max(1,Math.round(count*.1))).offset);
      else setCount(v=>zoomBars(v,direction>0?1.15:1/1.15,bars.length));
    };
    svg.addEventListener('wheel',wheel,{passive:false});return()=>svg.removeEventListener('wheel',wheel);
  },[bars.length,count,expanded,width]);
  useEffect(()=>{
    if(!expanded)return;
    const previous=document.activeElement as HTMLElement|null,overflow=document.body.style.overflow;
    document.body.style.overflow='hidden';expandRef.current?.focus();
    const key=(event:KeyboardEvent)=>{if(event.key==='Escape'){event.preventDefault();event.stopPropagation();setExpanded(false)}
      if(event.key==='Tab'){const nodes=Array.from(shellRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled),svg[tabindex="0"]')||[]),first=nodes[0],last=nodes[nodes.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}}};
    document.addEventListener('keydown',key);return()=>{document.body.style.overflow=overflow;document.removeEventListener('keydown',key);previous?.focus()};
  },[expanded]);
  if(!data.length)return <div className="empty">Waiting for candle data…</div>;
  const possible=frame?.zones||[];
  const zoneLevels=layers.zones?possible.flatMap(z=>[z.low,z.high]):[];
  const levels=setup?[setup.entry_low,setup.entry_high,setup.stop,...setup.targets]:[];
  const baseLo=Math.min(...data.map(b=>b.low),...levels,...zoneLevels)-2,baseHi=Math.max(...data.map(b=>b.high),...levels,...zoneLevels)+2;
  const baseSpan=Math.max(.01,baseHi-baseLo),span=baseSpan*scale,mid=(baseLo+baseHi)/2+vertical*baseSpan;
  const lo=mid-span/2,hi=mid+span/2;
  const y=(p:number)=>pad+(hi-p)/(hi-lo)*(height-2*pad);
  const step=(width-right-pad)/data.length;
  const zoneIndex=setup?data.findIndex(b=>b.time>=(setup.zone_time||0)):0;
  const zoneX=zoneIndex>=0?Math.max(0,pad+zoneIndex*step-step/2):0;
  const last=data[data.length-1]; const selected=hover===null||hover>=data.length?last:data[hover];
  const content=<div ref={shellRef} className={expanded?'chart-shell expanded':'chart-shell'} role={expanded?'dialog':undefined} aria-modal={expanded?true:undefined} aria-label={expanded?'Expanded price chart':undefined}><div className="chart-controls" aria-label="Chart navigation"><div className="chart-control-group"><button aria-label="Reset chart view" onClick={reset}><RotateCcw size={14}/> Reset</button><button ref={expandRef} aria-label={expanded?'Restore chart':'Maximize chart'} onClick={()=>setExpanded(v=>!v)}>{expanded?<Minimize2 size={15}/>:<Maximize2 size={15}/>} {expanded?'Restore':'Expand'}</button></div></div><div className="overlay-toolbar" aria-label="Chart overlays">{(Object.keys(layers) as (keyof typeof layers)[]).map(k=><button key={k} aria-pressed={layers[k]} onClick={()=>setLayers(v=>({...v,[k]:!v[k]}))}>{({zones:'Supply / demand',gaps:'FVG',structure:'Structure',sweeps:'Sweeps',swings:'Pivots'})[k]}</button>)}</div><div className="chart-ohlc"><span>{hover===null?'Latest candle':date(selected.time)}</span><span>O <b>{money(selected.open)}</b></span><span>H <b>{money(selected.high)}</b></span><span>L <b>{money(selected.low)}</b></span><span>C <b className={selected.close>=selected.open?'green':'red'}>{money(selected.close)}</b></span></div><svg ref={svgRef} tabIndex={0} onDoubleClick={e=>{const r=e.currentTarget.getBoundingClientRect();if((e.clientX-r.left)/r.width>(width-right)/width){setScale(1);setVertical(0)}}} onKeyDown={e=>{if(e.key==='ArrowLeft'){e.preventDefault();setOffset(view.offset+5)}if(e.key==='ArrowRight'){e.preventDefault();setOffset(Math.max(0,view.offset-5))}if(e.key==='ArrowUp'){e.preventDefault();setVertical(v=>v+.1)}if(e.key==='ArrowDown'){e.preventDefault();setVertical(v=>v-.1)}if(e.key==='+'||e.key==='='){e.preventDefault();setCount(zoomBars(view.size,.8,bars.length))}if(e.key==='-'){e.preventDefault();setCount(zoomBars(view.size,1.25,bars.length))}if(e.key==='Home'){e.preventDefault();reset()}}} onPointerDown={e=>{if(e.button!==0)return;const r=e.currentTarget.getBoundingClientRect();e.currentTarget.setPointerCapture(e.pointerId);drag.current={x:e.clientX,y:e.clientY,offset:view.offset,vertical,axis:(e.clientX-r.left)/r.width>(width-right)/width,scale,size:view.size,width:r.width,height:r.height};setHover(null)}} onPointerMove={e=>{const d=drag.current;if(!d)return;const dx=e.clientX-d.x,dy=e.clientY-d.y;if(d.axis){setScale(axisDragScale(d.scale,dy,d.height))}else{setOffset(candleWindow(bars.length,d.size,d.offset+dx/d.width*d.size*width/(width-right-pad)).offset);setVertical(d.vertical+dy/d.height*d.scale*height/(height-2*pad))}setHover(null)}} onPointerUp={()=>{drag.current=null}} onPointerCancel={()=>{drag.current=null}} onLostPointerCapture={()=>{drag.current=null}} viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label={label} onMouseLeave={()=>setHover(null)}>
  {[0,1,2,3,4].map(i=>{const p=lo+(hi-lo)*i/4;return <g key={i}><line x1="0" x2={width-right} y1={y(p)} y2={y(p)} stroke="#23232e" strokeDasharray="3 5"/><text x={width-right+12} y={y(p)+4} fill="#828291" fontSize="11">{money(p)}</text></g>})}
  {layers.zones&&possible.filter(z=>z.high>=lo&&z.low<=hi).map(z=>{const color=z.side==='BUY'?'#458eff':'#f34759',top=Math.max(0,y(z.high)),bottom=Math.min(height,y(z.low));return <g key={`${z.time}-${z.side}`} aria-label={`Possible ${z.kind} zone ${money(z.low)} to ${money(z.high)}`}><title>{`Possible ${z.kind}: ${money(z.low)}–${money(z.high)}. ${z.tested?'Retested':'Untested'}. ${z.method}`}</title><rect x="0" y={top} width={width-right} height={Math.max(2,bottom-top)} fill={color} fillOpacity="0.17"/><line x1="0" x2={width-right} y1={y(z.high)} y2={y(z.high)} stroke={color} strokeWidth="1.5"/><line x1="0" x2={width-right} y1={y(z.low)} y2={y(z.low)} stroke={color} strokeWidth="1.5"/><text x="8" y={Math.max(12,top-5)} fill={color} fontSize="10">{`POSSIBLE ${z.side==='BUY'?'BUY / DEMAND':'SELL / SUPPLY'} ZONE`}</text>{[z.high,z.low].map((p,i)=>y(p)>=0&&y(p)<=height?<g key={i}><rect x={width-right+1} y={y(p)-8} width={right-2} height="16" rx="3" fill={color}/><text x={width-right+5} y={y(p)+4} fill="#fff" fontSize="10">{money(p)}</text></g>:null)}</g>})}
  {setup&&layers.zones&&<g aria-label={`${setup.zone_type} zone ${money(setup.entry_low)} to ${money(setup.entry_high)}`}><rect x={zoneX} y={y(setup.entry_high)} width={width-right-zoneX} height={Math.max(2,y(setup.entry_low)-y(setup.entry_high))} fill={setup.side==='BUY'?'#53d8a5':'#e77c86'} opacity="0.16"/><text x="8" y={y(setup.entry_high)-5} fill="#b9b3cd" fontSize="11">{setup.zone_type?.toUpperCase()} ZONE</text>{[{p:setup.stop,name:'SL',color:'#e77c86'},{p:setup.targets[2],name:setup.rr_targets?`TP3 · ${setup.rr_targets[2]}R`:'TP3 · structure',color:'#53d8a5'}].map(l=><g key={l.name}><line x1="0" x2={width-right} y1={y(l.p)} y2={y(l.p)} stroke={l.color} strokeDasharray="3 5"/><text x="8" y={y(l.p)-4} fill={l.color} fontSize="11">{l.name} {money(l.p)}</text></g>)}</g>}
  {layers.gaps&&frame?.gaps.filter(g=>g.high>=lo&&g.low<=hi).map(g=>{const index=data.findIndex(b=>b.time>=g.time),x=index<0?0:pad+index*step;return <g key={`${g.time}-${g.side}`}><rect x={x} width={Math.max(0,width-right-x)} y={y(Math.min(g.high,hi))} height={Math.max(1,y(Math.max(g.low,lo))-y(Math.min(g.high,hi)))} fill={g.side==='bullish'?'#40ba96':'#e6955b'} opacity="0.10"/><text x={x+3} y={y(Math.min(g.high,hi))+10} fontSize="9" fill="#9f9aac">FVG {g.partial?'· partial':''}</text></g>})}
  {layers.structure&&frame?.protected!=null&&frame.protected>=lo&&frame.protected<=hi&&<g><line x1="0" x2={width-right} y1={y(frame.protected)} y2={y(frame.protected)} stroke="#e0b86c" strokeDasharray="7 4"/><text x="8" y={y(frame.protected)-5} fill="#e0b86c" fontSize="10">Protected {frame.bias==='bullish'?'low':'high'} {money(frame.protected)}</text></g>}
  {data.map((b,i)=>{const col=b.close>=b.open?'#53d8a5':'#e77c86',x=pad+i*step;return <g key={b.time} onMouseEnter={()=>setHover(i)}><rect x={x-step/2} y="0" width={step} height={height} fill="transparent"/><line x1={x} x2={x} y1={y(b.high)} y2={y(b.low)} stroke={col}/><rect x={x-step*.3} width={step*.6} y={y(Math.max(b.open,b.close))} height={Math.max(1.5,Math.abs(y(b.open)-y(b.close)))} fill={col} rx="1"/></g>})}
  {layers.structure&&frame?.events.filter(e=>e.time>=data[0].time&&e.time<=last.time).map((e,n)=>{const i=data.findIndex(b=>b.time===e.time);return i<0?null:<g key={`${e.time}-${n}`}><circle cx={pad+i*step} cy={y(e.price)} r="3" fill="#e0b86c"/><text x={pad+i*step+4} y={y(e.price)-9} fill="#e0b86c" fontSize="9">{e.kind}</text></g>})}
  {layers.swings&&frame?.swings.filter(s=>s.time>=data[0].time&&s.time<=last.time).map(s=>{const i=data.findIndex(b=>b.time===s.time);return i<0?null:<text key={`${s.time}-${s.kind}`} x={pad+i*step} y={y(s.price)+(s.kind==='high'?-6:14)} fill="#c2b5dd" fontSize="9" textAnchor="middle">{s.kind==='high'?'SH':'SL'}</text>})}
  {layers.sweeps&&frame?.sweeps.filter(s=>s.time>=data[0].time&&s.time<=last.time).map(s=>{const i=data.findIndex(b=>b.time===s.time);return i<0?null:<g key={`${s.time}-${s.side}`}><circle cx={pad+i*step} cy={y(s.price)} r="4" fill={s.side==='bullish'?'#53d8a5':'#e77c86'}/><text x={pad+i*step+6} y={y(s.price)-5} fill="#c8bccf" fontSize="9">Sweep</text></g>})}
  <line x1="0" x2={width-right} y1={y(last.close)} y2={y(last.close)} stroke="#b39aff" strokeDasharray="4 4"/><rect x={width-right+3} y={Math.max(0,Math.min(height-21,y(last.close)-10))} width="71" height="21" rx="4" fill="#a68aee"/><text x={width-right+8} y={Math.max(14,Math.min(height-7,y(last.close)+4))} fill="#101019" fontSize="11" fontWeight="700">{money(last.close)}</text>
  <rect className="price-axis-hit" data-testid="price-axis" x={width-right} y="0" width={right} height={height} fill="transparent"><title>Hold and drag up/down to change the price scale. Double-click to restore automatic scale.</title></rect>
  </svg>{layers.zones&&<div className="zone-legend" aria-label="Possible supply and demand areas"><span>Dashed areas = possible zones, not entry signals.</span>{possible.length?possible.map(z=><span key={`${z.time}-${z.side}`} style={{color:z.side==='BUY'?'#458eff':'#f34759'}}>{z.kind.toUpperCase()} {money(z.low)}–{money(z.high)} · {z.tested?'retested':'untested'}</span>):<span>No intact base/displacement zones found on this timeframe.</span>}</div>}<div className="chart-times">{Array.from(new Set([0,Math.floor((data.length-1)/4),Math.floor((data.length-1)/2),Math.floor((data.length-1)*3/4),data.length-1])).map(i=><span key={i}>{new Date(data[i].time*1000).toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'UTC'})}</span>)}</div></div>;
  return expanded?createPortal(content,document.body):content;
}
