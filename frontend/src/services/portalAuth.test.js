import test from 'node:test';
import assert from 'node:assert/strict';
import {resolvePortalLogin,workspaceFor,workspaceRedirect} from './portalAuth.js';

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

test('unverified and unrecognized roles have no workspace',()=>{
  for(const role of [undefined,null,'guest','operations']){
    assert.equal(workspaceFor(role),null);
    assert.equal(resolvePortalLogin('user',role).allowed,false);
    assert.equal(resolvePortalLogin('operations',role).allowed,false);
  }
});

test('verified sessions guard direct links and history destinations',()=>{
  const user={role:'user'};
  const technician={role:'technician',can_view_security:false};
  const admin={role:'admin',can_view_security:true};
  assert.equal(workspaceRedirect('/connect/',user),null);
  assert.equal(workspaceRedirect('/dashboard',user),'/connect');
  assert.equal(workspaceRedirect('/operations',user),'/connect');
  assert.equal(workspaceRedirect('/connect/',technician),'/dashboard');
  assert.equal(workspaceRedirect('/tickets',technician),null);
  assert.equal(workspaceRedirect('/security/',technician),'/dashboard');
  assert.equal(workspaceRedirect('/technicians',technician),'/dashboard');
  assert.equal(workspaceRedirect('/security',admin),null);
  assert.equal(workspaceRedirect('/technicians',admin),null);
});
