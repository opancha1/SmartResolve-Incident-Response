import { useEffect, useMemo, useState } from 'react';
import { api } from '../services/api';
import Status from '../components/Status';
import { ErrorState, Loading } from '../components/PageState';

const SPECIALIZATIONS = ['Network', 'Security', 'Hardware', 'Software', 'Classroom Technology'];
const blankForm = { name: '', specialization: '', location: '', availability: 'true' };

export default function Technicians({ refresh, setRefresh }) {
  const [techs, setTechs] = useState(null);
  const [tickets, setTickets] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [locations, setLocations] = useState([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState(blankForm);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState('');
  const [specialization, setSpecialization] = useState('');
  const [location, setLocation] = useState('');
  const [availability, setAvailability] = useState('');

  useEffect(() => {
    let active = true;
    setTechs(null);
    setError('');
    Promise.all([api('/technicians'), api('/tickets'), api('/incidents'), api('/locations')])
      .then(([techData, ticketData, incidentData, locationData]) => {
        if (!active) return;
        setTechs(Array.isArray(techData) ? techData : []);
        setTickets(Array.isArray(ticketData) ? ticketData : []);
        setIncidents(Array.isArray(incidentData) ? incidentData : []);
        setLocations(Array.isArray(locationData) ? locationData : []);
      })
      .catch(e => { if (active) { setError(e.message || 'Unable to load technicians.'); setTechs([]); } });
    return () => { active = false; };
  }, [refresh]);

  const visibleTechs = useMemo(() => (techs || []).filter(t =>
    (!query || t.name.toLowerCase().includes(query.toLowerCase())) &&
    (!specialization || t.specialization === specialization) &&
    (!location || t.location === location) &&
    (!availability || String(Boolean(t.availability)) === availability)
  ), [techs, query, specialization, location, availability]);

  const triggerRefresh = () => setRefresh?.(value => value + 1);
  const openCreate = () => { setForm(blankForm); setModal({ type: 'form' }); };
  const openEdit = technician => {
    setForm({ name: technician.name, specialization: technician.specialization, location: technician.location, availability: String(Boolean(technician.availability)) });
    setModal({ type: 'form', technician });
  };
  const activeAssignments = technician => {
    const activeTickets = tickets.filter(ticket => ticket.assigned_technician === technician.name && ticket.status !== 'Resolved');
    const activeIncidents = incidents.filter(incident => incident.recommended_technician === technician.name && incident.status !== 'Resolved');
    return activeTickets.length + activeIncidents.length;
  };
  const requestDelete = technician => {
    if (activeAssignments(technician)) setModal({ type: 'blocked', technician });
    else setModal({ type: 'confirm', technician });
  };

  async function submitForm(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError('');
    const editing = modal.technician;
    const payload = { ...form, availability: form.availability === 'true' };
    try {
      await api(editing ? `/technicians/${editing.id}` : '/technicians', { method: editing ? 'PUT' : 'POST', body: JSON.stringify(payload) });
      setModal(null);
      setNotice(editing ? 'Technician updated successfully.' : 'Technician created successfully.');
      triggerRefresh();
    } catch (e) {
      setError(`${editing ? 'Unable to update technician. Please try again.' : 'Unable to create technician. Please try again.'} ${e.message || ''}`.trim());
    } finally { setBusy(false); }
  }

  async function deleteTechnician() {
    if (busy) return;
    const technician = modal.technician;
    setBusy(true); setError('');
    try {
      await api(`/technicians/${technician.id}`, { method: 'DELETE' });
      setModal(null); setNotice('Technician deleted successfully.'); triggerRefresh();
    } catch (e) {
      const message = e.message || '';
      if (message.toLowerCase().includes('active assignment') || message.includes('409')) setModal({ type: 'blocked', technician });
      else setError(`Unable to delete technician. Please try again. ${message}`.trim());
    } finally { setBusy(false); }
  }

  if (error && techs === null) return <ErrorState message={error}/>;
  if (!techs) return <Loading/>;

  return <>
    <header className="page-title technician-title"><div><p className="eyebrow">RESPONSE COORDINATION</p><h1>Technicians</h1><p>Manage technician details and see assignments from the backend.</p></div><button className="primary-button" onClick={openCreate}>+ Add Technician</button></header>
    {notice && <div className="success-banner" role="status">{notice}<button aria-label="Dismiss" onClick={() => setNotice('')}>×</button></div>}
    {error && <div className="error-banner" role="alert">{error}<button aria-label="Dismiss" onClick={() => setError('')}>×</button></div>}
    <section className="technician-filters" aria-label="Technician search and filters">
      <input aria-label="Search technicians" placeholder="Search technicians..." value={query} onChange={e => setQuery(e.target.value)}/>
      <select aria-label="Filter by specialization" value={specialization} onChange={e => setSpecialization(e.target.value)}><option value="">All specializations</option>{SPECIALIZATIONS.map(item => <option key={item}>{item}</option>)}</select>
      <select aria-label="Filter by location" value={location} onChange={e => setLocation(e.target.value)}><option value="">All locations</option>{locations.map(item => <option key={item}>{item}</option>)}</select>
      <select aria-label="Filter by availability" value={availability} onChange={e => setAvailability(e.target.value)}><option value="">All availability</option><option value="true">Available</option><option value="false">Unavailable</option></select>
    </section>
    <div className="technician-grid">{visibleTechs.length ? visibleTechs.map(technician => {
      const assigned = tickets.filter(ticket => ticket.assigned_technician === technician.name && ticket.status !== 'Resolved');
      const initials = technician.name.split(/\s+/).map(part => part[0]).join('').slice(0, 2).toUpperCase();
      return <article className="tech-card" key={technician.id}>
        <div className="avatar">{initials}</div><div className="tech-head"><h2>{technician.name}</h2><Status value={technician.availability ? 'Available' : 'Unavailable'}/></div>
        <p>{technician.specialization} specialist · {technician.location}</p>
        <div className="workload"><span>Current workload</span><b>{technician.current_workload ?? 0} active task{technician.current_workload === 1 ? '' : 's'}</b></div>
        <div className="recommend"><b>Assigned tickets:</b>{assigned.length ? assigned.map(ticket => <span key={ticket.id}>#{ticket.id} · {ticket.title} · {ticket.status}</span>) : <small>No active ticket assignments</small>}</div>
        <div className="technician-actions"><button className="secondary-button" onClick={() => openEdit(technician)}>Edit</button><button className="danger-button" onClick={() => requestDelete(technician)}>Delete</button></div>
      </article>;
    }) : <div className="technician-empty"><p>No technicians found.</p><button className="primary-button" onClick={openCreate}>+ Add Technician</button></div>}</div>
    <section className="panel recommendation-panel"><h2>How recommendations work</h2><p>The backend recommendation service weighs specialization, location match, availability, and current workload.</p></section>
    {modal?.type === 'form' && <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget && !busy) setModal(null); }}><section className="manager-modal" role="dialog" aria-modal="true" aria-labelledby="technician-form-title"><h2 id="technician-form-title">{modal.technician ? 'Edit Technician' : 'Add Technician'}</h2><form onSubmit={submitForm}>
      <label>Name<input autoFocus required maxLength="120" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}/></label>
      <label>Specialization<select required value={form.specialization} onChange={e => setForm({ ...form, specialization: e.target.value })}><option value="">Select specialization</option>{SPECIALIZATIONS.map(item => <option key={item}>{item}</option>)}</select></label>
      <label>Location<select required value={form.location} onChange={e => setForm({ ...form, location: e.target.value })}><option value="">Select location</option>{locations.map(item => <option key={item}>{item}</option>)}</select></label>
      <label>Availability<select required value={form.availability} onChange={e => setForm({ ...form, availability: e.target.value })}><option value="true">Available</option><option value="false">Unavailable</option></select></label>
      <div className="modal-actions"><button type="button" className="secondary-button" disabled={busy} onClick={() => setModal(null)}>Cancel</button><button className="primary-button" disabled={busy}>{busy ? 'Saving...' : modal.technician ? 'Save Changes' : 'Create Technician'}</button></div>
    </form></section></div>}
    {(modal?.type === 'confirm' || modal?.type === 'blocked') && <div className="modal-backdrop"><section className="manager-modal confirm-modal" role="dialog" aria-modal="true" aria-labelledby="delete-title"><h2 id="delete-title">{modal.type === 'blocked' ? 'Active assignments' : 'Delete Technician?'}</h2>{modal.type === 'blocked' ? <><p>Cannot delete this technician because they have active assignments.</p><p>Please reassign or unassign their active tickets first.</p><div className="modal-actions"><button className="primary-button" onClick={() => setModal(null)}>Close</button></div></> : <><p>Are you sure you want to delete {modal.technician.name}?</p><div className="modal-actions"><button className="secondary-button" disabled={busy} onClick={() => setModal(null)}>Cancel</button><button className="danger-button" disabled={busy} onClick={deleteTechnician}>{busy ? 'Deleting...' : 'Delete Technician'}</button></div></>}</section></div>}
  </>;
}
