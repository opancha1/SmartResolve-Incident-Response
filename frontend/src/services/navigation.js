export const paths={dashboard:'/dashboard',tickets:'/tickets',incidents:'/incidents',network:'/network',security:'/security',technicians:'/technicians',demo:'/demo'};
export function pageFromPath(pathname){const path=pathname.replace(/\/$/,'')||'/dashboard';return Object.keys(paths).find(key=>paths[key]===path)||'dashboard'}
export function navigationGroups(user,demoEnabled=false){
 return [
  {label:'Workspace',items:[['dashboard','Dashboard'],['tickets','Tickets'],['incidents','Incidents'],...(user?.role==='admin'?[['technicians','Technicians']]:[])]},
  {label:'Monitoring',items:[['network','Network Monitoring'],...(user?.can_view_security?[['security','Security Monitoring']]:[])]},
  ...(demoEnabled&&['technician','admin'].includes(user?.role)?[{label:'Demonstration',items:[['demo','Demo Control Center']]}]:[]),
 ];
}
export function readSidebarPreference(storage){try{return storage.getItem('sr_sidebar_collapsed')==='true'}catch{return false}}
export function saveSidebarPreference(storage,collapsed){try{storage.setItem('sr_sidebar_collapsed',String(collapsed))}catch{/* Navigation remains usable when storage is unavailable. */}}
