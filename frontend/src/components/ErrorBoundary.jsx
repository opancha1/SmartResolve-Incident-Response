import {Component} from 'react';

export default class ErrorBoundary extends Component {
  state={error:null};

  static getDerivedStateFromError(error){return {error};}

  componentDidCatch(error,info){
    if(import.meta.env.DEV) console.error('SmartResolve render failure:',error,info.componentStack);
  }

  retry=()=>this.setState({error:null});

  render(){
    if(!this.state.error)return this.props.children;
    const message=this.state.error instanceof Error?this.state.error.message:String(this.state.error);
    return <div className="crash-screen"><section className="state error crash-card" role="alert"><h1>Something went wrong</h1><p>SmartResolve could not load this view.</p><div className="actions"><button onClick={this.retry}>Retry</button><button className="secondary" onClick={()=>window.location.assign('/dashboard')}>Return to Dashboard</button></div>{import.meta.env.DEV&&<details><summary>Developer details</summary><pre>{message}</pre></details>}</section></div>;
  }
}
