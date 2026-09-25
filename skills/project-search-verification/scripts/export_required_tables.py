"""Original workflow table contract, with explicit gaps instead of invented metrics."""
import csv
import json
from pathlib import Path

GROUPS={
 '00_项目输入与审计边界':['项目材料清单.csv','项目成果声明抽取表.csv','评审时间窗口表.csv'],
 '01_SOTA与对比指标验证':['对比方法原始指标表.csv','论文声明与评审时点SOTA核验表.csv','指标可比性与参数差异表.csv','其他方法实际指标估计表.csv'],
 '02_项目前既有成果追溯':['团队成员既有论文表.csv','团队成员既有专利表.csv','团队成员其他研究成果表.csv','学校学院既有研究成果表.csv','项目成果时间归属与复用判断表.csv'],
 '03_成果使用评价与媒体报道':['外部使用与部署表.csv','外部评价与引用表.csv','新闻与媒体自媒体报道表.csv','项目内部自报应用核验表.csv'],
 '04_综合结论':['综合判断总表.csv','高风险误归属与复用清单.csv','超出评审时间窗口排除清单.csv','待线下核验材料清单.csv','证据总索引.csv']}


def write_csv(path,columns,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(dict.fromkeys(columns+['填报状态','未核验说明'])),extrasaction='ignore')
        writer.writeheader()
        for row in rows:writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})


