import {useState} from 'react';
import {statuses, formatTime} from '../services/operations';

export function Timeline({entries}) {
 return <section className="investigation-section">
  <h3>Investigation timeline</h3>
  {entries.length ? <ol className="investigation-timeline">{entries.map(entry=><li key={entry.id}>
   <b>{entry.kind}</b> <time>{formatTime(entry.created_at)}</time><p>{entry.body}</p>
  </li>)}</ol> : <p>No investigation updates yet.</p>}
 </section>;
}

export default function InvestigationForm({record, technicians, includeCause, busy, onSave}) {
 const [status, setStatus] = useState(record.status);
 const [technician, setTechnician] = useState('');
 const [note, setNote] = useState('');
 const [resolution, setResolution] = useState('');
 const [cause, setCause] = useState('');

 async function submit(event) {
  event.preventDefault();
  const saved = await onSave({
   status, technician_id: technician ? Number(technician) : undefined,
   note: note.trim() || undefined, resolution: resolution.trim() || undefined,
   confirmed_cause: cause.trim() || undefined,
  });
  if (saved) {
   setTechnician('');
   setNote('');
   setResolution('');
   setCause('');
  }
 }

 return <form className="form investigation-section" onSubmit={submit}>
  <h3>Update investigation</h3>
  <div className="investigation-fields">
   <label>Status<select value={status} onChange={event=>setStatus(event.target.value)}>
    {statuses.map(item=><option key={item}>{item}</option>)}
   </select></label>
   <label>Assign technician<select value={technician} onChange={event=>setTechnician(event.target.value)}>
    <option value="">{record.assigned_technician || 'Unassigned'}</option>
    {technicians.filter(item=>item.availability&&item.name!==record.assigned_technician).map(item=>
     <option key={item.id} value={item.id}>{item.name} · {item.specialization} · {item.current_workload} open</option>)}
   </select></label>
  </div>
  <label>Investigation note<textarea value={note} maxLength={4000} onChange={event=>setNote(event.target.value)}/></label>
  {includeCause&&<label>Confirmed root cause<input value={cause} maxLength={4000} onChange={event=>setCause(event.target.value)}/></label>}
  <label>Resolution notes<textarea value={resolution} maxLength={4000} onChange={event=>setResolution(event.target.value)}/></label>
  <button disabled={busy}>Save investigation</button>
 </form>;
}
