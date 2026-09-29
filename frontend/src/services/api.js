// Keep the API host aligned with the confirmed local FastAPI endpoint.
const BASE="http://127.0.0.1:8000/api";
export async function api(path, options={}) {
 let response;
 try{response=await fetch(`${BASE}${path}`,{headers:{"Content-Type":"application/json"},...options})}
 catch(error){throw new Error(`Unable to reach the SmartResolve API at ${BASE}. ${error?.message||'Check that FastAPI is running.'}`)}
 if(response.status===204)return null;
 let payload;
 try{payload=await response.json()}
 catch{throw new Error(response.ok?`The API returned invalid JSON for ${path}.`:`Request failed (${response.status}) for ${path}.`)}
 if(!response.ok){let detail=payload?.detail;if(Array.isArray(detail))detail=detail.map(item=>item?.msg||String(item)).join('; ');else if(detail&&typeof detail!=='string')detail=JSON.stringify(detail);throw new Error(detail||`Request failed (${response.status}) for ${path}.`)}
 return payload;
}
