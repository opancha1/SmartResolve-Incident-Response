export default function ThemeToggle({theme,onToggle}){
 const dark=theme==='dark';
 return <button className="theme-toggle" type="button" onClick={onToggle}
   aria-label={`Switch to ${dark?'light':'dark'} mode`} title={`Switch to ${dark?'light':'dark'} mode`}>
   <span aria-hidden="true">{dark?'☾':'☼'}</span><span>{dark?'Dark':'Light'}</span>
 </button>;
}
