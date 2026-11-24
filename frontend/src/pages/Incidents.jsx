import {useEffect,useState} from 'react';
import {api} from '../services/api';
import Status from '../components/Status';
import MetricCard from '../components/MetricCard';
import OperationsDialog from '../components/OperationsDialog';
import InvestigationForm, {Timeline} from '../components/InvestigationForm';
import {Empty, ErrorState, Loading} from '../components/PageState';
import {categories, formatTime, json, priorityName, statuses} from '../services/operations';

const blank = {title:'',description:'',category:'Network',location:'',ticket_ids:[]};

export default function Incidents({refresh,setRefresh,drilldown,clearDrilldown,onDrilldown}) {
 const [data,setData]=useState(null), [selected,setSelected]=useState(null), [creating,setCreating]=useState(null);
 const [status,setStatus]=useState(''), [search,setSearch]=useState(''), [ticketId,setTicketId]=useState('');
 const [priority,setPriority]=useState(''),[location,setLocation]=useState(''),[technician,setTechnician]=useState(''),[review,setReview]=useState(null),[reviewEvidence,setReviewEvidence]=useState(null);
 const [error,setError]=useState(''), [notice,setNotice]=useState(''), [busy,setBusy]=useState(false);

 useEffect(()=>{
  let active=true;
  Promise.all(['/incidents','/incidents/recommendations','/technicians','/tickets'].map(path=>api(path)))
   .then(([items,recommendations,technicians,tickets])=>{if(active)setData({items,recommendations,technicians,tickets})})
   .catch(reason=>{if(active)setError(reason.message)});
  return ()=>{active=false};
 },[refresh]);

 useEffect(()=>{
  const id=selected?.incident?.id;
  if(!id)return;
  let active=true;
  api(`/incidents/${id}`).then(next=>{if(active)setSelected(next)}).catch(reason=>{if(active)setError(reason.message)});
  return ()=>{active=false};
 },[refresh,selected?.incident?.id]);

 async function view(id) {
  setError('');
  try { setSelected(await api(`/incidents/${id}`)); setTicketId(''); }
  catch (reason) { setError(reason.message); }
 }

 useEffect(()=>{
  if (!drilldown) return;
  if (drilldown.active) setStatus('active');
  if (drilldown.incidentId) view(drilldown.incidentId);
  clearDrilldown?.();
 },[drilldown]);

 async function reviewGroup(item){
  if(!item.incident_id){setCreating(item);return}
  setError('');setReviewEvidence(null);setReview(item);
  try{setReviewEvidence(await api(`/incidents/${item.incident_id}`))}
  catch(reason){setError(reason.message)}
 }

 async function change(path,options,message) {
  setBusy(true);setError('');
  try {
   const result=await api(path,options);
   setRefresh(value=>value+1);
   setNotice(message);
   return {result};
  } catch (reason) {
   setError(reason.message);
   return null;
  } finally { setBusy(false); }
 }

 async function save(event) {
  event.preventDefault();
  const payload=Object.fromEntries(Object.keys(blank).map(key=>[key,creating[key]]));
  const response=await change('/incidents',json('POST',payload),'Incident created.');
  if(response){setCreating(null);await view(response.result.id);}
 }

 if (!data) return error?<ErrorState message={error}/>:<Loading label="Loading incidents…"/>;
 const {items,recommendations,technicians,tickets}=data;
 const visible=items.filter(item=>(!priority||priorityName(item.priority)===priority)&&(!location||location===item.location)&&(!technician||technician===(item.assigned_technician||'Unassigned'))&&(!status||(status==='active'?item.status!=='Resolved':item.status===status))&&
  (!search||`#${item.id} ${item.title} ${item.location} ${item.category}`.toLowerCase().includes(search.toLowerCase())));
 const incident=selected?.incident;
 const linked=new Set(selected?.relationships.filter(item=>item.type==='ticket').map(item=>item.item.id));

 return <>
  <header className="page-title"><div><h1>Incidents</h1><p>Review shared issues, evidence, and investigations.</p></div>
   <div className="actions"><button className="secondary" disabled={busy} onClick={()=>
    change('/incidents/correlate',{method:'POST'},'Network evidence reviewed. Check the queue for linked investigations.')
   }>Correlate network evidence</button><button onClick={()=>{setError('');setCreating(blank)}}>Create Incident</button></div></header>
  {error&&<ErrorState message={error}/>}
  {notice&&<p className="notice" role="status">{notice}</p>}
  <div className="metrics five">
   <MetricCard label="Active incidents" value={items.filter(item=>item.status!=='Resolved').length}/>
   <MetricCard label="Investigating" value={items.filter(item=>item.status==='Investigating').length}/>
   <MetricCard label="Resolved" value={items.filter(item=>item.status==='Resolved').length}/>
   <MetricCard label="Unresolved high priority" value={items.filter(item=>item.priority>50&&item.status!=='Resolved').length} tone="orange"/>
   <MetricCard label="Pending recommendations" value={recommendations.length}/>
  </div>
  {recommendations.length>0&&<section className="panel scenario-recommendations"><h2>Recommended incident groups</h2>
   {recommendations.map(item=><div className="investigation-row" key={item.id}>
    <div><b>{item.title}</b><p>{item.location} · Tickets {item.ticket_ids.map(id=>`#${id}`).join(', ')} · {item.reported_impact} reported affected across tickets{item.demo?' · Simulated Demo':''}</p>
    <p>{item.description}</p>
    {item.similarity_evidence.map(match=><small className="record-source" key={match.id}>#{match.id} · {Math.round(match.similarity*100)}% text similarity · {match.evidence.join(', ')}{match.same_room?' · Same room':''}</small>)}</div>
    <div className="actions"><button className="secondary" onClick={()=>reviewGroup(item)}>Review group</button>
    <button className="secondary" disabled={busy} onClick={()=>change(`/incidents/recommendations/${item.id}/dismiss`,{method:'POST'},'Recommendation dismissed.')}>Dismiss</button></div>
   </div>)}
  </section>}
  <section className="panel table-wrap workspace-table">
   <div className="panel-head"><div><h2>Incident queue</h2><span>{visible.length} matching incidents</span></div>
    <div className="filters inline"><input aria-label="Search incidents" placeholder="Search incidents…" value={search} onChange={event=>setSearch(event.target.value)}/>
     <select aria-label="Filter incident status" value={status} onChange={event=>setStatus(event.target.value)}><option value="">All statuses</option>
      <option value="active">Active</option>{statuses.map(item=><option key={item}>{item}</option>)}</select>{[[priority,setPriority,'All priorities',['Critical','High','Medium','Low']],
      [location,setLocation,'All locations',[...new Set(items.map(item=>item.location))]],
      [technician,setTechnician,'All technicians',[...new Set(items.map(item=>item.assigned_technician||'Unassigned'))]]].map(([value,setter,label,values])=>
      <select key={label} aria-label={label} value={value} onChange={event=>setter(event.target.value)}><option value="">{label}</option>{values.map(option=><option key={option}>{option}</option>)}</select>)}</div></div>
   {visible.length?<table><thead><tr>{['Incident','Building','Tickets','Priority','Assigned technician','Status','Created','Updated'].map(item=><th key={item}>{item}</th>)}</tr></thead>
    <tbody>{visible.map(item=><tr key={item.id}><td><button className="link-button" onClick={()=>view(item.id)}>#{item.id} · {item.title}</button>
     {(item.demo_key||item.demo_context)&&<small className="record-source">Simulated Demo</small>}</td><td>{item.location}</td><td>{item.related_ticket_count}</td>
     <td><Status value={priorityName(item.priority)}/></td><td>{item.assigned_technician||'Unassigned'}</td><td><Status value={item.status}/></td>
     <td>{formatTime(item.created_at)}</td><td>{formatTime(item.updated_at||item.resolved_at||item.created_at)}</td></tr>)}</tbody></table>:<Empty>No incidents match the current filters.</Empty>}
  </section>
  {review&&<OperationsDialog title={review.title} label="Incident recommendation" onClose={()=>setReview(null)}>
   <p>{review.description}</p><p>{review.location} · {review.reported_impact} reported affected across tickets</p>
   <ul>{review.ticket_ids.map(id=><li key={id}><button className="link-button" onClick={()=>onDrilldown('tickets',{ticketId:id})}>Review ticket #{id}</button></li>)}</ul>
   {reviewEvidence?.relationships.filter(item=>item.type!=='ticket').map(({id,item,type,reason})=>
    <div className="investigation-row" key={id}><div><b>{item.event_type||`Endpoint status · ${item.status}`}</b><p>{reason}</p></div>
    {type==='security'&&<button className="secondary" onClick={()=>onDrilldown('security',{eventId:item.id})}>Review event</button>}</div>)}
   {error&&<ErrorState message={error}/>}
   <button disabled={busy} onClick={async()=>{const response=await change(`/incidents/recommendations/${review.incident_id}/accept`,{method:'POST'},'Recommendation accepted.');if(response){setReview(null);await view(response.result.id)}}}>Accept and open incident</button>
  </OperationsDialog>}
  {creating&&<OperationsDialog title="Create incident" onClose={()=>setCreating(null)}>
   <form className="form" onSubmit={save}>
    <label>Title<input required minLength={3} maxLength={180} value={creating.title} onChange={event=>setCreating({...creating,title:event.target.value})}/></label>
    <label>Summary<textarea required minLength={3} maxLength={5000} value={creating.description} onChange={event=>setCreating({...creating,description:event.target.value})}/></label>
    <label>Building or location<input required minLength={2} maxLength={100} value={creating.location} onChange={event=>setCreating({...creating,location:event.target.value})}/></label>
    <label>Category<select value={creating.category} onChange={event=>setCreating({...creating,category:event.target.value})}>
     {Object.entries(categories).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
    <label>Related tickets<select multiple value={creating.ticket_ids.map(String)}
     onChange={event=>setCreating({...creating,ticket_ids:[...event.target.selectedOptions].map(option=>Number(option.value))})}>
     {tickets.filter(ticket=>ticket.status!=='Resolved').map(ticket=><option key={ticket.id} value={ticket.id}>#{ticket.id} · {ticket.title}</option>)}</select></label>
    <button disabled={busy}>Create incident</button>
    {error&&<ErrorState message={error}/>}
   </form>
  </OperationsDialog>}
  {incident&&<OperationsDialog title={incident.title} label={`Incident #${incident.id}${incident.demo_key||incident.demo_context?' · Simulated Demo':''}`} onClose={()=>setSelected(null)}>
   <p>{incident.description}</p>
   <p><Status value={incident.status}/> · {incident.location} · Priority {incident.priority}/100</p>
   <p>Created {formatTime(incident.created_at)} · Updated {formatTime(incident.updated_at||incident.resolved_at||incident.created_at)}</p>
   <p>Recommended technician · {incident.recommended_technician||'Unavailable'}</p>
   {selected.possible_cause&&<p><b>Root cause to investigate</b> · {selected.possible_cause}</p>}
   {incident.confirmed_cause&&<p><b>Confirmed root cause</b> · {incident.confirmed_cause}</p>}
   {incident.resolution&&<p><b>Resolution</b> · {incident.resolution}</p>}
   <section className="investigation-section"><h3>Linked tickets and evidence</h3>
    {selected.relationships.length===0&&<p>No evidence linked.</p>}
    {selected.relationships.map(({id,type,item,reason})=><div className="investigation-row" key={id}><div>
     {type==='ticket'||type==='security'?<button className="link-button" onClick={()=>onDrilldown(type==='ticket'?'tickets':'security',type==='ticket'?{ticketId:item.id}:{eventId:item.id})}>
      #{item.id} · {item.title||item.event_type}</button>:<b>{item.event_type||`Endpoint status · ${item.status}`}</b>}
     <p>{reason}</p></div>
     {type==='ticket'&&<button className="secondary compact" disabled={busy} onClick={async()=>{
      if(await change(`/incidents/${incident.id}/tickets/${item.id}`,{method:'DELETE'},'Ticket unlinked.')) await view(incident.id);
     }}>Unlink</button>}
    </div>)}
    <form className="filters inline" onSubmit={async event=>{
     event.preventDefault();
     if(await change(`/incidents/${incident.id}/tickets/${ticketId}`,{method:'PUT'},'Ticket linked.')) await view(incident.id);
    }}><select aria-label="Ticket to link" required value={ticketId} onChange={event=>setTicketId(event.target.value)}>
     <option value="">Select a ticket</option>{tickets.filter(ticket=>!linked.has(ticket.id)&&(!incident.demo_key||ticket.demo_key)).map(ticket=>
      <option key={ticket.id} value={ticket.id}>#{ticket.id} · {ticket.title}</option>)}</select>
     <button disabled={busy||!ticketId}>Link ticket</button></form>
   </section>
   <Timeline entries={selected.timeline}/>
   <InvestigationForm key={incident.id} record={incident} technicians={technicians} includeCause busy={busy} onSave={async payload=>{
    if(!await change(`/incidents/${incident.id}`,json('PATCH',payload),'Investigation updated.')) return false;
    await view(incident.id);return true;
   }}/>
   {error&&<ErrorState message={error}/>}
  </OperationsDialog>}
 </>;
}
