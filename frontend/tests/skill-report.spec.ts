import {test,expect} from '@playwright/test'

const payload={schema_version:'1.0',title:'界面验证成果',keywords:['验证'],category:'科研成果',summary:'仅用于界面测试的报告。',level:3,level_name:'外部应用验证',reasons:['已有独立使用证据','持续采用尚待核验'],reason_evidence_refs:[['E1'],[]],dimensions:[{topic:'外部应用',claim:'项目方称已被采用',assessment:'材料可确认一次使用',evidence_ids:['E1'],project_evidence_ids:[]}],evidence:[{id:'E1',title:'独立团队使用记录与应用情况'.repeat(10),source:'界面测试来源',excerpt:'这是测试引文，不是真实项目依据。',material_id:null,locator:'第1段',kind:'external',url:'https://example.com/evidence',supports:'一次使用',does_not_prove:'持续采用',verification:'verified'}],follow_ups:[{title:'请项目组补充材料',detail:'请补持续使用记录',body:'项目组您好：\n请提供持续使用记录。',kind:'material'}],is_demo:true,evaluation_status:'formal',project_name:'界面测试项目',upgrades:[{target_level:4,level_name:'专业方向显著影响',need:'多团队持续采用',proof_materials:['连续使用记录']},{target_level:5,level_name:'领域基础能力',need:'成为领域基础能力',proof_materials:['领域多方向使用证明']}]}

test('新版报告的升级路径、证据来源、任务编辑和窄屏布局',async({page})=>{
  await page.route('**/api/results/report-test',r=>r.fulfill({json:{id:'report-test',payload,status:'published',revision:1}}))
  await page.goto('/results/report-test')
  await expect(page.getByText('提升1级 → L4 · 专业方向显著影响')).toBeVisible()
  await expect(page.getByText('提升2级 → L5 · 领域基础能力')).toBeVisible()
  await page.getByRole('button',{name:'查看任务',exact:true}).click()
  await page.getByRole('textbox',{name:'任务文案'}).fill('修改后的补证文案')
  await page.getByRole('button',{name:'恢复原文',exact:true}).click()
  await expect(page.getByRole('textbox',{name:'任务文案'})).toHaveValue('项目组您好：\n请提供持续使用记录。')
  await page.getByRole('dialog').getByRole('button',{name:'Close this dialog'}).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await page.locator('.evidence-index').first().click()
  await expect(page.getByRole('link',{name:'打开原始来源'})).toHaveAttribute('href','https://example.com/evidence')
  await expect(page.getByText('不能证明：持续采用')).toBeVisible()
  await page.evaluate(()=>{document.body.style.zoom='1.25'})
  expect(await page.getByRole('dialog').evaluate(e=>e.scrollWidth<=e.clientWidth+1)).toBeTruthy()
  await page.setViewportSize({width:390,height:844})
  await page.evaluate(()=>{document.body.style.zoom='1'})
  expect(await page.getByRole('dialog').evaluate(e=>e.scrollWidth<=e.clientWidth+1)).toBeTruthy()
})
