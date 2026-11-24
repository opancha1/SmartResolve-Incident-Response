import {useState} from 'react';
import AuthLoading from '../components/AuthLoading';
import ThemeToggle from '../components/ThemeToggle';

export default function Login({theme,onToggleTheme,initialPortal,onAuthenticate,signingIn}){
 const[portal,setPortal]=useState(initialPortal);
 const[mode,setMode]=useState('login');
 const[form,setForm]=useState({email:'',password:'',full_name:''});
 const[error,setError]=useState('');
 async function auth(event){
  event.preventDefault();
  if(signingIn)return;
  setError('');
  try{await onAuthenticate(portal,mode,form)}
  catch(reason){setError(reason.message)}
 }
 if(signingIn)return <AuthLoading signingIn/>;
 return <div className="connect-shell"><div className={`connect-card login-card ${portal==='operations'?'technician-login':''}`}><div className="login-card-head"><div className="connect-brand">◈ SmartResolve <span>{portal==='operations'?'Operations':'Connect'}</span></div><ThemeToggle theme={theme} onToggle={onToggleTheme}/></div><div className="login-tabs" role="tablist" aria-label="Choose login portal"><button type="button" role="tab" aria-selected={portal==='user'} className={portal==='user'?'selected':''} onClick={()=>{setPortal('user');setMode('login');setError('')}}>User Login</button><button type="button" role="tab" aria-selected={portal==='operations'} className={portal==='operations'?'selected':''} onClick={()=>{setPortal('operations');setMode('login');setError('')}}>Technician Login</button></div><p className="eyebrow">{portal==='operations'?'SMARTRESOLVE OPERATIONS':'SMARTRESOLVE CONNECT'}</p><h1>{portal==='user'?'Sign in to User Portal.':'Sign in to Technician Portal.'}</h1><p>{portal==='user'?'Get support, submit requests, and track your tickets.':'Investigate incidents, manage tickets, and monitor campus IT operations.'}</p><form className="form" onSubmit={auth}>{mode==='register'&&portal==='user'&&<label>Full name<input required minLength="2" value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})}/></label>}<label>Email<input type="email" autoComplete="username" required value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label><label>Password<input type="password" autoComplete={mode==='login'?'current-password':'new-password'} required minLength={mode==='register'?10:1} value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/></label><button>{mode==='register'?'Create user account':portal==='user'?'Sign in to User Portal':'Sign in to Technician Portal'}</button></form>{error&&<p className="error-banner login-error" role="alert">{error}</p>}<p className="switch-auth">{portal==='operations'?<>Technician access is provisioned by an administrator. <a href="/connect">Open Connect</a></>:<>{mode==='login'?"New to SmartResolve?":"Already have an account?"} <button className="link-button" onClick={()=>{setMode(mode==='login'?'register':'login');setError('')}}>{mode==='login'?'Register':'Sign in'}</button></>}</p></div></div>;
}
