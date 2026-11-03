import test from 'node:test';
import assert from 'node:assert/strict';
import {priorityTickets,recentActivity,timestamp,isTestEndpoint,priorityName} from './dashboard.js';
test('queue uses backend scores, excludes resolved, and breaks ties oldest first',()=>{
 const items=[{id:1,priority:100,status:'Resolved'},{id:2,priority:80,status:'Open',created_at:'2026-01-02T00:00:00'},{id:3,priority:80,status:'Investigating',created_at:'2026-01-01T00:00:00'},...Array.from({length:5},(_,n)=>({id:n+4,priority:20,status:'Open',created_at:'2026-01-01T00:00:00'}))];
 assert.deepEqual(priorityTickets(items).map(t=>t.id),[3,2,4,5,6]);assert.equal(items[0].id,1);
});
test('activity uses stored milestones, without inventing assignment changes',()=>{
 const events=recentActivity([{id:1,title:'A',created_at:'2026-01-01T00:00:00',assigned_technician:'Sam'}],[{id:2,title:'B',created_at:'2026-01-02T00:00:00',resolved_at:'2026-01-03T00:00:00'},{id:3,created_at:'invalid'}]);
 assert.deepEqual(events.map(e=>e.label),['Incident resolved','Incident created','Ticket created']);assert.equal(events[0].page,'incidents');assert.equal(events[2].id,1);
});
test('API UTC timestamps, demo facility classification and priority thresholds',()=>{
 assert.equal(timestamp('2026-01-01T00:00:00'),Date.parse('2026-01-01T00:00:00Z'));
 assert.equal(isTestEndpoint({building:'Demo Cycle Building'}),true);assert.equal(isTestEndpoint({building:'Atkins Library',mode:'demo'}),false);
 assert.deepEqual([25,26,50,51,75,76].map(priorityName),['Low','Medium','Medium','High','High','Critical']);
});
