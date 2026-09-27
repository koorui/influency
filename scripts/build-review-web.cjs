// Local review build using installed compilers and explicit file names.
const fs = require('node:fs');
const path = require('node:path');
const repo = path.resolve(__dirname, '..');
const frontend = path.join(repo, 'frontend');
const esbuild = require(path.join(frontend, 'node_modules/esbuild'));
const vue = require(path.join(frontend, 'node_modules/@vue/compiler-sfc'));
const out = path.resolve(process.argv[2] || path.join(repo,'.local-runtime/teacher-v4/web'));
const styles = new Map();
const plugin = {
  name: 'local-vue-review',
  setup(build) {
    build.onResolve({filter: /^local-vue-style:/}, args => ({path: args.path, namespace: 'local-vue-style'}));
    build.onLoad({filter: /.*/, namespace: 'local-vue-style'}, args => ({contents: styles.get(args.path), loader: 'css', resolveDir: frontend}));
    build.onLoad({filter: /\.vue$/}, args => {
      const source = fs.readFileSync(args.path, 'utf8');
      const parsed = vue.parse(source, {filename: args.path});
      if (parsed.errors.length) throw parsed.errors[0];
      const d = parsed.descriptor;
      const id = path.relative(frontend, args.path).replace(/[^a-zA-Z0-9_]/g, '_');
      const script = d.script || d.scriptSetup ? vue.compileScript(d, {id, genDefaultAs: '__sfc__'}) : {content:'const __sfc__ = {};', bindings:{}};
      let contents = script.content;
      if (d.template) {
        const template = vue.compileTemplate({source: d.template.content, filename:args.path, id,
          scoped:d.styles.some(s => s.scoped), compilerOptions:{bindingMetadata:script.bindings}});
        if (template.errors.length) throw template.errors[0];
        contents += '\n'+template.code+'\n__sfc__.render = render;';
      }
      if (d.styles.some(s => s.scoped)) contents += '\n__sfc__.__scopeId = '+JSON.stringify('data-v-'+id)+';';
      d.styles.forEach((style,index) => {
        const css = vue.compileStyle({source:style.content, filename:args.path, id:'data-v-'+id, scoped:style.scoped});
        if (css.errors.length) throw css.errors[0];
        const key='local-vue-style:'+id+'_'+index;
        styles.set(key,css.code);
        contents += '\nimport '+JSON.stringify(key)+';';
      });
      return {contents:contents+'\nexport default __sfc__;', loader:'ts', resolveDir:path.dirname(args.path)};
    });
  }
};
(async () => {
  fs.mkdirSync(path.join(out,'assets'),{recursive:true});
  await esbuild.build({absWorkingDir:frontend,entryPoints:['src/main.ts'],bundle:true,minify:true,
    platform:'browser',format:'esm',target:'es2022',outfile:path.join(out,'assets/app.js'),assetNames:'[name]',
    define:{'process.env.NODE_ENV':'"production"',__VUE_OPTIONS_API__:'true',__VUE_PROD_DEVTOOLS__:'false',__VUE_PROD_HYDRATION_MISMATCH_DETAILS__:'false'},
    loader:{'.svg':'dataurl','.png':'dataurl','.woff2':'file','.woff':'file'},plugins:[plugin]});
  const html=fs.readFileSync(path.join(frontend,'index.html'),'utf8').replace('/src/main.ts','/assets/app.js').replace('</head>','<link rel="stylesheet" href="/assets/app.css"></head>');
  fs.writeFileSync(path.join(out,'index.html'),html);
  if(fs.existsSync(path.join(frontend,'public'))) fs.cpSync(path.join(frontend,'public'),out,{recursive:true});
  process.stdout.write('Local web build completed: '+out+'\n');
})().catch(error=>{process.stderr.write(String(error)+'\n');process.exitCode=1;});
