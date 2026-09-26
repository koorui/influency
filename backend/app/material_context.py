"""Locate exact source passages for retrieval planning; no factual assertions."""
import re


def relevant_context(materials,names,budget=46000):
    terms=set()
    for name in names:
        terms.update(t.lower() for t in re.findall(r'[A-Za-z][A-Za-z0-9\[\]_-]{3,}',name or ''))
        for run in re.findall(r'[\u4e00-\u9fff]+',name or ''):
            terms.update(run[i:i+4] for i in range(max(0,len(run)-3)))
    blocks=[]
    for m in materials:
        lines=m['text'].splitlines();covered=set()
        for i,line in enumerate(lines):
            if not any(t in line.lower() for t in terms):continue
            start=max(0,i-20);end=min(len(lines),i+26)
            if sum(j in covered for j in range(start,end))>(end-start)*.7:continue
            covered.update(range(start,end))
            text='\n'.join(f'{j+1}: {lines[j]}' for j in range(start,end))
            score=2*len(re.findall(r'202[0-9]年|10\.\d{4,9}/|s\d{5}-\d{3}-',text))+len(re.findall(r'doi|github|模型|验证|测试|论文',text,re.I))
            blocks.append((score,{'material_id':m['id'],'filename':m['filename'],'start_line':start+1,'end_line':end,'text':text}))
    result=[];used=0
    for _,block in sorted(blocks,key=lambda b:b[0],reverse=True):
        if used+len(block['text'])>budget:continue
        result.append(block);used+=len(block['text'])
    return result
