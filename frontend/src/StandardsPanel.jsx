import React,{useEffect,useMemo,useState} from 'react';
import {api,forCase} from './live-api.mjs';
import {Icon} from './Icons.jsx';

const fields=form=>Object.fromEntries(new FormData(form).entries());

export default function StandardsPanel({id,connected,reviewAvailable}){
  const [frameworks,setFrameworks]=useState([]);
  const [requirements,setRequirements]=useState([]);
  const [mappings,setMappings]=useState([]);
  const [loading,setLoading]=useState(true);
  const [saving,setSaving]=useState(false);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const [revision,setRevision]=useState(0);

  useEffect(()=>{
    const controller=new AbortController();
    setLoading(true);
    setError('');
    if(!connected){
      setFrameworks([]);
      setRequirements([]);
      setMappings([]);
      setLoading(false);
      return ()=>controller.abort();
    }
    Promise.all([
      api('/standards/frameworks',{signal:controller.signal}),
      api('/standards/requirements',{signal:controller.signal}),
      api(forCase(id)+'/standards/mappings',{signal:controller.signal}),
    ]).then(([f,r,m])=>{
      if(controller.signal.aborted)return;
      setFrameworks(f);
      setRequirements(r);
      setMappings(m);
    }).catch(failure=>{
      if(!controller.signal.aborted)setError(failure.message);
    }).finally(()=>{
      if(!controller.signal.aborted)setLoading(false);
    });
    return ()=>controller.abort();
  },[id,connected,revision]);

  const frameworkById=useMemo(
    ()=>new Map(frameworks.map(item=>[item.identifier,item])),
    [frameworks]
  );
  const requirementById=useMemo(
    ()=>new Map(requirements.map(item=>[item.id,item])),
    [requirements]
  );
  const counts=useMemo(()=>({
    pending:mappings.filter(item=>item.review_status==='pending').length,
    verified:mappings.filter(item=>item.review_status==='verified').length,
    rejected:mappings.filter(item=>item.review_status==='rejected').length,
  }),[mappings]);

  async function submit(event,path,transform=fields){
    event.preventDefault();
    if(saving || !connected || !reviewAvailable)return;
    const form=event.currentTarget;
    const body=transform(form);
    setSaving(true);
    setError('');
    setNotice('');
    try{
      await api(path,{method:'POST',body});
      form.reset();
      setNotice('Record saved. The evidence and review registers have been refreshed.');
      setRevision(value=>value+1);
    }catch(failure){
      setError(failure.message);
    }finally{
      setSaving(false);
    }
  }

  const canEdit=connected && reviewAvailable && !saving;
  const mappingPath=forCase(id)+'/standards/mappings';

  return <div className="detail-body standards-workspace">
    <div className="detail-heading">
      <div>
        <div className="eyebrow small">GOVERNANCE TRACEABILITY</div>
        <h2>Standards & Governance</h2>
      </div>
      <button className="button secondary" type="button"
        disabled={loading || saving || !connected}
        onClick={()=>setRevision(value=>value+1)}>
        <Icon name="history" size={15}/> Refresh
      </button>
    </div>

    <p className="detail-copy">
      Map reviewer-attested evidence to registered standards requirements.
      These records support human assessment; they do not establish
      regulatory compliance or certification.
    </p>

    <div className="standards-metrics" aria-label="Standards mapping summary">
      <div><strong>{frameworks.length}</strong><span>Frameworks</span></div>
      <div><strong>{requirements.length}</strong><span>Requirements</span></div>
      <div><strong>{counts.pending}</strong><span>Pending review</span></div>
      <div><strong>{counts.verified}</strong><span>Reviewed mappings</span></div>
    </div>

    {loading && <p className="detail-copy" role="status">Loading governance records…</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p className="verify-status" role="status">{notice}</p>}
    {!reviewAvailable && <p className="detail-copy">Read-only access. Reviewer authorization is required to register or review mappings.</p>}

    <div className="standards-columns">
      <section className="record">
        <div className="eyebrow small">01 / REGISTRY</div>
        <h3>Frameworks</h3>
        {!frameworks.length && <p>No frameworks registered.</p>}
        {frameworks.map(item=><div className="standards-entry" key={item.identifier}>
          <strong>{item.identifier}</strong>
          <p>{item.title} · {item.edition}</p>
          <small>{item.publisher} · {item.normative_status}</small>
          {/^https:\/\//.test(item.official_url) &&
            <a href={item.official_url} target="_blank" rel="noreferrer">Publisher reference</a>}
        </div>)}
        {reviewAvailable && <details className="source-controls">
          <summary>Register framework</summary>
          <form className="workbench-form" onSubmit={event=>submit(event,'/standards/frameworks')}>
            <label>Identifier<input name="identifier" minLength={2} maxLength={100} required/></label>
            <label>Title<input name="title" minLength={3} maxLength={250} required/></label>
            <label>Publisher<input name="publisher" minLength={2} maxLength={180} required/></label>
            <label>Edition<input name="edition" maxLength={100} required/></label>
            <label>Official URL<input name="official_url" type="url" pattern="https://.*" required/></label>
            <label>Normative classification
              <select name="normative_status">
                <option value="unknown">Unknown</option>
                <option value="guidance">Guidance</option>
                <option value="voluntary">Voluntary</option>
                <option value="regulatory">Regulatory (requires legal validation)</option>
              </select>
            </label>
            <button className="button primary" disabled={!canEdit}>Register framework</button>
          </form>
        </details>}
      </section>

      <section className="record">
        <div className="eyebrow small">02 / REQUIREMENTS</div>
        <h3>Requirement catalogue</h3>
        {!requirements.length && <p>No requirements registered.</p>}
        {requirements.map(item=><div className="standards-entry" key={item.id}>
          <strong>{item.framework_id} / {item.requirement_code}</strong>
          <p>{item.description}</p>
        </div>)}
        {reviewAvailable && <details className="source-controls">
          <summary>Add requirement</summary>
          <form className="workbench-form" onSubmit={event=>submit(event,'/standards/requirements')}>
            <label>Framework
              <select name="framework_id" required>
                <option value="">Choose framework</option>
                {frameworks.map(item=><option key={item.identifier} value={item.identifier}>{item.identifier}</option>)}
              </select>
            </label>
            <label>Requirement code<input name="requirement_code" maxLength={100} required/></label>
            <label>Description<textarea name="description" minLength={5} maxLength={2000} required/></label>
            <button className="button primary" disabled={!canEdit || !frameworks.length}>Add requirement</button>
          </form>
        </details>}
      </section>
    </div>

    <section className="record">
      <div className="eyebrow small">03 / CASE TRACEABILITY</div>
      <h3>Evidence mappings</h3>
      <p className="detail-copy">
        Each mapping connects a requirement to a specific passage in this case.
        A verified mapping means the association was reviewed, not that the
        requirement has been satisfied.
      </p>

      {!mappings.length && <p>No evidence mappings recorded for this case.</p>}

      {mappings.map(item=>{
        const requirement=requirementById.get(item.requirement_id);
        const framework=frameworkById.get(item.framework_id);
        return <article className="standards-entry" key={item.id}>
          <div className="standards-entry-head">
            <strong>{item.framework_id} / {item.requirement_code}</strong>
            <span className="ref static">{item.review_status}</span>
          </div>
          <p>{requirement?.description??'Requirement details unavailable'}</p>
          <p>{item.assessment.replaceAll('_',' ')} · {item.rationale}</p>
          <small>Passage reference: <code>{item.passage_id}</code></small>
          {framework && <small>Framework edition: {framework.edition}</small>}
          {item.reviewed_by && <p>Reviewed by {item.reviewed_by}: {item.review_rationale}</p>}

          {reviewAvailable && item.review_status==='pending' &&
            <details className="source-controls">
              <summary>Review mapping</summary>
              <form className="workbench-form"
                onSubmit={event=>submit(
                  event,
                  mappingPath+'/'+encodeURIComponent(item.id)+'/review',
                  form=>({
                    ...fields(form),
                    decision:event.nativeEvent.submitter?.value,
                  })
                )}>
                <label>Reviewer<input name="reviewer" minLength={2} maxLength={180} required/></label>
                <label>Review rationale<textarea name="rationale" minLength={20} maxLength={4000} required/></label>
                <div className="review-actions">
                  <button className="button secondary" type="submit" name="decision" value="rejected" disabled={!canEdit}>Reject</button>
                  <button className="button primary" type="submit" name="decision" value="verified" disabled={!canEdit}>Verify mapping</button>
                </div>
              </form>
            </details>}
        </article>;
      })}

      {reviewAvailable && <details className="source-controls">
        <summary>Create evidence mapping</summary>
        <form className="workbench-form" onSubmit={event=>submit(event,mappingPath)}>
          <label>Requirement
            <select name="requirement_id" required>
              <option value="">Choose requirement</option>
              {requirements.map(item=><option key={item.id} value={item.id}>{item.framework_id} / {item.requirement_code}</option>)}
            </select>
          </label>
          <label>Verified evidence passage ID
            <input name="passage_id" required placeholder="Passage identifier from evidence search"/>
          </label>
          <label>Assessment
            <select name="assessment">
              <option value="needs_review">Needs review</option>
              <option value="potential_alignment">Potential alignment</option>
              <option value="potential_gap">Potential gap</option>
            </select>
          </label>
          <label>Rationale<textarea name="rationale" minLength={20} maxLength={4000} required/></label>
          <button className="button primary" disabled={!canEdit || !requirements.length}>Create pending mapping</button>
        </form>
      </details>}
    </section>

    <p className="detail-copy">
      Compliance status: <strong>Not determined.</strong> All legal interpretations,
      jurisdictional applicability and certification decisions require qualified
      human assessment.
    </p>
  </div>;
}
