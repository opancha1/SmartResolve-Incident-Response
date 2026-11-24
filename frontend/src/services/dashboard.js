export const priorityName=n=>n>75?'Critical':n>50?'High':n>25?'Medium':'Low';
export function timestamp(value){
 if(!value)return NaN;
 return Date.parse(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value)?value:`${value}Z`);
}
export const formatTime=value=>Number.isFinite(timestamp(value))?new Date(timestamp(value)).toLocaleString():'Not checked';
export const priorityTickets=tickets=>tickets.filter(t=>t.status!=='Resolved').sort((a,b)=>b.priority-a.priority||timestamp(a.created_at)-timestamp(b.created_at)||a.id-b.id).slice(0,5);
export const isTestEndpoint=e=>e.is_test??/\b(?:demo|test)\b/i.test(e.building||'');
export function recentActivity(tickets,incidents){
 const events=[];
 for(const [kind,items,page] of [['Ticket',tickets,'tickets'],['Incident',incidents,'incidents']]){
  for(const item of items){
   for(const [field,action] of [['created_at','created'],['resolved_at','resolved']]){
    if(Number.isFinite(timestamp(item[field])))events.push({key:`${kind}-${item.id}-${field}`,page,id:item.id,title:item.title,label:`${kind} ${action}`,at:item[field]});
   }
  }
 }
 return events.sort((a,b)=>timestamp(b.at)-timestamp(a.at)||b.id-a.id).slice(0,6);
}
