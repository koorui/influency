import {test,expect} from '@playwright/test'

test('完整工作流创建、阶段展示与下载权限',async({page})=>{
  const password=process.env.E2E_ADMIN_PASSWORD
  test.skip(!password,'需要本地管理员测试凭据')
  await page.goto('/login')
  await page.getByLabel('账号',{exact:true}).fill('admin')
  await page.getByLabel('密码',{exact:true}).fill(password!)
  await page.getByRole('button',{name:'登录',exact:true}).click()
  await expect(page.getByRole('heading',{name:'评价工作台'})).toBeVisible()
  const title=`Pipeline界面测试-${Date.now()}`
  const upload=await page.request.post('/api/admin/materials',{multipart:{file:{name:'pipeline-ui.txt',mimeType:'text/plain',buffer:Buffer.from('这是工作流界面测试材料，不用于正式模型评价。')}}})
  expect(upload.ok()).toBeTruthy()
  await page.getByRole('tab',{name:'完整工作流',exact:true}).click()
  await page.getByText('＋ 新建完整评价工作流', {exact:true}).click()
  await page.getByLabel('工作流成果名称',{exact:true}).fill(title)
  await page.getByLabel('工作流项目名称',{exact:true}).fill('界面测试项目')
  await page.getByLabel('工作流项目ID',{exact:true}).fill('UI-TEST')
  await page.getByLabel('工作流成果ID',{exact:true}).fill('UI-OUTCOME')
  await page.getByTestId('pipeline-materials').click()
  await page.getByRole('option',{name:'pipeline-ui.txt',exact:true}).last().click()
  await page.getByLabel('已确认范围',{exact:true}).click()
  const created=page.waitForResponse(r=>r.url().endsWith('/api/admin/pipelines') && r.request().method()==='POST')
  await page.getByRole('button',{name:'创建完整工作流',exact:true}).click()
  const response=await created
  expect(response.status()).toBe(201)
  const job=await response.json()
  // Cancel before any model worker is launched; this test is explicitly UI/API-only.
  const cancelled=await page.request.post(`/api/admin/pipelines/${job.id}/cancel`,{data:{revision:job.revision}})
  expect(cancelled.status()).toBe(200)
  await page.getByRole('button',{name:'刷新工作流',exact:true}).click()
  await page.getByRole('row').filter({hasText:title}).getByRole('button',{name:'查看工作流'}).click()
  await expect(page.getByRole('dialog').getByText('① 吴老师：成果定位与建卡',{exact:true})).toBeVisible()
  await expect(page.getByRole('dialog').getByText('⑤ v19：双层评估',{exact:true})).toBeVisible()
  await expect(page.getByRole('dialog').getByText('阶段底稿与独立结果',{exact:true})).toBeVisible()
  await page.screenshot({path:'test-results/pipeline-admin.png',fullPage:true})
  const blocked=await page.request.get(`/api/admin/pipelines/${job.id}/artifact?path=../../.env`)
  expect(blocked.status()).toBe(404)
})
