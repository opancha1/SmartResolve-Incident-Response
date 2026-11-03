// The backend's verified role is the authority; the selected tab only defines the expected portal.
export function resolvePortalLogin(portal, role) {
  const allowed = portal === 'user' ? role === 'user' : ['technician', 'admin'].includes(role);
  if (allowed) return { allowed: true, redirect: portal === 'user' ? '/connect' : '/dashboard', error: '' };
  const actual = role === 'user' ? 'User' : role === 'technician' ? 'Technician' : 'Administrator';
  return { allowed: false, redirect: '', error: `Access denied: this account has the ${actual} role. Select the matching login tab to continue.` };
}
