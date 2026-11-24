import {useCallback,useEffect,useRef,useState} from 'react';
import Dashboard from './pages/Dashboard';
import Demo from './pages/Demo';
import Tickets from './pages/Tickets';
import Network from './pages/Network';
import Incidents from './pages/Incidents';
import Security from './pages/Security';
import Technicians from './pages/Technicians';
import ErrorBoundary from './components/ErrorBoundary';
import Connect from './pages/Connect';
import Login from './pages/Login';
import AuthLoading from './components/AuthLoading';
import {resolvePortalLogin,workspaceFor,workspaceRedirect} from './services/portalAuth';
import {api} from './services/api';
import ThemeToggle from './components/ThemeToggle';
import {getInitialTheme} from './services/theme';
import Sidebar from './components/Sidebar';
import {Menu} from 'lucide-react';
import {paths,pageFromPath,readSidebarPreference,saveSidebarPreference} from './services/navigation';

export default function App(){
 const[pathname,setPathname]=useState(()=>window.location.pathname);
 const page=pageFromPath(pathname);
 const[refresh,setRefresh]=useState(0),[drilldown,setDrilldown]=useState(null),[retryKey,setRetryKey]=useState(0);
 const[session,setSession]=useState(()=>({status:localStorage.getItem('sr_token')?'checking':'signed-out'}));
 const authRevision=useRef(0);
 const workspace=workspaceFor(session.user?.role);
 const operationUser=workspace==='operations'?session.user:null;
 const[demoEnabled,setDemoEnabled]=useState(false);
 const[theme,setTheme]=useState(getInitialTheme);
 const[sidebarCollapsed,setSidebarCollapsed]=useState(()=>readSidebarPreference(window.localStorage));
 const[sidebarOpen,setSidebarOpen]=useState(false);
 const toggleSidebar=()=>setSidebarCollapsed(current=>{const next=!current;saveSidebarPreference(window.localStorage,next);return next});
 const replaceRoute=useCallback(path=>{
  window.history.replaceState({},'',path);
  setPathname(path);
  setDrilldown(null);
 },[]);
 const restoreSession=useCallback(async()=>{
  const revision=++authRevision.current;
  const token=localStorage.getItem('sr_token');
  localStorage.removeItem('sr_user');
  if(!token){setSession({status:'signed-out'});return}
  setSession({status:'checking'});
  try{
   const user=await api('/auth/me');
   if(revision!==authRevision.current)return;
   if(!workspaceFor(user?.role))throw new Error('This account has no supported workspace.');
   setSession({status:'verified',user});
  }catch{
   if(revision!==authRevision.current)return;
   localStorage.removeItem('sr_token');
   setSession({status:'signed-out'});
  }
 },[]);
 useEffect(()=>{
  restoreSession();
  const storage=event=>{if(event.key==='sr_token'||event.key===null)restoreSession()};
  const pageShow=event=>{if(event.persisted)restoreSession()};
  window.addEventListener('storage',storage);
  window.addEventListener('pageshow',pageShow);
  return()=>{
   authRevision.current++;
   window.removeEventListener('storage',storage);
   window.removeEventListener('pageshow',pageShow);
  };
 },[restoreSession]);
 const redirect=session.status==='verified'?workspaceRedirect(pathname,session.user):null;
 useEffect(()=>{if(redirect)replaceRoute(redirect)},[redirect,replaceRoute]);

 async function authenticate(portal,mode,form){
  const revision=++authRevision.current;
  setSession({status:'signing-in'});
  try{
   const result=await api(`/auth/${mode}`,{method:'POST',body:JSON.stringify(form)});
   if(revision!==authRevision.current)return;
   if(!result.access_token)throw new Error('The server did not return a session.');
   const user=await api('/auth/me',{headers:{Authorization:`Bearer ${result.access_token}`}});
   if(revision!==authRevision.current)return;
   const decision=resolvePortalLogin(portal,user?.role);
   if(!decision.allowed)throw new Error(decision.error);
   localStorage.setItem('sr_token',result.access_token);
   replaceRoute(decision.redirect);
   setSession({status:'verified',user});
  }catch(error){
   if(revision!==authRevision.current)return;
   setSession({status:'signed-out'});
   throw error;
  }
 }

 function signOut(){
  authRevision.current++;
  localStorage.removeItem('sr_token');
  localStorage.removeItem('sr_user');
  setSidebarOpen(false);
  replaceRoute(workspace==='operations'?'/operations':'/connect');
  setSession({status:'signed-out'});
 }

 useEffect(()=>{
  setDemoEnabled(false);
  if(!operationUser)return;
  let active=true;
  api('/demo').then(result=>{if(active)setDemoEnabled(!!result.enabled)}).catch(()=>{if(active)setDemoEnabled(false)});
  return()=>{active=false};
 },[operationUser]);
 useEffect(()=>{
  if(!operationUser||redirect)return;
  const timer=setInterval(()=>setRefresh(value=>value+1),20000);
  return()=>clearInterval(timer);
 },[operationUser,redirect]);
 useEffect(()=>{
  const handlePopState=()=>{setPathname(window.location.pathname);setDrilldown(null)};
  window.addEventListener('popstate',handlePopState);
  return ()=>window.removeEventListener('popstate',handlePopState);
 },[]);
 const navigate=(target,filter=null)=>{
  const destination=paths[target]||paths.dashboard;
  const restricted=workspaceRedirect(destination,operationUser);
  const next=restricted||destination;
  if(window.location.pathname!==next)window.history.pushState({},'',next);
  setPathname(next);
  setDrilldown(restricted?null:filter);
  setRetryKey(key=>key+1);
 };
 const clearDrilldown=()=>setDrilldown(null);
 useEffect(()=>{document.documentElement.dataset.theme=theme;document.querySelector('meta[name="theme-color"]')?.setAttribute('content',theme==='dark'?'#0d1725':'#f5f7fa')},[theme]);
 const toggleTheme=()=>setTheme(current=>{const next=current==='dark'?'light':'dark';window.localStorage.setItem('sr_theme',next);return next});
 const props={refresh,setRefresh,onDrilldown:navigate,demoEnabled,canViewSecurity:!!operationUser?.can_view_security,canConfigureMonitoring:operationUser?.role==='admin',theme,onToggleTheme:toggleTheme};
 const views={
  demo:demoEnabled?<Demo {...props}/>:<p role="status">Demo Control Center is unavailable.</p>,
  dashboard:<Dashboard {...props} onDrilldown={navigate}/>,
  tickets:<Tickets {...props} drilldown={page==='tickets'?drilldown:null} clearDrilldown={clearDrilldown}/>,
  network:<Network {...props} drilldown={page==='network'?drilldown:null} clearDrilldown={clearDrilldown}/>,
  incidents:<Incidents {...props} drilldown={page==='incidents'?drilldown:null} clearDrilldown={clearDrilldown}/>,
  security:<Security {...props} drilldown={page==='security'?drilldown:null} clearDrilldown={clearDrilldown}/>,
  technicians:<Technicians {...props}/>,
 };
 if(session.status==='checking'||redirect)return <AuthLoading/>;
 if(session.status==='signed-out'||session.status==='signing-in'){
  const initialPortal=['/','/connect','/connect/'].includes(pathname)?'user':'operations';
  return <Login key={pathname} initialPortal={initialPortal} theme={theme} onToggleTheme={toggleTheme}
   signingIn={session.status==='signing-in'} onAuthenticate={authenticate}/>;
 }
 if(workspace==='user')return <Connect key={session.user.id} user={session.user} theme={theme} onToggleTheme={toggleTheme} onSignOut={signOut}/>;
 if(workspace!=='operations')return <AuthLoading/>;
 return <div className={`app operations-shell ${sidebarCollapsed?'sidebar-collapsed':''}`}><Sidebar user={operationUser} activePage={page} demoEnabled={demoEnabled} collapsed={sidebarCollapsed} onCollapse={toggleSidebar} open={sidebarOpen} onOpenChange={setSidebarOpen} onNavigate={navigate} onSignOut={signOut}/><main inert={sidebarOpen}><div className="topbar"><div className="workspace-heading"><button type="button" className="sidebar-menu-toggle" aria-label="Open navigation" aria-expanded={sidebarOpen} aria-controls="operations-sidebar" onClick={()=>setSidebarOpen(true)}><Menu aria-hidden="true" size={20}/></button><span>Operations workspace</span></div><div className="topbar-actions"><span>Campus IT workspace</span><ThemeToggle theme={theme} onToggle={toggleTheme}/></div></div><ErrorBoundary key={`${page}-${retryKey}`}>{views[page]||views.dashboard}</ErrorBoundary></main></div>;
}
