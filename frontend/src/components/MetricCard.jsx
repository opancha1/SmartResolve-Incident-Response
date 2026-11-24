import {Activity, AlertTriangle, Building2, CheckCircle2, CircleHelp, ClipboardList, ListChecks,
 ShieldAlert, Ticket, Timer, Wifi, WifiOff} from 'lucide-react';

const icons = {
 'monitored endpoints': Building2, 'online': Wifi, 'offline': WifiOff, 'offline endpoints': WifiOff,
 'unknown': CircleHelp, 'open': Ticket, 'open tickets': Ticket, 'total': ClipboardList,
 'active incidents': Activity, 'investigating': Timer, 'resolved': CheckCircle2,
 'pending recommendations': ListChecks, 'security alerts': ShieldAlert, 'recorded events': ShieldAlert,
 'unresolved high priority': AlertTriangle, 'critical issues': AlertTriangle,
};

export default function MetricCard({label,value,tone='blue',hint,onClick}){
 const Icon=icons[label.toLowerCase()]||Activity;
 const content=<><div className="metric-icon"><Icon size={19} aria-hidden="true"/></div>
  <div><span>{label}</span><strong>{value}</strong>{hint&&<small>{hint}</small>}</div></>;
 return onClick?<button type="button" className={`metric ${tone} metric-button`} onClick={onClick}
  aria-label={`${label}, ${value}. Open filtered view.`}>{content}</button>:<div className={`metric ${tone}`}>{content}</div>;
}
