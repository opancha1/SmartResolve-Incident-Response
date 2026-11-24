import {useState} from 'react';
import {api} from '../services/api';
import {json} from '../services/operations';
import {ErrorState} from '../components/PageState';
import OperationsDialog from '../components/OperationsDialog';

const scenarios = [
 ['capstone','Load Capstone Dataset','Load the presentation dataset with 20 tickets, eight incidents, building checks, and fictional security evidence.',true],
 ['network-outage','Trigger Network Outage','Record failed Atkins Library endpoint checks and recommend a related Wi-Fi incident.'],
 ['suspicious-login','Trigger Suspicious Login Activity','Record synthetic authentication events, an account lockout report, and a security incident recommendation.',true],
 ['classroom-av','Trigger Classroom AV Failure','Create related projector tickets for Woodward Hall, Room 120.'],
 ['duplicate-tickets','Trigger Duplicate Tickets','Create two reports describing the same docking station fault.'],
 ['campus-software','Trigger Campus-Wide Software Issue','Create related LockDown Browser reports with an estimated campus-wide impact.'],
 ['network-recovery','Simulate Network Recovery','Record a successful endpoint check and add evidence for technician review.'],
 ['network-unknown','Simulate Unknown Status','Record an inconclusive endpoint check.'],
 ['load','Load Demo Dataset','Run the outage, authentication, classroom, duplicate, and software scenarios.',true],
];

export default function Demo({setRefresh,canViewSecurity,onDrilldown}){
 const [busy,setBusy]=useState(''), [result,setResult]=useState(null), [error,setError]=useState('');
 const [confirm,setConfirm]=useState(false);
 async function run(action){
  setBusy(action);setError('');setResult(null);
  try{
   setResult(await api(`/demo/${action}`,json('POST',{confirm:action==='reset'})));
   setRefresh(value=>value+1);setConfirm(false);
  }catch(reason){setError(reason.message)}
  finally{setBusy('')}
 }
 return <>
  <header className="page-title"><div><h1>Demo Control Center</h1><p>Run connected synthetic scenarios and review the resulting records in Operations.</p></div></header>
  {error&&<ErrorState message={error}/>}
  {result&&<div className="notice" role="status">
   <p>{result.message}</p>
   {result.tickets!=null&&<p>{result.tickets} tickets · {result.incidents} incidents · {result.endpoints} endpoints · {result.security_events} security events · {result.technicians} technicians</p>}
   {result.incident_id&&<button className="link-button" onClick={()=>onDrilldown('incidents')}>Review recommendation #{result.incident_id}</button>}
   {result.ticket_ids?.length>0&&<p>Tickets {result.ticket_ids.map(id=>`#${id}`).join(', ')}</p>}
   {result.removed&&<p>{result.removed.ticket} tickets, {result.removed.incident} incidents, {result.removed.security} security events, {result.removed.network} network events removed.</p>}
  </div>}
  <section className="panel scenario-recommendations"><h2>Simulated Demo</h2>
   {scenarios.filter(item=>!item[3]||canViewSecurity).map(([id,label,description])=><div className="investigation-row" key={id}>
    <div><b>{label}</b><p>{description}</p></div>
    <button disabled={!!busy} className="secondary" onClick={()=>run(id)}>{busy===id?'Running…':label}</button>
   </div>)}
   {canViewSecurity&&<div className="investigation-row">
    <div><b>Reset generated scenario records</b><p>Remove records created by the demo engine and restore the previous monitoring configuration.</p></div>
    <button className="secondary" disabled={!!busy} onClick={()=>{setError('');setConfirm(true)}}>Reset Generated Demo Data</button>
   </div>}
  </section>
  {confirm&&<OperationsDialog title="Reset generated demo data?" onClose={()=>{if(!busy)setConfirm(false)}}>
   <p>Generated scenario tickets, incidents, events, and checks will be removed. Technician-created records and accounts are retained.</p>
   {error&&<ErrorState message={error}/>}
   <button disabled={!!busy} onClick={()=>run('reset')}>{busy?'Resetting…':'Confirm reset'}</button>
  </OperationsDialog>}
 </>;
}
