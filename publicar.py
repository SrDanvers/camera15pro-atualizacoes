import os,json,urllib.request,subprocess,re,hashlib,pathlib
release=json.loads(os.environ['RELEASE_JSON'])

# Publicacao de um APK previamente assinado enviado pela conexao GitHub.
pending_path=pathlib.Path('incoming/pending.json')
current=json.loads(pathlib.Path('update.json').read_text()) if pathlib.Path('update.json').exists() else {}
if pending_path.exists():
 pending=json.loads(pending_path.read_text())
 if int(pending['versionCode'])>int(current.get('versionCode',0)):
  apk=pathlib.Path('incoming')/pending['filename']
  if apk.parent!=pathlib.Path('incoming') or apk.suffix!='.apk':raise SystemExit('Caminho de APK invalido')
  raw=apk.read_bytes()
  if hashlib.sha256(raw).hexdigest()!=pending['sha256']:raise SystemExit('Hash do APK pendente incorreta')
  sdk=pathlib.Path(os.environ.get('ANDROID_HOME','/usr/local/lib/android/sdk'))
  signer=sorted(sdk.glob('build-tools/*/apksigner'))[-1]
  signed=subprocess.check_output([str(signer),'verify','--print-certs',str(apk)],text=True)
  pinned=pathlib.Path('certificado-sha256.txt').read_text().strip().lower()
  digests=re.findall(r'certificate SHA-256 digest:\s*([0-9a-fA-F:]+)',signed,re.I)
  if not digests or any(v.replace(':','').lower()!=pinned for v in digests):raise SystemExit('Assinatura pendente incorreta')
  aapt=sorted(sdk.glob('build-tools/*/aapt'))[-1]
  info=subprocess.check_output([str(aapt),'dump','badging',str(apk)],text=True)
  if not re.search(r"package: name='br.com.denny.camera' versionCode='"+str(int(pending['versionCode']))+r"' versionName='"+re.escape(pending['versionName'])+r"'",info):raise SystemExit('Versao pendente incorreta')
  def api(path,method='GET',body=None,binary=False):
   address=path if path.startswith('https://uploads.github.com/repos/SrDanvers/camera15pro-atualizacoes/') else 'https://api.github.com/repos/SrDanvers/camera15pro-atualizacoes/'+path
   payload=body if binary else json.dumps(body).encode() if body is not None else None
   request=urllib.request.Request(address,data=payload,method=method,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/vnd.android.package-archive' if binary else 'application/json','User-Agent':'CameraPublisher'})
   with urllib.request.urlopen(request,timeout=120) as response:return json.load(response)
  try: staged=api('releases/tags/'+pending['tag'])
  except urllib.error.HTTPError as error:
   if error.code!=404:raise
   staged=api('releases','POST',dict(tag_name=pending['tag'],target_commitish='main',name='Camera 15 Pro '+pending['versionName'],body=pending['notes'],draft=True,prerelease=False))
  if staged['draft']:
   if not any(x['name']==pending['filename'] for x in staged['assets']):
    api(staged['upload_url'].split('{')[0]+'?name='+pending['filename'],'POST',raw,True)
   staged=api('releases/'+str(staged['id']),'PATCH',{'draft':False})
  release=api('releases/'+str(staged['id']))

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
