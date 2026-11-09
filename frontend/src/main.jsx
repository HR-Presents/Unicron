import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import Live from './Live.jsx';
import {Icon} from './Icons.jsx';
import './styles.css';
import './theme.css';

function App(){
  const [motion,setMotion]=useState(()=>!window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  return <>
    <header className="topbar">
      <div className="top-inner">
        <a className="brand" href="#command"><img src="/mark.svg" className="unicron-mark" width="50" height="50" alt=""/><span>UNICRON<small>Unified Network for Incident Coordination, Reasoning, Oversight, and Navigation</small></span></a>
        <nav aria-label="Workspace">
          <span className="topbar-context"><i/> INTELLIGENCE WORKSPACE</span>
          <a className="nav-selected" href="#command"><Icon name="grid" size={16}/> Command centre</a>
          <button aria-pressed={motion} onClick={()=>setMotion(!motion)}><Icon name={motion?'pause':'play'} size={16}/> Motion</button>
        </nav>
      </div>
    </header>
    <main id="command"><Live motion={motion}/></main>
  </>;
}

createRoot(document.getElementById('root')).render(<App/>);
