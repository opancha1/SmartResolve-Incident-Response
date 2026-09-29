export function Loading({label="Loading SmartResolve data…"}) { return <div className="state loading"><span className="spinner" />{label}</div> }
export function ErrorState({message}) { return <div className="state error"><b>Unable to load this view.</b><span>{message}. Check that the FastAPI server is running on port 8000.</span></div> }
export function Empty({children}) { return <div className="state empty">{children}</div> }
