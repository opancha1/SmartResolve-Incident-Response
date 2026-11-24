import {useEffect, useRef} from 'react';

export default function OperationsDialog({title, onClose, children, label}) {
 const dialog = useRef(null);
 useEffect(() => {
  const element = dialog.current;
  element.showModal();
  return () => element.close();
 }, []);
 return <dialog className="ticket-modal operations-dialog" ref={dialog} aria-label={title}
   onCancel={event => { event.preventDefault(); onClose(); }}>
  <header className="modal-head"><div>{label && <p className="eyebrow">{label}</p>}<h2>{title}</h2></div>
   <button type="button" className="secondary" onClick={onClose}>Close</button>
  </header>
  {children}
 </dialog>;
}
