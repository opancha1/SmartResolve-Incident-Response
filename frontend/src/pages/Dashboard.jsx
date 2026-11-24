import {useEffect,useState} from 'react';
import {api} from '../services/api';
import MetricCard from '../components/MetricCard';
import Status from '../components/Status';
import {ErrorState,Loading,Empty} from '../components/PageState';
import {formatTime,isTestEndpoint,priorityName,priorityTickets,recentActivity} from '../services/dashboard';

const records=r=>r.status==='fulfilled'&&Array.isArray(r.value)?r.value.filter(x=>x&&typeof x==='object'):[];
const errorOf=r=>r.status==='rejected'?(r.reason?.message||'Unable to load this section.'):!Array.isArray(r.value)?'The API returned an invalid list.':'';
export default function Dashboard({refresh,onDrilldown,canViewSecurity=true}){
 const[data,setData]=useState(null),[now,setNow]=useState(()=>new Date());
 useEffect(()=>{const timer=setInterval(()=>setNow(new Date()),1000);return()=>clearInterval(timer)},[]);
 useEffect(()=>{
  let active=true;
  Promise.allSettled([api('/dashboard'),api('/tickets'),api('/incidents'),api('/technicians'),api('/network-availability'),canViewSecurity?api('/security-events'):Promise.resolve([])]).then(([summary,tickets,incidents,technicians,network,security])=>{
   if(!active)return;
   setData({metrics:summary.status==='fulfilled'?summary.value?.metrics:null,metricsError:summary.status==='rejected'?summary.reason.message:!summary.value?.metrics?'Dashboard metrics are unavailable.':'',checkedAt:new Date(),activity:summary.status==='fulfilled'?summary.value.recent_activity:null,tickets:records(tickets),incidents:records(incidents),technicians:records(technicians),availability:records(network),security:records(security),errors:[tickets,incidents,technicians,network,security].map(errorOf)});
  });
  return()=>{active=false};
 },[refresh,canViewSecurity]);
 if(!data)return <Loading label="Loading operations overview…"/>;
 const [ticketError,incidentError,technicianError,networkError,securityError]=data.errors;
 const m=data.metrics||{},queue=priorityTickets(data.tickets),activity=data.activity||recentActivity(data.tickets,data.incidents);
 const facilities=data.availability.filter(e=>!isTestEndpoint(e)),tests=data.availability.filter(isTestEndpoint);
 const metric=(key)=>Number.isFinite(m[key])?m[key]:'—';
 const endpointRows=endpoints=>endpoints.map(e=><button type="button" className="signal availability-signal" key={e.id} onClick={()=>onDrilldown('network',{status:e.status,includeTests:isTestEndpoint(e)})}><span className="endpoint-copy"><b>{e.building||'Unnamed endpoint'}</b><small>{e.mode==='demo'?'Simulated Demo':e.source||'Source unavailable'}{e.response_ms!=null?` · ${e.response_ms} ms`:''}</small><small>Checked: {formatTime(e.last_checked_at)}</small></span><Status value={e.status||'Unknown'}/></button>);
 return <div className="operations-dashboard">
  <header className="operations-header"><div><p className="eyebrow">SMARTRESOLVE OPERATIONS</p><h1>Operations Overview</h1><p>Service desk, incident response, and monitored endpoint status.</p></div><div className="operations-context"><time dateTime={now.toISOString()}>{now.toLocaleString()}</time><span className={data.metricsError?'api-state api-error':'api-state'}>{data.metricsError?'Dashboard API unavailable':'Dashboard API connected'}</span><small>Last API check: {data.checkedAt.toLocaleTimeString()}</small></div></header>
  {data.metricsError?<ErrorState message={data.metricsError}/>:<div className={`metrics ${canViewSecurity?'five':''}`}>
   <MetricCard label="Open tickets" value={metric('open_status_tickets')} onClick={()=>onDrilldown('tickets',{status:'Open'})}/>
   <MetricCard label="Active incidents" value={metric('active_incidents')} tone="orange" hint="Open or investigating" onClick={()=>onDrilldown('incidents',{active:true})}/>
   <MetricCard label="Offline endpoints" value={metric('campus_offline_endpoints')} tone="red" hint={`${metric('campus_endpoints')} campus endpoints`} onClick={()=>onDrilldown('network',{status:'Offline'})}/>
   {canViewSecurity&&<MetricCard label="Security alerts" value={metric('security_alerts')} tone="purple" hint="Unresolved high or critical events" onClick={()=>onDrilldown('security',{alerts:true})}/>}
   <MetricCard label="Critical issues" value={metric('critical_issues')} tone="red" hint="Unresolved tickets and incidents" onClick={()=>onDrilldown('tickets',{critical:true})}/>
  </div>}
  <div className="operations-main-grid">
   <section className="panel priority-panel"><div className="panel-head"><div><h2>Priority ticket queue</h2><span>Top five unresolved · highest priority, then oldest first</span></div><button className="link-button" onClick={()=>onDrilldown('tickets')}>View all tickets →</button></div>
   {ticketError?<ErrorState message={ticketError}/>:queue.length?<div className="priority-table-wrap"><table><thead><tr><th>Ticket ID</th><th>Issue title</th><th>Location</th><th>Priority</th><th>Technician</th><th>Status</th></tr></thead><tbody>{queue.map(t=><tr key={t.id} className="ticket-row" tabIndex={0} aria-label={`Open ticket ${t.id}: ${t.title}`} onClick={()=>onDrilldown('tickets',{ticketId:t.id})} onKeyDown={e=>{if(e.target===e.currentTarget&&(e.key==='Enter'||e.key===' ')){e.preventDefault();onDrilldown('tickets',{ticketId:t.id})}}}><td>#{t.id}</td><td><button className="link-button" onClick={e=>{e.stopPropagation();onDrilldown('tickets',{ticketId:t.id})}}>{t.title}</button></td><td>{t.location}</td><td><Status value={priorityName(t.priority)}/></td><td>{t.assigned_technician||'Unassigned'}</td><td><Status value={t.status}/></td></tr>)}</tbody></table></div>:<Empty>No unresolved tickets. The queue is clear.</Empty>}</section>
   <section className="panel recent-panel"><div className="panel-head"><div><h2>Recent activity</h2><span>Stored ticket and incident milestones</span></div></div>{ticketError&&<ErrorState message={ticketError}/>} {incidentError&&<ErrorState message={incidentError}/>}{activity.length?<ol className="recent-list">{activity.map(e=><li key={e.key}><span className="activity-marker" aria-hidden="true"/><div><b>{e.label}</b><button className="activity-link" onClick={()=>onDrilldown(e.page,e.page==='tickets'?{ticketId:e.id}:{incidentId:e.id})}>#{e.id} · {e.title}</button><time dateTime={new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(e.at)?e.at:`${e.at}Z`).toISOString()}>{formatTime(e.at)}</time></div></li>)}</ol>:!ticketError&&!incidentError&&<Empty>No ticket or incident activity has been recorded.</Empty>}</section>
  </div>
  <div className="operations-secondary-grid dashboard-grid">
   <section className="panel"><div className="panel-head"><div><h2>Technician assignments</h2><span>Open ticket counts and recorded availability</span></div></div>{technicianError?<ErrorState message={technicianError}/>:data.technicians.length?data.technicians.map(t=><div className="assignment" key={t.id}><div className="avatar small" aria-hidden="true">{t.name?.split(' ').map(x=>x[0]).join('')||'?'}</div><div className="technician-copy"><b>{t.name}</b><small>{t.specialization||'Specialization not recorded'} · {ticketError?'Ticket count unavailable':`${data.tickets.filter(ticket=>ticket.status!=='Resolved'&&ticket.assigned_technician===t.name).length} open tickets`}</small></div><Status value={typeof t.availability==='boolean'?(t.availability?'Available':'Unavailable'):'Unknown'}/></div>):<Empty>No technicians have been added.</Empty>}</section>
   <section className="panel"><div className="panel-head"><div><h2>Building availability</h2><span>Endpoint checks · simulated sources labeled below</span></div></div>{networkError?<ErrorState message={networkError}/>:<>{facilities.length?endpointRows(facilities):<Empty>No facility endpoints are configured.</Empty>}{tests.length>0&&<details className="test-endpoints"><summary>Demo / test endpoints ({tests.length})</summary>{endpointRows(tests)}</details>}</>}</section>
  </div>
  {canViewSecurity&&<section className="panel operations-security"><div className="panel-head"><div><h2>Security signals</h2><span>Recorded authentication and risk events</span></div><button className="link-button" onClick={()=>onDrilldown('security')}>View security →</button></div>{securityError?<ErrorState message={securityError}/>:data.security.length?data.security.slice(0,4).map(e=><div className="signal" key={e.id}><div><b>{e.event_type}</b><small>{e.username} · {e.location} · risk {e.risk_score}/100</small></div><Status value={e.severity}/></div>):<Empty>No security events have been recorded.</Empty>}</section>}
 </div>;
}
