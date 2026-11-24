import {useEffect,useState} from 'react';
import {api} from '../services/api';
import Status from '../components/Status';
import MetricCard from '../components/MetricCard';
import OperationsDialog from '../components/OperationsDialog';
import InvestigationForm, {Timeline} from '../components/InvestigationForm';
import {Empty, ErrorState, Loading} from '../components/PageState';
import {formatTime, json, statuses} from '../services/operations';

const severities=['Critical','High','Medium','Low'];
function localDate(value){
 const date=new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value)?value:`${value}Z`);
 if(Number.isNaN(date.valueOf()))return '';
 return [date.getFullYear(),String(date.getMonth()+1).padStart(2,'0'),String(date.getDate()).padStart(2,'0')].join('-');
}
const isAlert=event=>event.status!=='Resolved'&&['High','Critical'].includes(event.severity);

export default function Security({refresh,setRefresh,drilldown,clearDrilldown,onDrilldown}){
 const [data,setData]=useState(null), [detail,setDetail]=useState(null), [search,setSearch]=useState('');
 const [status,setStatus]=useState(''), [alertsOnly,setAlertsOnly]=useState(false), [error,setError]=useState('');
 const [severity,setSeverity]=useState(''),[eventType,setEventType]=useState(''),[date,setDate]=useState('');
 const [busy,setBusy]=useState(false), [notice,setNotice]=useState('');

 useEffect(()=>{
  let active=true;
  Promise.all([api('/security-events'),api('/technicians')]).then(([events,technicians])=>{
   if(active)setData({events,technicians});
  }).catch(reason=>{if(active)setError(reason.message)});
  return()=>{active=false};
 },[refresh]);

 useEffect(()=>{
  const id=detail?.event?.id;
  if(!id)return;
  let active=true;
  api(`/security-events/${id}`).then(next=>{if(active)setDetail(next)}).catch(reason=>{if(active)setError(reason.message)});
  return ()=>{active=false};
 },[refresh,detail?.event?.id]);

 async function view(id){
  setError('');
  try {setDetail(await api(`/security-events/${id}`))}
  catch(reason){setError(reason.message)}
 }

 useEffect(()=>{
  if(!drilldown)return;
  setAlertsOnly(!!drilldown.alerts);
  if(drilldown.eventId)view(drilldown.eventId);
  clearDrilldown?.();
 },[drilldown]);

 async function save(payload){
  setBusy(true);setError('');
  try{
   await api(`/security-events/${detail.event.id}`,json('PATCH',payload));
   await view(detail.event.id);
   setRefresh(value=>value+1);
   setNotice('Security investigation updated.');
   return true;
  }catch(reason){setError(reason.message);return false}
  finally{setBusy(false)}
 }

 if(!data)return error?<ErrorState message={error}/>:<Loading label="Loading security events…"/>;
 const {events,technicians}=data;
 const visible=events.filter(event=>(!severity||event.severity===severity)&&(!eventType||event.event_type===eventType)&&(!date||localDate(event.timestamp)===date)&&(!alertsOnly||isAlert(event))&&(!status||event.status===status)&&
  (!search||`#${event.id} ${event.event_type} ${event.username} ${event.location}`.toLowerCase().includes(search.toLowerCase())));
 const event=detail?.event;

 return <>
  <header className="page-title"><div><h1>Security Monitoring</h1><p>Review authentication and endpoint signals and record investigation outcomes.</p></div></header>
  {error&&<ErrorState message={error}/>}
  {notice&&<p className="notice" role="status">{notice}</p>}
  <div className="metrics">
   <MetricCard label="Security alerts" value={events.filter(isAlert).length} tone="red" hint="Unresolved high or critical events"/>
   <MetricCard label="Recorded events" value={events.length}/>
   <MetricCard label="Investigating" value={events.filter(item=>item.status==='Investigating').length}/>
   <MetricCard label="Resolved" value={events.filter(item=>item.status==='Resolved').length}/>
  </div>
  <section className="panel table-wrap workspace-table">
   <div className="panel-head"><div><h2>Security event feed</h2><span>{visible.length} matching events</span></div>
    <div className="filters inline">
     <input value={search} aria-label="Search security events" placeholder="Search events…" onChange={e=>setSearch(e.target.value)}/>
     <select value={status} aria-label="Filter event status" onChange={e=>setStatus(e.target.value)}><option value="">All statuses</option>
      {statuses.map(item=><option key={item}>{item}</option>)}</select>
     <select aria-label="Filter event severity" value={severity} onChange={e=>setSeverity(e.target.value)}><option value="">All severities</option>{severities.map(item=><option key={item}>{item}</option>)}</select>
     <select aria-label="Filter event type" value={eventType} onChange={e=>setEventType(e.target.value)}><option value="">All event types</option>{[...new Set(events.map(item=>item.event_type))].sort().map(item=><option key={item}>{item}</option>)}</select>
     <input type="date" aria-label="Filter detection date" value={date} onChange={e=>setDate(e.target.value)}/>
     <label className="check-filter"><input type="checkbox" checked={alertsOnly} onChange={e=>setAlertsOnly(e.target.checked)}/> Alerts only</label>
    </div>
   </div>
   {visible.length?<table><thead><tr>{['Event','Account or device','Location','Risk score','Severity','Detected','Status','Assigned technician','Incidents'].map(item=><th key={item}>{item}</th>)}</tr></thead>
    <tbody>{visible.map(item=><tr key={item.id}><td><button className="link-button" onClick={()=>view(item.id)}>#{item.id} · {item.event_type}</button>
     {(item.demo_key||item.username?.startsWith('demo.'))&&<small className="record-source">Simulated Demo</small>}</td>
     <td>{item.username}</td><td>{item.location||'—'}</td><td><div className="risk-indicator"><b>{item.risk_score}/100</b><meter aria-label={`Risk score ${item.risk_score} of 100`} min="0" max="100" value={item.risk_score}/></div></td><td><Status value={item.severity}/></td>
     <td>{formatTime(item.timestamp)}</td><td><Status value={item.status}/></td><td>{item.assigned_technician||'Unassigned'}</td><td>{item.incident_count}</td></tr>)}</tbody>
   </table>:<Empty>No security events match the current filters.</Empty>}
  </section>
  {event&&<OperationsDialog title={event.event_type} label={`Security event #${event.id}${event.demo_key||event.username?.startsWith('demo.')?' · Simulated Demo':''}`} onClose={()=>setDetail(null)}>
   <p>{detail.description}</p>
   <p><Status value={event.severity}/> · {event.risk_score}/100 · {event.location||'Location unavailable'} · {formatTime(event.timestamp)}</p>
   <p>{Object.entries(detail.risk_factors).map(([name,points])=>`${name} +${points}`).join(' · ')}. Failed attempts contribute ten points each, capped at 65. The combined score is capped at 100 and helps prioritize review. Confirm findings through investigation.</p>
   <section className="investigation-section"><h3>Evidence</h3><ul>{detail.evidence.map(item=><li key={item}>{item}</li>)}</ul>
    <h3>Recommended investigation steps</h3><ol>{detail.recommended_steps.map(item=><li key={item}>{item}</li>)}</ol>
    <h3>Related records</h3>
    {detail.incidents.map(item=><div key={item.id}><button className="link-button" onClick={()=>onDrilldown('incidents',{incidentId:item.id})}>Incident #{item.id} · {item.title}</button></div>)}
    {detail.tickets.map(item=><div key={item.id}><button className="link-button" onClick={()=>onDrilldown('tickets',{ticketId:item.id})}>Ticket #{item.id} · {item.title}</button></div>)}
    {!detail.incidents.length&&!detail.tickets.length&&<p>No related records linked.</p>}
   </section>
   {event.resolution&&<p><b>Resolution</b> · {event.resolution}</p>}
   <Timeline entries={detail.timeline}/>
   <InvestigationForm key={event.id} record={event} technicians={technicians} busy={busy} onSave={save}/>
   {error&&<ErrorState message={error}/>}
  </OperationsDialog>}
 </>;
}
