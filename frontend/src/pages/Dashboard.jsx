import {useEffect,useState} from 'react';
import {api} from '../services/api';
import MetricCard from '../components/MetricCard';
import Status from '../components/Status';
import {ErrorState,Loading,Empty} from '../components/PageState';

const emptyMetrics={open_tickets:0,active_incidents:0,network_anomalies:0,security_alerts:0,critical_issues:0};
const records=result=>result.status==='fulfilled'&&Array.isArray(result.value)?result.value.filter(item=>item&&typeof item==='object'):[];
const errorOf=result=>result.status==='rejected'?(result.reason?.message||'Unable to load this section.'):result.status==='fulfilled'&&!Array.isArray(result.value)?'The API returned an invalid list.':'';
export default function Dashboard({refresh,onDrilldown}){
 const[data,setData]=useState(null);
 useEffect(()=>{
  let active=true;setData(null);
  Promise.allSettled([api('/dashboard'),api('/incidents'),api('/technicians'),api('/network-events'),api('/security-events')]).then(results=>{
   if(!active)return;
   const [metricsResult,incidentsResult,techniciansResult,networkResult,securityResult]=results;
   const rawMetrics=metricsResult.status==='fulfilled'&&metricsResult.value?.metrics&&typeof metricsResult.value.metrics==='object'?metricsResult.value.metrics:{};
   const metrics=Object.fromEntries(Object.keys(emptyMetrics).map(key=>[key,Number.isFinite(Number(rawMetrics[key]))?Number(rawMetrics[key]):0]));
   setData({metrics,metricsError:metricsResult.status==='rejected'?(metricsResult.reason?.message||'Unable to load dashboard metrics.'):!metricsResult.value?.metrics?'Dashboard metrics were missing from the API response.':'',incidents:records(incidentsResult),technicians:records(techniciansResult),network_events:records(networkResult),security_events:records(securityResult),sectionErrors:[errorOf(incidentsResult),errorOf(techniciansResult),errorOf(networkResult),errorOf(securityResult)]});
  });
  return()=>{active=false};
 },[refresh]);
 if(!data)return <Loading label="Loading operations center…"/>;
 const m=data.metrics,[incidentError,technicianError,networkError,securityError]=data.sectionErrors;
 return <><header className="hero"><div><p className="eyebrow">UNIFIED IT INCIDENT RESPONSE</p><h1>Operations Center</h1><p>Prioritize incidents with connected service-desk, network, and security evidence.</p></div><div className="pulse"><span className="live-dot"/> Monitoring live signals</div></header>
 {data.metricsError?<section className="panel"><ErrorState message={data.metricsError}/></section>:<div className="metrics five"><MetricCard label="Open tickets" value={m.open_tickets??0} hint="Awaiting resolution" onClick={()=>onDrilldown('tickets',{status:'Open'})}/><MetricCard label="Active incidents" value={m.active_incidents??0} tone="orange" hint="Open or investigating" onClick={()=>onDrilldown('incidents',{active:true})}/><MetricCard label="Network anomalies" value={m.network_anomalies??0} tone="red" hint="Threshold exceeded" onClick={()=>onDrilldown('network',{anomalies:true})}/><MetricCard label="Security alerts" value={m.security_alerts??0} tone="purple" hint="High or critical" onClick={()=>onDrilldown('security',{alerts:true})}/><MetricCard label="Critical issues" value={m.critical_issues??0} tone="red" hint="Needs attention" onClick={()=>onDrilldown('tickets',{critical:true})}/></div>}
 <div className="dashboard-grid"><section className="panel wide"><div className="panel-head"><div><h2>Incident activity</h2><span>Operational records with linked evidence</span></div></div>{incidentError?<ErrorState message={incidentError}/>:data.incidents.length?<div className="activity-list">{data.incidents.map((i,index)=><div className="activity" key={i.id??`${i.title}-${i.created_at}-${index}`}><i className="activity-dot"/><div><b>{i.title||'Untitled incident'}</b><small>{i.location||'Location unavailable'} · {i.category||'Unclassified'} · Technician: {i.recommended_technician||'Unassigned'}</small></div><div><b className="priority">P{i.priority??'—'}</b><Status value={i.status||'Unknown'}/></div></div>)}</div>:<Empty>No active incidents. Network correlations will appear here.</Empty>}</section>
 <section className="panel"><div className="panel-head"><div><h2>Technician assignments</h2><span>Current response capacity</span></div></div>{technicianError?<ErrorState message={technicianError}/>:data.technicians.length?data.technicians.map((t,index)=><div className="assignment" key={t.id??`${t.name}-${index}`}><div className="avatar small">{(t.name||'?').split(' ').map(x=>x[0]).join('')}</div><div><b>{t.name||'Technician'}</b><small>{t.specialization||'General'} · workload {t.current_workload??0}</small></div><Status value={t.availability?'Available':'Unavailable'}/></div>):<Empty>No technicians are available.</Empty>}</section>
 <section className="panel"><div className="panel-head"><div><h2>Network signals</h2><span>Latest infrastructure events</span></div></div>{networkError?<ErrorState message={networkError}/>:data.network_events.length?data.network_events.map((e,index)=><div className="signal" key={e.id??`${e.location}-${index}`}><div><b>{e.location||'Location unavailable'}</b><small>{e.event_type||'Network event'} · {e.latency??'—'} ms · {e.packet_loss??'—'}% loss</small></div><Status value={e.severity||'Unknown'}/></div>):<Empty>No network events have been recorded.</Empty>}</section>
 <section className="panel"><div className="panel-head"><div><h2>Security signals</h2><span>Authentication and risk activity</span></div></div>{securityError?<ErrorState message={securityError}/>:data.security_events.length?data.security_events.map((e,index)=><div className="signal" key={e.id??`${e.username}-${index}`}><div><b>{e.event_type||'Security event'}</b><small>{e.username||'Unknown user'} · {e.location||'Location unavailable'} · risk {e.risk_score??'—'}/100</small></div><Status value={e.severity||'Unknown'}/></div>):<Empty>No security events have been recorded.</Empty>}</section></div></>;
}
