import test from 'node:test';
import assert from 'node:assert/strict';
import {paths,pageFromPath,navigationGroups,readSidebarPreference,saveSidebarPreference} from './navigation.js';
test('each existing route and trailing slash resolves to exactly one active destination',()=>{
 for(const [id,path] of Object.entries(paths)){
  assert.equal(pageFromPath(path),id);assert.equal(pageFromPath(`${path}/`),id);
  assert.equal(navigationGroups({role:'admin',can_view_security:true}).flatMap(g=>g.items).filter(([key])=>key===pageFromPath(path)).length,1);
 }
 assert.equal(pageFromPath('/'),'dashboard');assert.equal(pageFromPath('/unknown'),'dashboard');
});
test('sidebar preserves admin and security visibility restrictions',()=>{
 const ids=user=>navigationGroups(user).flatMap(g=>g.items.map(([id])=>id));
 assert.deepEqual(ids({role:'technician',can_view_security:false}),['dashboard','tickets','incidents','network']);
 assert.deepEqual(ids({role:'technician',can_view_security:true}),['dashboard','tickets','incidents','network','security']);
 assert.ok(ids({role:'admin',can_view_security:true}).includes('technicians'));
});
test('collapse preference persists across reads and safely handles unavailable storage',()=>{
 const values=new Map(),storage={getItem:key=>values.get(key),setItem:(key,value)=>values.set(key,value)};
 assert.equal(readSidebarPreference(storage),false);saveSidebarPreference(storage,true);assert.equal(readSidebarPreference(storage),true);
 saveSidebarPreference(storage,false);assert.equal(readSidebarPreference(storage),false);
 const blocked={getItem:()=>{throw Error('blocked')},setItem:()=>{throw Error('blocked')}};
 assert.equal(readSidebarPreference(blocked),false);assert.doesNotThrow(()=>saveSidebarPreference(blocked,true));
});
