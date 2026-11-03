import {useEffect,useState} from 'react';
import Dashboard from './pages/Dashboard';
import Tickets from './pages/Tickets';
import Network from './pages/Network';
import Incidents from './pages/Incidents';
import Security from './pages/Security';
import Technicians from './pages/Technicians';
import ErrorBoundary from './components/ErrorBoundary';
import Connect from './pages/Connect';
import {api} from './services/api';
import ThemeToggle from './components/ThemeToggle';
import {getInitialTheme} from './services/theme';
import Sidebar from './components/Sidebar';
import {Menu} from 'lucide-react';
import {paths,pageFromPath,readSidebarPreference,saveSidebarPreference} from './services/navigation';

export default function App(){
 const[page,setPage]=useState(()=>pageFromPath(window.location.pathname));
 const[refresh,setRefresh]=useState(0),[drilldown,setDrilldown]=useState(null),[retryKey,setRetryKey]=useState(0);
 const[operationAuth,setOperationAuth]=useState('checking');
 const[operationUser,setOperationUser]=useState(null);
 const[theme,setTheme]=useState(getInitialTheme);
 const[sidebarCollapsed,setSidebarCollapsed]=useState(()=>readSidebarPreference(window.localStorage));
 const[sidebarOpen,setSidebarOpen]=useState(false);
 const toggleSidebar=()=>setSidebarCollapsed(current=>{const next=!current;saveSidebarPreference(window.localStorage,next);return next});
 const portalPath=window.location.pathname==='/connect'||window.location.pathname==='/connect/';
 const loginPath=window.location.pathname==='/operations'||window.location.pathname==='/operations/';
 useEffect(()=>{
  if(portalPath||loginPath)return;
  const token=localStorage.getItem('sr_token');
  if(!token){setOperationAuth('denied');return}
  let active=true;api('/auth/me').then(user=>{if(!active)return;if(user.role==='user'){window.location.replace('/connect');return}if(['technician','admin'].includes(user.role)){setOperationUser(user);if((window.location.pathname==='/security'&&!user.can_view_security)||(window.location.pathname==='/technicians'&&user.role!=='admin')){window.history.replaceState({},'', '/dashboard');setPage('dashboard');setDrilldown(null)}setOperationAuth('allowed')}else setOperationAuth('denied')}).catch(()=>{localStorage.removeItem('sr_token');localStorage.removeItem('sr_user');if(active)setOperationAuth('denied')});
  return()=>{active=false};
 },[portalPath,loginPath]);
 useEffect(()=>{
  if(operationAuth!=='allowed')return;
  const timer=setInterval(()=>setRefresh(value=>value+1),20000);
  return()=>clearInterval(timer);
 },[operationAuth]);
 useEffect(()=>{
  const handlePopState=()=>{setPage(pageFromPath(window.location.pathname));setDrilldown(null)};
  window.addEventListener('popstate',handlePopState);
  return ()=>window.removeEventListener('popstate',handlePopState);
 },[]);
 const navigate=(target,filter=null)=>{
  if(target==='technicians'&&operationUser?.role!=='admin'){target='dashboard';filter=null}
  if(target==='security'&&!operationUser?.can_view_security){target='dashboard';filter=null}
  const next=paths[target]?target:'dashboard';
  window.history.pushState({page:next},'',paths[next]);
  setPage(next);setDrilldown(filter);setRetryKey(key=>key+1);
 };
 const clearDrilldown=()=>setDrilldown(null);
 useEffect(()=>{document.documentElement.dataset.theme=theme;document.querySelector('meta[name="theme-color"]')?.setAttribute('content',theme==='dark'?'#0d1725':'#f5f7fa')},[theme]);
 const toggleTheme=()=>setTheme(current=>{const next=current==='dark'?'light':'dark';window.localStorage.setItem('sr_theme',next);return next});
 const props={refresh,setRefresh,canViewSecurity:!!operationUser?.can_view_security,canConfigureMonitoring:operationUser?.role==='admin',theme,onToggleTheme:toggleTheme};
 const views={
  dashboard:<Dashboard {...props} onDrilldown={navigate}/>,
  tickets:<Tickets {...props} drilldown={page==='tickets'?drilldown:null} clearDrilldown={clearDrilldown}/>,
  network:<Network {...props} drilldown={page==='network'?drilldown:null} clearDrilldown={clearDrilldown}/>,
  incidents:<Incidents {...props} drilldown={page==='incidents'?drilldown:null} clearDrilldown={clearDrilldown}/>,
  security:<Security {...props} drilldown={page==='security'?drilldown:null} clearDrilldown={clearDrilldown}/>,
  technicians:<Technicians {...props}/>,
 };
 if(portalPath)return <Connect theme={theme} onToggleTheme={toggleTheme}/>;
 if(loginPath||operationAuth==='denied')return <Connect theme={theme} onToggleTheme={toggleTheme}/>;
 if(operationAuth!=='allowed')return <div className="connect-shell"><div className="state"><span className="spinner"/> Verifying Operations access…</div></div>;
 return <div className={`app operations-shell ${sidebarCollapsed?'sidebar-collapsed':''}`}><Sidebar user={operationUser} collapsed={sidebarCollapsed} onCollapse={toggleSidebar} open={sidebarOpen} onOpenChange={setSidebarOpen} onNavigate={navigate}/><main inert={sidebarOpen}><div className="topbar"><div className="workspace-heading"><button type="button" className="sidebar-menu-toggle" aria-label="Open navigation" aria-expanded={sidebarOpen} aria-controls="operations-sidebar" onClick={()=>setSidebarOpen(true)}><Menu aria-hidden="true" size={20}/></button><span>Operations workspace</span></div><div className="topbar-actions"><span>Campus IT workspace</span><ThemeToggle theme={theme} onToggle={toggleTheme}/></div></div><ErrorBoundary key={`${page}-${retryKey}`}>{views[page]||views.dashboard}</ErrorBoundary></main></div>;
}
