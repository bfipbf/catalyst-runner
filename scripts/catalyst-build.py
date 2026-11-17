#!/usr/bin/env python3
"""Read-only Salesforce DX dependency indexer. Usage: python catalyst-build.py /path/to/checked-out/repo --ref Branch_Gabungan"""
import argparse, collections, datetime, hashlib, json, pathlib, re, subprocess, xml.etree.ElementTree as ET

ROOT='force-app/main/default/'
def git(repo,*args):
    p=subprocess.run(['git','-C',str(repo),*args],capture_output=True,text=True,check=True)
    return p.stdout.strip()
def tag(e): return e.tag.rsplit('}',1)[-1]
def child(e,name): return next((x for x in e if tag(x)==name),None)
def val(e,name):
    x=child(e,name)
    return x.text.strip() if x is not None and x.text else None
def values(e,name):return [x.text.strip() for x in e.iter() if tag(x)==name and x.text and x.text.strip()]
def collect_refs(root):
    d=collections.defaultdict(set)
    for e in root.iter():
        t=tag(e)
        if t in ('object','objectType','objectName','sObject','sObjectType','recordType','targetObject') and e.text:
            d['objects'].add(e.text.strip())
        elif t in ('field','fieldName','fieldReference','sortField','assignToReference') and e.text:
            d['fields'].add(e.text.strip())
        elif t in ('flowName','subflowName') and e.text:
            d['flows'].add(e.text.strip())
        elif t in ('actionName','apexClass','className') and e.text:
            d['actions'].add(e.text.strip())
    return {k:sorted(v) for k,v in d.items()}
def parse_flow(root):
    element_kinds={'actionCalls','apexPluginCalls','assignments','collectionProcessors','customErrors','decisions','loops','recordCreates','recordDeletes','recordLookups','recordUpdates','screens','subflows','transforms','waits','steps','orchestratedStages','orchestratedSteps'}
    nodes=[]; edges=[]
    def connections(e,src):
        for x in e.iter():
            if tag(x) in ('connector','defaultConnector','nextValueConnector','noMoreValuesConnector','faultConnector','scheduledPaths'):
                target=val(x,'targetReference')
                if target: edges.append({'from':src,'to':target,'via':tag(x)})
    start=child(root,'start')
    if start is not None:
        nodes.append({'name':'$start','type':'start','object':val(start,'object'),'triggerType':val(start,'triggerType'),'recordTriggerType':val(start,'recordTriggerType'),'filters':[{'field':val(x,'field'),'operator':val(x,'operator'),'value':values(x,'stringValue') or values(x,'elementReference')} for x in start if tag(x)=='filters']})
        connections(start,'$start')
    for e in root:
        if tag(e) not in element_kinds:continue
        nm=val(e,'name')
        if not nm:continue
        node={'name':nm,'label':val(e,'label'),'type':tag(e)}
        for k in ('object','actionName','actionType','flowName','collectionReference','iterationOrder','inputReference','outputReference','storeOutputAutomatically'):
            v=val(e,k)
            if v is not None:node[k]=v
        if tag(e)=='decisions':
            node['rules']=[{'name':val(r,'name'),'conditions':[{'left':val(c,'leftValueReference'),'operator':val(c,'operator'),'right':values(c,'elementReference') or values(c,'stringValue')} for c in r if tag(c)=='conditions'],'logic':val(r,'conditionLogic')} for r in e if tag(r)=='rules']
        if tag(e)=='assignments':
            node['items']=[{'reference':val(i,'assignToReference'),'operator':val(i,'operator'),'value':values(i,'elementReference') or values(i,'stringValue')} for i in e if tag(i)=='assignmentItems']
        if tag(e)=='loops':
            node['collection']=val(e,'collectionReference');node['iterator']=val(e,'nextValueConnector')
        nodes.append(node);connections(e,nm)
    outgoing={x['from'] for x in edges}
    targets={x['name'] for x in nodes}
    return {'status':val(root,'status'),'processType':val(root,'processType'),'apiVersion':val(root,'apiVersion'),'nodes':nodes,'edges':edges,'unresolved_connectors':sorted(set(x['to'] for x in edges)-targets),'refs':collect_refs(root)}
