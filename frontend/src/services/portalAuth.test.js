import test from 'node:test';
import assert from 'node:assert/strict';
import {resolvePortalLogin} from './portalAuth.js';

test('user and technician login tabs route their verified roles to the matching dashboard',()=>{
  assert.deepEqual(resolvePortalLogin('user','user'),{allowed:true,redirect:'/connect',error:''});
  assert.deepEqual(resolvePortalLogin('operations','technician'),{allowed:true,redirect:'/dashboard',error:''});
  assert.deepEqual(resolvePortalLogin('operations','admin'),{allowed:true,redirect:'/dashboard',error:''});
});

test('portal role mismatches are denied and do not produce a redirect',()=>{
  const userOnTechnicianTab=resolvePortalLogin('operations','user');
  assert.equal(userOnTechnicianTab.allowed,false);
  assert.equal(userOnTechnicianTab.redirect,'');
  assert.match(userOnTechnicianTab.error,/Access denied/);
  const technicianOnUserTab=resolvePortalLogin('user','technician');
  assert.equal(technicianOnUserTab.allowed,false);
  assert.equal(technicianOnUserTab.redirect,'');
});
