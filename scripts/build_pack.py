#!/usr/bin/env python3
"""Overlay this fork's artwork on the pinned, public Appstract dashboard APK."""
import argparse, hashlib, os, pathlib, re, shutil, subprocess, tempfile
import urllib.request, xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE_URL = 'https://github.com/yangchoo/Appstract/releases/download/v5.0.6/Appstract-v5.0.6.apk'
BASE_SHA256 = 'dfdae011e8057f3473818beb1d79f001766ca101b7aaab548083f1f880840541'
PACKAGE = 'dev.appstract.pixel9'
VERSION = '5.0.6-pixel9.2'
VERSION_CODE = 9
ANDROID = '{http://schemas.android.com/apk/res/android}'

def checked_download(url, dest, expected):
    if not dest.exists():
        print('Downloading:', url, flush=True)
        urllib.request.urlretrieve(url, dest)
    if hashlib.sha256(dest.read_bytes()).hexdigest() != expected:
        raise RuntimeError(f'Checksum mismatch: {dest}')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-apk', type=pathlib.Path, help='Pinned Appstract 5.0.6 APK; downloaded if omitted')
    parser.add_argument('--keystore', type=pathlib.Path, help='Sign with your own Android keystore')
    parser.add_argument('--ks-alias', default='pixel9')
    parser.add_argument('--signer-jar', type=pathlib.Path, help='uber-apk-signer 1.3.0 JAR')
    parser.add_argument('--java', default='java')
    parser.add_argument('--output', type=pathlib.Path, default=ROOT/'output/Appstract-Pixel9.apk')
    args = parser.parse_args()
    if args.keystore and not args.signer_jar:
        parser.error('--keystore requires --signer-jar')
    password = os.environ.get('APPSTRACT_KEYSTORE_PASSWORD')
    if args.keystore and not password:
        parser.error('Set APPSTRACT_KEYSTORE_PASSWORD to sign the APK')
    build = ROOT/'build'; build.mkdir(exist_ok=True)
    base_apk = args.base_apk or build/'Appstract-v5.0.6.apk'
    if args.base_apk:
        if hashlib.sha256(base_apk.read_bytes()).hexdigest() != BASE_SHA256:
            raise RuntimeError('Expected the pinned public Appstract 5.0.6 APK')
    else:
        checked_download(BASE_URL, base_apk, BASE_SHA256)
    if not shutil.which('apktool'):
        raise RuntimeError('Install Apktool 3.0.3 and put it on PATH')
    ET.register_namespace('android', ANDROID[1:-1])
    with tempfile.TemporaryDirectory(dir=build) as temporary:
        work = pathlib.Path(temporary)/'pack'
        subprocess.run(['apktool','d','-f',str(base_apk),'-o',str(work)],check=True)
        for source,qualifier in [('appstract-light','drawable-nodpi'),('appstract-dark','drawable-night-nodpi')]:
            dest = work/'res'/qualifier; dest.mkdir(exist_ok=True)
            for image in (ROOT/'icons'/source).glob('*.png'): shutil.copy2(image,dest/image.name)
        for name in ['appfilter.xml','drawable.xml']:
            for dest in ['assets','res/xml']:shutil.copy2(ROOT/'app/xml'/name,work/dest/name)
        tree = ET.parse(work/'AndroidManifest.xml');tree.getroot().set('package',PACKAGE)
        for node in tree.getroot().iter():
            for key,value in list(node.attrib.items()):
                if key==ANDROID+'authorities' or (node.tag in ['permission','uses-permission'] and key==ANDROID+'name'):
                    node.set(key,value.replace('dev.appstract.iconpack',PACKAGE))
        tree.write(work/'AndroidManifest.xml',encoding='utf-8',xml_declaration=True)
        tree=ET.parse(work/'res/values/strings.xml')
        for node in tree.getroot():
            if node.get('name')=='app_name':node.text='Appstract Pixel 9'
        tree.write(work/'res/values/strings.xml',encoding='utf-8',xml_declaration=True)
        config=work/'apktool.yml'
        content=re.sub(r'versionCode: .*',f'versionCode: {VERSION_CODE}',config.read_text())
        content=re.sub(r'versionName: .*',f'versionName: {VERSION}',content);config.write_text(content)
        for source,dest in [('LICENSE.md','APPSTRACT-LICENSE.txt'),('NOTICE.md','PIXEL9-NOTICE.txt')]:
            shutil.copy2(ROOT/source,work/'assets'/dest)
        names={p.stem for d in (work/'res').glob('drawable*') for p in d.iterdir() if p.is_file()}
        bindings=ET.parse(work/'assets/appfilter.xml').getroot()
        for node in bindings:
            if node.tag=='item' and node.get('drawable') not in names:
                raise RuntimeError(f'Missing drawable: {node.attrib}')
            if node.tag=='calendar':
                for day in range(1,32):
                    if node.get('prefix')+str(day) not in names:raise RuntimeError(f'Missing date: {day}')
        unsigned=pathlib.Path(temporary)/'unsigned.apk'
        subprocess.run(['apktool','b',str(work),'-o',str(unsigned)],check=True)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        if args.keystore:
            signed=pathlib.Path(temporary)/'signed'
            subprocess.run([args.java,'-jar',str(args.signer_jar),'--apks',str(unsigned),'--out',str(signed),
                '--ks',str(args.keystore),'--ksAlias',args.ks_alias,'--ksPass',password,'--ksKeyPass',password],check=True)
            shutil.copy2(next(signed.glob('*.apk')),args.output)
        else:
            args.output=args.output.with_name(args.output.stem+'-unsigned.apk')
            shutil.copy2(unsigned,args.output)
        print('Built:',args.output)

if __name__=='__main__':main()