def export_required(result,audited,output,sources,context=None):
    specs=json.loads((Path(__file__).resolve().parents[1]/'schemas/required-tables.json').read_text(encoding='utf-8'))
    context=context or {};intake=context.get('intake',{})
    claims={c['id']:c for c in intake.get('claims',[])}
    evidence={e['id']:e for e in intake.get('evidence',[])}
    outcome=intake.get('canonical_name') or result.outcome_id
    stage='本次评审窗口'
    common={'对应阶段ID':stage,'评审基准日':result.review_cutoff,'成果名称':outcome,'项目成果':outcome}
    rows={name:[] for group in GROUPS.values() for name in group}
    seen_materials=set()
    for e in evidence.values():
        identifier=e.get('material_id')
        if identifier in seen_materials:continue
        seen_materials.add(identifier)
        rows['项目材料清单.csv'].append({'材料ID':identifier,'文件名':'见原材料登记ID','对应评审阶段':stage,
            '主要用途':'原始成果定位与项目方声明','是否包含成果声明':'是','备注':e.get('locator',''),
            '填报状态':'已关联原材料；其余元数据未传入','未核验说明':'不能仅凭摘录推断材料日期、完整人员名单或合同情况'})
    for identifier,c in claims.items():
        refs=c.get('evidence_ids',[])
        rows['项目成果声明抽取表.csv'].append({**common,'声明ID':identifier,'对应课题':result.project_id,'对应评审阶段':stage,
            '项目声明内容':c.get('text',''),'项目材料来源':[evidence[r].get('material_id') for r in refs if r in evidence],
            '页码、表格行号或单元格':[evidence[r].get('locator') for r in refs if r in evidence],
            '填报状态':'原始自报声明，待按各模块核验','未核验说明':'声明形成日及各项结构化指标不得从检索日期反推'})
    rows['评审时间窗口表.csv']=[{'阶段ID':stage,'阶段名称':stage,'阶段开始时间':result.project_start_date,'评审基准日':result.review_cutoff,
        '数据统计截止日':result.review_cutoff,'日期来源':result.cutoff_basis,'适用声明ID':list(claims),'填报状态':'本次输入固定边界'}]
    for check in audited['checks']:
        base={**common,'声明ID':check['claim_id'],'证据ID':check['eligible_evidence_ids'],'填报状态':check['formal_status'],
              '未核验说明':check['formal_conclusion']+' '+check['protocol_notes']}
        if check['module']=='sota':
            rows['论文声明与评审时点SOTA核验表.csv'].append({**base,'项目声明是否成立':check['formal_status'],'参数或数据差异':check['protocol_notes'],
                '判断置信度':check['confidence'],'评审基准日前真实SOTA':'未形成经完整时点核验的排名'})
            rows['指标可比性与参数差异表.csv'].append({**base,'可比性等级':'待核验','可比性置信度':check['confidence']['protocol'],'备注':check['protocol_notes']})
        if check['module']=='prior_work':
            rows['项目成果时间归属与复用判断表.csv'].append({**base,'项目申报成果':outcome,'项目启动日':result.project_start_date,
                '对应评审基准日':result.review_cutoff,'归属分类':check['formal_status'],'风险说明':check['formal_conclusion'],
                '时间归属置信度':check['confidence']['time']})
        if check['module']=='usage_media':
            rows['项目内部自报应用核验表.csv'].append({**base,'项目材料中的应用、合同或部署声称':claims.get(check['claim_id'],{}).get('text',''),
                '是否能够公开确认':check['formal_status'],'当前可采用表述':check['formal_conclusion'],
                '公开确认置信度':check['confidence']})
        if check['formal_status'] in ('not_verified','partial','conflicts'):
            rows['待线下核验材料清单.csv'].append({'核验ID':check['id'],'待核事项':check['formal_conclusion'],
                '当前公开证据':check['eligible_evidence_ids'],'证据缺口':check['protocol_notes'] or '引用未通过完整日期或正文审计',
                '建议索取材料':'与该声明直接对应的有日期原始记录、对照协议或独立证明','优先级':'待管理员按结论影响确定',
                '对最终结论的影响':'未解决前不得作为提升等级的正式依据','填报状态':check['formal_status']})
    for identifier,claim in claims.items():
        relevant=[c for c in audited['checks'] if c['claim_id']==identifier]
        conclusions=lambda m:'；'.join(c['formal_conclusion'] for c in relevant if c['module']==m) or '本轮未形成针对本声明的独立核验'
        rows['综合判断总表.csv'].append({**common,'声明ID':identifier,'原始项目声明':claim.get('text',''),
            'SOTA核验结论':conclusions('sota'),'项目前既有成果结论':conclusions('prior_work'),'外部使用结论':conclusions('usage_media'),
            '核心证据ID':list(dict.fromkeys(i for c in relevant for i in c['eligible_evidence_ids'])),
            '综合判断':'；'.join(c['formal_conclusion'] for c in relevant) or '待核验',
            '填报状态':'已汇总本轮核验边界；不等于全部声明已验证'})
    for source in sources:
        index={'证据ID':source['id'],'所属模块':source['module'],'对应阶段ID':stage,'对应评审基准日':result.review_cutoff,
            '证据类型':'公开检索来源','本地相对路径':source['本地相对路径'],'来源标题':source['title'],'原始URL':source['url'],
            '来源机构':source['publisher'],'首次公开日期':source['first_public_date'],'事件日期':source['event_date'],
            '当前采集日期':source['accessed_at'],'是否处于有效时间窗口':source['time_status'],'保存格式':source['保存格式'],
            '保存状态':source['保存状态'],'对应项目成果':outcome,'主要用途':source['supports'],'访问限制':source['访问限制'],
            '备注':source['does_not_prove'],'填报状态':source['time_status']}
        rows['证据总索引.csv'].append(index)
        if source['time_status'] in ('unknown_date','not_verified'):
            rows['待线下核验材料清单.csv'].append({'核验ID':'SRC-'+source['id'],'待核事项':source['title'],
                '当前公开证据':source['url'],'证据缺口':'首次公开日/事件日未完整确认' if source['time_status']=='unknown_date' else '未完成正文核验',
                '建议索取材料':'提供能确认日期及所述事件的原始记录，或补充可读取原文','对最终结论的影响':'不计正式外部支持','填报状态':source['time_status']})
        if source['time_status']=='excluded_after_cutoff':
            rows['超出评审时间窗口排除清单.csv'].append({'ID':source['id'],'对应声明ID':source['claim_ids'],'对应成果':outcome,
                '搜索结果题名':source['title'],'来源URL':source['url'],'来源公开日期':source['first_public_date'],'事件发生日期':source['event_date'],
                '对应评审基准日':result.review_cutoff,'超出时间范围的原因':'首次公开日或事件日晚于评审截止日','填报状态':'排除'})
    internal_folder=output/'00_项目输入与审计边界/evidence';internal_folder.mkdir(exist_ok=True)
    existing_ids={row['证据ID'] for row in rows['证据总索引.csv']}
    for n,(identifier,item) in enumerate(evidence.items(),1):
        if identifier in existing_ids:raise ValueError('内部与外部证据索引编号冲突')
        relative=Path('00_项目输入与审计边界/evidence')/f'project-evidence-{n:03d}.txt'
        (output/relative).write_text(str(item.get('quote','')),encoding='utf-8')
        rows['证据总索引.csv'].append({'证据ID':identifier,'所属模块':'项目原始材料','对应阶段ID':stage,'对应评审基准日':result.review_cutoff,
            '证据类型':'项目材料摘录；内部自报','本地相对路径':[relative.as_posix()],'来源标题':item.get('material_id',''),
            '来源机构':intake.get('project_name') or result.project_id,'保存格式':'text/plain；原材料摘录，不是完整原文件',
            '保存状态':'摘录已保存；完整原件见材料库','对应项目成果':outcome,'主要用途':'追溯项目声明',
            '备注':item.get('locator',''),'填报状态':'项目自报，未独立核验','是否处于有效时间窗口':'不得自动视为评审时点公开可得'})
    for record in result.research_records:
        eligible=bool(record.source_ids) and all(audited['source_status'][s]=='eligible' for s in record.source_ids)
        internal_ids=list(dict.fromkeys(e for c in record.claim_ids for e in claims.get(c,{}).get('evidence_ids',[])))
        rows[record.table].append({**{c.column:c.value for c in record.cells},'证据ID':list(dict.fromkeys([*record.source_ids,*internal_ids])),
            '声明ID':record.claim_ids,'是否处于有效时间窗口':'通过公开来源时点审计' if eligible else '待核验：内部声明或公开来源日期/正文未完整核验',
            '填报状态':'来源与时点已核验；仍需判断内容是否支持该关系' if eligible else '待核验：内部声明或来源未通过完整时点审计',
            '未核验说明':record.limitation+f' 原记录类型：{record.status}；关联声明：'+','.join(record.claim_ids)})
    coverage=[]
    for directory,names in GROUPS.items():
        for name in names:
            write_csv(output/directory/name,specs[name],rows[name])
            coverage.append({'文件':f'{directory}/{name}','行数':len(rows[name]),
                '状态':'已输出已有结构化记录，未核字段留空' if rows[name] else '待补证：未取得足以填报该类关系的结构化依据',
                '边界':'空表不等于不存在；不把同名、引用、合作、自报或估计当成独立实测'})
    negative_columns=['模块','检索词','渠道','执行日期','观察状态','关联来源','说明']
    for module,directory,name in [('sota','01_SOTA与对比指标验证','阴性检索与误命中排除表.csv'),
        ('prior_work','02_项目前既有成果追溯','阴性检索与身份歧义表.csv'),('usage_media','03_成果使用评价与媒体报道','阴性检索与同名误命中表.csv')]:
        negative=[{'模块':q.module,'检索词':q.query,'渠道':q.channel,'执行日期':q.executed_at,'观察状态':q.outcome,
                   '关联来源':q.source_ids,'说明':q.note} for q in result.queries if q.module==module and q.outcome!='results_found']
        write_csv(output/directory/name,negative_columns,negative)
    for directory,name in [('01_SOTA与对比指标验证','SOTA验证报告.md'),('02_项目前既有成果追溯','项目前成果追溯报告.md'),('03_成果使用评价与媒体报道','成果使用与媒体验证报告.md')]:
        (output/directory/name).write_text((output/directory/'核验报告.md').read_text(encoding='utf-8')+'\n\n专门表格空行表示该类结构化依据缺失，不表示不存在；请结合综合目录的交付覆盖检查查看缺项。\n',encoding='utf-8')
    write_csv(output/'04_综合结论/交付覆盖检查.csv',['文件','行数','状态','边界'],coverage)
    module_map={m.id:m for m in result.modules}
    links={name:f'[{name}](../{directory}/{name})' for directory,names in GROUPS.items() for name in names}
    sections=[
        ('项目基本信息',f'项目：{intake.get("project_name") or result.project_id}；成果：{outcome}。本轮只核验这一具体成果。'),
        ('项目启动时间',str(result.project_start_date)),
        ('各阶段评审基准日',f'本次阶段：{result.review_cutoff}。日期依据：{result.cutoff_basis}。其他阶段未在本轮输入中指定。'),
        ('成果有效时间窗口',f'本成果按{result.review_cutoff}进行时点审计；前序追溯另以项目启动日{result.project_start_date}为界。'),
        ('项目成果声明概览',f'本轮输入{len(claims)}条项目声明。见'+links['项目成果声明抽取表.csv']),
        ('对比方法原始指标','尚未取得可直接填报的同口径原始指标明细。见'+links['对比方法原始指标表.csv']),
        ('截至评审基准日的SOTA',module_map['sota'].summary+' 正式判断以时间审计状态为准。见'+links['论文声明与评审时点SOTA核验表.csv']),
        ('数据集、参数和测评协议差异','不把不同测评协议的数值直接排名。见'+links['指标可比性与参数差异表.csv']),
        ('其他方法实际指标估计','本轮没有满足明确推算依据和关键假设的估计，不生成推荐值。见'+links['其他方法实际指标估计表.csv']),
        ('团队成员项目前论文','未形成同时具备成员身份、论文对应与时点依据的结构化记录。见'+links['团队成员既有论文表.csv']),
        ('团队成员项目前专利','未形成同时具备人员身份、专利及日期依据的结构化记录。见'+links['团队成员既有专利表.csv']),
        ('团队成员其他既有成果','未形成可确认人员与成果归属的结构化记录。见'+links['团队成员其他研究成果表.csv']),
        ('学校学院或机构既有成果','同机构成果不自动归入项目团队。见'+links['学校学院既有研究成果表.csv']),
        ('成果时间归属与复用',module_map['prior_work'].summary+' 见'+links['项目成果时间归属与复用判断表.csv']),
        ('外部实际使用',module_map['usage_media'].summary+' 不把背景方法使用迁移为本成果部署。见'+links['外部使用与部署表.csv']),
        ('外部评价与引用','未取得可确认独立引用者、引用事件及实际运行关系的结构化记录。见'+links['外部评价与引用表.csv']),
        ('新闻与媒体、自媒体报道','未形成可确认来源链、内部供稿和独立评价关系的结构化记录。见'+links['新闻与媒体自媒体报道表.csv']),
        ('内部与外部使用区分','项目报告属于内部自报；合作单位不自动等于独立第三方，引用/星标不自动等于实际使用。见'+links['项目内部自报应用核验表.csv']),
        ('同名误命中','公开索引可能返回同名异领域来源；仅标题/关键词相同不能确认对象。详见各模块检索日志、候选归档和阴性检索表。'),
        ('超出时间窗口的排除',f'本轮报告来源中排除{sum(s["time_status"]=="excluded_after_cutoff" for s in sources)}条；日期未知另列待核，不视为窗口内。见'+links['超出评审时间窗口排除清单.csv']),
        ('负检索与访问失败',f'未取得可核验引用的查询{sum(q.outcome=="no_verified_result" for q in result.queries)}次，访问或解析失败{sum(q.outcome=="access_failed" for q in result.queries)}次。前者仅限本次实际检索范围；后者不能作为不存在证据。'),
        ('高风险误归属','本轮未形成已确认误归属事件的独立结构化记录；这不表示不存在风险。见'+links['高风险误归属与复用清单.csv']),
        ('线下待核材料','按声明补充有日期的任务书、对照协议、原始测量、合同、验收、历史代码版本或真实用户证明。见'+links['待线下核验材料清单.csv'])]
    supplied={record.table for record in result.research_records}
    for n,(title,text) in enumerate(sections):
        for name in supplied:
            if links[name] in text:
                sections[n]=(title,f'本轮记录{len(rows[name])}项，见{links[name]}。未确认字段留空，证据和时点状态逐行列出；不能仅凭存在记录认定团队身份、独立使用或指标达成。')
                break
    (output/'04_综合结论/规范分项说明.md').write_text('\n\n'.join(f'## {n}. {title}\n\n{text}' for n,(title,text) in enumerate(sections,1)),encoding='utf-8')
    return coverage
