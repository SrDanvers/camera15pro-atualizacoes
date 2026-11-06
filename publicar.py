import os,json,urllib.request,subprocess,re,hashlib,pathlib
release=json.loads(os.environ['RELEASE_JSON'])
if release.get('prerelease') or release.get('draft'): raise SystemExit('Somente releases finais')
assets=[a for a in release['assets'] if a['name'].endswith('.apk')]
if len(assets)!=1:raise SystemExit('Anexe exatamente um APK assinado antes de publicar a release')
asset=assets[0];url=asset['browser_download_url']
if not url.startswith('https://github.com/SrDanvers/camera15pro-atualizacoes/releases/download/'):raise SystemExit('Repositorio inesperado')
data=urllib.request.urlopen(url,timeout=60).read(100*1024*1024+1)
if len(data)>100*1024*1024:raise SystemExit('APK grande demais')
pathlib.Path('camera.apk').write_bytes(data)
sdk=pathlib.Path(os.environ.get('ANDROID_HOME','/usr/local/lib/android/sdk'))
aapt=sorted(sdk.glob('build-tools/*/aapt'))[-1];signer=sorted(sdk.glob('build-tools/*/apksigner'))[-1]
badging=subprocess.check_output([str(aapt),'dump','badging','camera.apk'],text=True)
m=re.search(r"package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'",badging)
if not m or m[1]!='br.com.denny.camera':raise SystemExit('Pacote incorreto')
cert=subprocess.check_output([str(signer),'verify','--print-certs','camera.apk'],text=True)
pinned=pathlib.Path('certificado-sha256.txt').read_text().strip()
digests=re.findall(r'certificate SHA-256 digest:\s*([0-9a-fA-F:]+)',cert,re.I)
normalize=lambda value: value.replace(':','').strip().lower()
if not digests or any(normalize(value)!=normalize(pinned) for value in digests):raise SystemExit('Assinatura diferente da oficial')
code=int(m[2]);old=json.loads(pathlib.Path('update.json').read_text()) if pathlib.Path('update.json').exists() else {}
if code<int(old.get('versionCode',0)):raise SystemExit('Versao inferior ao canal atual')
manifest=dict(versionCode=code,versionName=m[3],minVersionCode=code,apkUrl=url,sha256=hashlib.sha256(data).hexdigest(),notes=(release.get('body') or 'Nova versão disponível')[:2000])
pathlib.Path('update.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
pathlib.Path('camera.apk').unlink()