def main():
    a=argparse.ArgumentParser();a.add_argument('repo',type=pathlib.Path);a.add_argument('--ref',default='Branch_Gabungan');a.add_argument('--out',type=pathlib.Path,default=pathlib.Path('.'));args=a.parse_args()
    repo=args.repo.resolve();head=git(repo,'rev-parse',args.ref+'^{commit}');current=git(repo,'rev-parse','HEAD')
    if head!=current:raise SystemExit('STOP: checkout HEAD != selected branch commit; checkout target branch first (no checkout performed)')
    records=[]; flows={}; reverse=collections.defaultdict(list); errors=[];categories=collections.Counter();nxml=0
    # git ls-tree includes blob SHAs independently of working tree timestamps
    for line in git(repo,'ls-tree','-r','-l','HEAD').splitlines():
        m=re.match(r'^\d+ blob ([0-9a-f]{40})\s+(\d+)\t(.+)$',line)
        if not m:continue
        sha,size,path=m.groups();type_=path[len(ROOT):].split('/')[0] if path.startswith(ROOT) else '_other'
        record={'path':path,'blob_sha':sha,'bytes':int(size),'category':type_}; records.append(record);categories[type_]+=1
        if not path.endswith('.xml'):continue
        try:
            content=(repo/path).read_bytes();root=ET.fromstring(content);nxml+=1
            refs=collect_refs(root)
            if type_=='flows' and path.endswith('.flow-meta.xml'):
                flowname=path.split('/')[-1][:-len('.flow-meta.xml')];data=parse_flow(root);flows[flowname]={'path':path,'blob_sha':sha,**data};refs=data['refs']
            for typ,items in refs.items():
                for item in items:reverse[typ+':'+item].append(path)
            # Derive object/field relations from DX path (proven path-level only)
            mm=re.match(r'^force-app/main/default/objects/([^/]+)/fields/([^/]+)\.field-meta\.xml$',path)
            if mm: reverse['object_field:'+mm[1]+'.'+mm[2]].append(path)
        except Exception as e:errors.append({'path':path,'error':str(e)[:200]})
    for k,v in reverse.items():reverse[k]=sorted(set(v))
    doc={'schema':'catalyst/v1','coverage':'parsed_repository','source':{'repository':'bfi-finance/bfi-pbf-live','branch':args.ref,'commit_sha':head},'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'statistics':{'files':len(records),'xml_parsed':nxml,'flows_parsed':len(flows),'errors':len(errors),'categories':dict(sorted(categories.items()))},'files':records,'flows':flows,'reverse_index':dict(sorted(reverse.items())),'parse_errors':errors,'cautions':['Git metadata is not proof of LIVE deployment or active runtime version','Reference extraction is heuristic; reconcile with XML before concluding RCA','No Salesforce org queried']}
    args.out.mkdir(parents=True,exist_ok=True);out=args.out/'catalyst-index.json';out.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    md=f'''# Catalyst v1 — Salesforce Metadata Index

Source: bfi-finance/bfi-pbf-live / {args.ref} / {head}.
Generated: {doc['generated_utc']}.

## Coverage
- Files: {len(records)}
- Parsed XML: {nxml}
- Parsed flows: {len(flows)}
- Parse errors: {len(errors)}
- Metadata categories: {len(categories)}

## RCA usage
1. Look up exact API Name in reverse_index and flows in catalyst-index.json.
2. Use files[*].blob_sha to verify the Git source at the pinned commit.
3. Inspect original XML nodes, connectors, conditions, DML and faults; do not infer behavior from names.
4. Validate deployed/active Flow versions, permission and runtime record via authorized LIVE read-only queries.
5. Mark findings SOURCE/LIVE/INFERENCE; do not assume Git proves runtime.

This document is a navigational index, not evidence that metadata is deployed.
'''
    (args.out/'catalyst.md').write_text(md,encoding='utf-8')
    print(json.dumps(doc['statistics'],indent=2));print('OUTPUT',out)
if __name__=='__main__':main()
