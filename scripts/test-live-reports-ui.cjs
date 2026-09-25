const {chromium}=require('../frontend/node_modules/playwright');
const fs=require('fs');const path=require('path');const crypto=require('crypto');
(async()=>{
  const base=path.resolve(__dirname,'..');
  const registration=JSON.parse(fs.readFileSync(path.join(base,'backend/storage/search-live-downstream-raman-2/registered-pipeline.json'),'utf8'));
  const id=registration.pipeline_id;const output=path.join(base,'backend/storage/live-report-ui-test-'+Date.now());fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({headless:true});
  try{
    const context=await browser.newContext({viewport:{width:1440,height:1200}});const page=await context.newPage();
    await page.goto(`http://localhost:5173/admin?pipeline=${id}`);
    await page.waitForURL(/\/login\?redirect=/);
    await page.getByLabel('账号',{exact:true}).fill('admin');await page.getByLabel('密码',{exact:true}).fill('123456');
    await page.getByRole('button',{name:'登录',exact:true}).click();
    await page.waitForURL(`http://localhost:5173/admin?pipeline=${id}`);
    const workflow=page.getByRole('dialog',{name:'完整评价工作流',exact:true});await workflow.waitFor();
    const response=await context.request.get(`http://localhost:5173/api/admin/pipelines/${id}`);if(!response.ok())throw new Error('Pipeline detail failed');
    const detail=await response.json();
    if(!Object.values(detail.stages).every(s=>s.status==='succeeded'))throw new Error('Incomplete workflow');
    if(!detail.scope_options.some(o=>o.id==='ACH-002')||detail.scope_evidence.length!==8)throw new Error('Frozen scope or evidence missing');
    if(await workflow.getByLabel('补充评审截止日期',{exact:true}).inputValue()!=='2026-04-30')throw new Error('Review cutoff not shown');
    await page.screenshot({path:path.join(output,'workflow.png'),fullPage:true,animations:'disabled'});
    await workflow.getByRole('button',{name:'预览吴老师报告',exact:true}).click();
    const wu=page.getByRole('dialog',{name:'吴老师成果报告 · 待审核',exact:true});await wu.waitFor();
    await wu.getByText(/外部证据核验截至 2026-04-30/).waitFor();
    if(!(await wu.locator('.grade').innerText()).includes('L2'))throw new Error('Real Wu result not rendered');
    await page.screenshot({path:path.join(output,'wu-report.png'),fullPage:true,animations:'disabled'});
    await wu.locator('.evidence-index').first().click();
    const evidence=page.getByRole('dialog',{name:'证据详情',exact:true});await evidence.waitFor();
    if((await evidence.locator('blockquote').innerText()).length<15)throw new Error('Original quotation missing');
    await evidence.getByRole('button',{name:'Close this dialog',exact:true}).click();
    await evidence.waitFor({state:'hidden'});
    await wu.getByRole('button',{name:'Close this dialog',exact:true}).click();
    await workflow.getByRole('button',{name:'预览v19独立底稿',exact:true}).click();
    const v19=page.getByRole('dialog',{name:'v19双层评估 · 独立底稿',exact:true});await v19.waitFor();
    await v19.getByRole('heading',{name:'成果整体：待确认',exact:true}).waitFor();
    if(await v19.locator('.el-table__body-wrapper tbody tr').count()!==7)throw new Error('Seven dimensions not rendered');
    await page.screenshot({path:path.join(output,'v19-report.png'),fullPage:true,animations:'disabled'});
    await v19.getByRole('button',{name:'Close this dialog',exact:true}).click();
    const [draftResponse]=await Promise.all([page.waitForResponse(r=>r.url().endsWith(`/pipeline-reports/${id}/draft`)&&r.request().method()==='POST'),workflow.getByRole('button',{name:'转入报告审核',exact:true}).click()]);
    if(draftResponse.status()!==201)throw new Error('Draft creation failed: '+await draftResponse.text());
    const draft=await draftResponse.json();if(draft.status!=='draft'||draft.payload.is_demo)throw new Error('Real report must remain draft');
    const guest=await browser.newContext();
    const hidden=await guest.request.get(`http://localhost:5173/api/results/${draft.id}`);if(hidden.status()!==404)throw new Error('Draft exposed to ordinary visitor');
    const blocked=await guest.request.get(`http://localhost:5173/api/admin/pipelines/${id}`);if(blocked.status()!==401)throw new Error('Admin details exposed');
    await guest.close();
    const tablePath='search_replay/attempt-1/required-tables/report/04_综合结论/证据总索引.csv';
    const table=await context.request.get(`http://localhost:5173/api/admin/pipelines/${id}/artifact?path=${encodeURIComponent(tablePath)}`);
    if(table.status()!==200||!(await table.text()).includes('证据ID'))throw new Error('Evidence CSV download failed');
    const manifest=await (await context.request.get(`http://localhost:5173/api/admin/pipelines/${id}/artifact?path=export/attempt-1/manifest.json`)).json();
    if(manifest.wu.rubric_id===manifest.v19.rubric_id||manifest.published!==false)throw new Error('Rubrics were merged or published');
    const library=JSON.parse(fs.readFileSync(path.join(base,'backend/storage/chemistry-library/manifest.json'),'utf8'));
    for(const file of library.records){
      const response=await context.request.get(`http://localhost:5173/api/admin/materials/${file.material_id}/download`,{timeout:120000});
      if(response.status()!==200)throw new Error('Original download failed: '+file.filename);
      const sha=crypto.createHash('sha256').update(await response.body()).digest('hex');if(sha!==file.sha256)throw new Error('Original bytes changed: '+file.filename);
    }
    fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'passed',pipeline_id:id,result_id:draft.id,published:false,original_downloads_verified:library.records.length,
      checks:['login returns to target workflow','six stages shown completed','review dates and frozen child controls','Wu actual L2 report and original quote','v19 seven dimensions and pending overall result','real report draft creation','draft and admin access isolation','CSV download','two independent rubric exports','all six original HTTP downloads match SHA256']},null,2));
    fs.writeFileSync(path.join(base,'backend/storage/search-live-downstream-raman-2/review-ready.json'),JSON.stringify({pipeline_id:id,result_id:draft.id,ui_test_dir:output,status:'draft',published:false},null,2));
    console.log(JSON.stringify({status:'passed',output,pipeline_id:id,result_id:draft.id}));
  }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
