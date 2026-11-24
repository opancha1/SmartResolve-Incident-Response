// The verified backend role authorizes a workspace. The login tab only selects which account is expected.
export function workspaceFor(role) {
 if(role==='user')return 'user';
 if(role==='technician'||role==='admin')return 'operations';
 return null;
}

export function resolvePortalLogin(portal, role) {
 const workspace=workspaceFor(role);
 if(!workspace)return {allowed:false,redirect:'',error:'Access denied: this account has no supported workspace.'};
 if(portal===workspace)return {allowed:true,redirect:workspace==='user'?'/connect':'/dashboard',error:''};
 const actual=role==='user'?'User':role==='technician'?'Technician':'Administrator';
 return {allowed:false,redirect:'',error:`Access denied: this account has the ${actual} role. Select the matching login tab to continue.`};
}

export function workspaceRedirect(pathname, user) {
 const workspace=workspaceFor(user?.role);
 const path=pathname.replace(/\/$/,'')||'/';
 if(workspace==='user')return path==='/connect'?null:'/connect';
 if(workspace!=='operations')return null;
 if(path==='/connect'||path==='/operations'||path==='/')return '/dashboard';
 if(path==='/security'&&!user.can_view_security)return '/dashboard';
 if(path==='/technicians'&&user.role!=='admin')return '/dashboard';
 return null;
}
