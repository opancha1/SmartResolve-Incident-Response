export default function AuthLoading({signingIn=false}){
 return <div className="connect-shell">
  <div className="connect-card auth-loading" role="status">
   <div className="connect-brand"><span aria-hidden="true">◈</span> SmartResolve</div>
   <p><span className="spinner" aria-hidden="true"/> {signingIn?'Signing you in...':'Loading your workspace...'}</p>
  </div>
 </div>;
}
