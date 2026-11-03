import {useEffect,useRef,useState} from 'react';
import {LayoutDashboard,Ticket,AlertCircle,Network,ShieldCheck,Users,PanelLeftClose,PanelLeftOpen,X,ExternalLink,LogOut,FlaskConical,UserRound} from 'lucide-react';
import {navigationGroups,pageFromPath,paths} from '../services/navigation';
const icons={dashboard:LayoutDashboard,tickets:Ticket,incidents:AlertCircle,network:Network,security:ShieldCheck,technicians:Users};
export default function Sidebar({user,collapsed,onCollapse,open,onOpenChange,onNavigate}){
 const [mobile,setMobile]=useState(()=>window.matchMedia('(max-width: 820px)').matches);
 const sidebarRef=useRef(null),closeRef=useRef(null);
 const activePage=pageFromPath(window.location.pathname);
 useEffect(()=>{const media=window.matchMedia('(max-width: 820px)');const update=()=>{setMobile(media.matches);onOpenChange(false)};media.addEventListener('change',update);return()=>media.removeEventListener('change',update)},[onOpenChange]);
 useEffect(()=>{
  if(!mobile||!open)return;
  const previousFocus=document.activeElement,previousOverflow=document.body.style.overflow;
  document.body.style.overflow='hidden';closeRef.current?.focus();
  const handleKey=e=>{
   if(e.key==='Escape'){e.preventDefault();onOpenChange(false);return}
   if(e.key==='Tab'){
    const focusable=[...sidebarRef.current.querySelectorAll('a[href],button:not([disabled]),summary')].filter(el=>el.getClientRects().length);
    const first=focusable[0],last=focusable.at(-1);
    if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus()}
    else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus()}
   }
  };
  document.addEventListener('keydown',handleKey);
  return()=>{document.body.style.overflow=previousOverflow;document.removeEventListener('keydown',handleKey);if(previousFocus?.isConnected)previousFocus.focus()};
 },[mobile,open,onOpenChange]);
 const navigate=(e,id)=>{if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.button!==0)return;e.preventDefault();onNavigate(id);onOpenChange(false)};
 return <>{mobile&&open&&<button type="button" className="sidebar-backdrop" aria-label="Close navigation" tabIndex={-1} onClick={()=>onOpenChange(false)}/>}
 <aside id="operations-sidebar" className={`operations-sidebar ${collapsed?'is-collapsed':''} ${open?'is-open':''}`} ref={sidebarRef} inert={mobile&&!open} role={mobile&&open?'dialog':undefined} aria-modal={mobile&&open?true:undefined} aria-label="Operations navigation">
  <div className="sidebar-brand-row"><a href="/dashboard" className="sidebar-brand" onClick={e=>navigate(e,'dashboard')} title={collapsed?'SmartResolve — Dashboard':undefined} aria-label="SmartResolve dashboard"><span className="sidebar-logo" aria-hidden="true">◈</span><span className="sidebar-brand-copy"><strong>SmartResolve</strong><small>Unified IT Operations</small></span></a><button type="button" ref={closeRef} className="sidebar-control sidebar-mobile-close" onClick={()=>onOpenChange(false)} aria-label="Close navigation"><X aria-hidden="true"/></button></div>
  <button type="button" className="sidebar-control sidebar-collapse" onClick={onCollapse} aria-expanded={!collapsed} aria-controls="sidebar-navigation" aria-label={collapsed?'Expand sidebar':'Collapse sidebar'} title={collapsed?'Expand sidebar':'Collapse sidebar'}>{collapsed?<PanelLeftOpen aria-hidden="true"/>:<PanelLeftClose aria-hidden="true"/>}<span className="sidebar-collapse-label">Collapse sidebar</span></button>
  <nav id="sidebar-navigation" className="sidebar-navigation" aria-label="Main navigation">{navigationGroups(user).map(group=><div className="sidebar-nav-group" key={group.label}><h2 className="sidebar-section-label">{group.label}</h2><div className="sidebar-nav-items">{group.items.map(([id,label])=>{const Icon=icons[id];return <a key={id} href={paths[id]} className={`sidebar-nav-link ${activePage===id?'is-active':''}`} aria-current={activePage===id?'page':undefined} aria-label={label} title={collapsed?label:undefined} onClick={e=>navigate(e,id)}><Icon aria-hidden="true" size={20} strokeWidth={1.8}/><span className="sidebar-item-label">{label}</span></a>})}</div></div>)}</nav>
  <footer className="sidebar-footer"><a href="/connect" className="sidebar-footer-link" title={collapsed?'Open SmartResolve Connect':undefined} aria-label="Open SmartResolve Connect"><ExternalLink aria-hidden="true"/><span className="sidebar-item-label">SmartResolve Connect</span></a><div className="sidebar-environment" title="Demo environment"><FlaskConical aria-hidden="true"/><span className="sidebar-item-label">Demo environment</span></div><div className="sidebar-account"><span className="sidebar-user-icon" title={user?.full_name}><UserRound aria-hidden="true"/></span><div className="sidebar-account-copy"><b>{user?.full_name||'Operations user'}</b><small>{user?.role==='admin'?'Administrator':'Technician'}</small></div></div><button type="button" className="sidebar-signout" title={collapsed?'Sign out':undefined} onClick={()=>{localStorage.removeItem('sr_token');localStorage.removeItem('sr_user');window.location.assign('/operations')}} aria-label="Sign out"><LogOut aria-hidden="true"/><span className="sidebar-item-label">Sign out</span></button></footer>
 </aside></>;
}
