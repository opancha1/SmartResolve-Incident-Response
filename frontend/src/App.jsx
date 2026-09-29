import {useEffect,useState} from 'react';
import Dashboard from './pages/Dashboard';
import Tickets from './pages/Tickets';
import Network from './pages/Network';
import Incidents from './pages/Incidents';
import Security from './pages/Security';
import Technicians from './pages/Technicians';
import ErrorBoundary from './components/ErrorBoundary';

const nav=[['dashboard','▦','Dashboard'],['tickets','▤','Tickets'],['incidents','◉','Incidents'],['network','⌁','Network Monitoring'],['security','◌','Security Monitoring'],['technicians','♙','Technicians']];
const paths={dashboard:'/dashboard',tickets:'/tickets',incidents:'/incidents',network:'/network',security:'/security',technicians:'/technicians'};
const pagesByPath=Object.fromEntries(Object.entries(paths).map(([page,path])=>[path,page]));
function pageFromPath(pathname){return pagesByPath[pathname.replace(/\/$/,'')||'/dashboard']||'dashboard'}

export default function App(){
 const[page,setPage]=useState(()=>pageFromPath(window.location.pathname));
 const[refresh,setRefresh]=useState(0),[drilldown,setDrilldown]=useState(null),[retryKey,setRetryKey]=useState(0);
 useEffect(()=>{
  const handlePopState=()=>{setPage(pageFromPath(window.location.pathname));setDrilldown(null)};
  window.addEventListener('popstate',handlePopState);
  return ()=>window.removeEventListener('popstate',handlePopState);
 },[]);
 const navigate=(target,filter=null)=>{
  const next=paths[target]?target:'dashboard';
  window.history.pushState({page:next},'',paths[next]);
  setPage(next);setDrilldown(filter);setRetryKey(key=>key+1);
 };
 const clearDrilldown=()=>setDrilldown(null);
 const props={refresh,setRefresh};
 const views={
  dashboard:<Dashboard {...props} onDrilldown={navigate}/>,
  tickets:<Tickets {...props} drilldown={page==='tickets'?drilldown:null} clearDrilldown={clearDrilldown}/>,
  network:<Network {...props} drilldown={page==='network'?drilldown:null} clearDrilldown={clearDrilldown}/>,
  incidents:<Incidents {...props} drilldown={page==='incidents'?drilldown:null} clearDrilldown={clearDrilldown}/>,
  security:<Security {...props} drilldown={page==='security'?drilldown:null} clearDrilldown={clearDrilldown}/>,
  technicians:<Technicians {...props}/>,
 };
 return <div className="app"><aside><div className="brand"><span>◈</span><div>SmartResolve<small>Unified IT Incident Response Platform</small></div></div><nav aria-label="Main navigation">{nav.map(([id,icon,label])=><button type="button" className={page===id?'active':''} aria-current={page===id?'page':undefined} onClick={()=>navigate(id)} key={id}><i aria-hidden="true">{icon}</i>{label}</button>)}</nav><div className="side-bottom"><span className="live-dot"/> Demo environment<br/><small>Synthetic data only</small></div></aside><main><div className="topbar"><span>Operations workspace</span><span>Campus IT · <b>System online</b></span></div><ErrorBoundary key={`${page}-${retryKey}`}>{views[page]||views.dashboard}</ErrorBoundary></main></div>;
}
