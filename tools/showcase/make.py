"""README showcase images: python3 tools/showcase/make.py (writes docs/showcase.jpg, docs/yaru-vs-haru.jpg).
Only Yaru, GNOME and LibreOffice icons: brand logos are never shipped here."""
import random, hicon
from PIL import Image, ImageDraw, ImageFont, ImageFilter
FD='/usr/share/fonts/truetype/ubuntu/'
def background(w,h,seed=7):
    random.seed(seed)
    bg=Image.new('RGB',(w,h),(58,40,52))
    d=ImageDraw.Draw(bg)
    # soft warm-to-aubergine blobs, then a heavy blur: an out-of-focus wallpaper
    cols=[(233,84,32),(119,41,83),(44,0,30),(250,160,90),(90,50,110),(30,20,40),(200,110,80),(70,30,60)]
    for _ in range(26):
        r=random.randint(w//8,w//3); x=random.randint(-r//2,w); y=random.randint(-r//2,h)
        d.ellipse((x-r,y-r,x+r,y+r),fill=random.choice(cols))
    bg=bg.filter(ImageFilter.GaussianBlur(w/14))
    shade=Image.new('L',(1,h)); 
    for y in range(h): shade.putpixel((0,y),int(70*y/h))
    bg.paste((0,0,0),(0,0),shade.resize((w,h)))   # a little darker towards the bottom
    return bg.convert('RGBA')

def shadow(img,blur=10,dy=6,alpha=0.35):
    a=img.getchannel('A').point(lambda v:int(v*alpha))
    s=Image.new('RGBA',img.size,(0,0,0,0)); s.putalpha(a)
    pad=blur*3; c=Image.new('RGBA',(img.width+2*pad,img.height+2*pad)); c.alpha_composite(s,(pad,pad+dy))
    return c.filter(ImageFilter.GaussianBlur(blur)),pad

ICONS=['org.gnome.Nautilus','org.gnome.Settings','org.gnome.Ptyxis','org.gnome.TextEditor','org.gnome.Papers','org.gnome.Loupe','org.gnome.Maps','org.gnome.Showtime',
 'org.gnome.Calculator','org.gnome.Calendar','org.gnome.clocks','org.gnome.Weather','org.gnome.Contacts','org.gnome.Snapshot','org.gnome.Music','org.gnome.Characters',
 'org.libreoffice.LibreOffice.startcenter','org.libreoffice.LibreOffice.writer','org.libreoffice.LibreOffice.calc','org.libreoffice.LibreOffice.impress','org.libreoffice.LibreOffice.draw','org.libreoffice.LibreOffice.base','org.libreoffice.LibreOffice.math','org.gnome.font-viewer',
 'org.gnome.Evolution','org.gnome.Builder','org.gnome.DiskUtility','org.gnome.Logs','org.gnome.DejaDup','org.gnome.Yelp','system-software-update','haru-snap-store_snap-store',
 'org.gnome.Totem','org.gnome.Rhythmbox3','org.gnome.SoundRecorder','org.gnome.Shotwell','com.transmissionbt.Transmission','org.gnome.Mahjongg','org.gnome.Mines','org.gnome.Sudoku']
YARU_SRC={'haru-snap-store_snap-store':'app-center','com.transmissionbt.Transmission':'transmission','org.gnome.Evolution':'mail-app'}

def showcase(out,W=2000,H=1560):
    bg=background(W,H)
    d=ImageDraw.Draw(bg)
    t1=ImageFont.truetype(FD+'Ubuntu-B.ttf',150); t2=ImageFont.truetype(FD+'Ubuntu-L.ttf',150)
    a='HARU'; b=' ICON THEME'
    wa=d.textlength(a,font=t1); wb=d.textlength(b,font=t2); x=(W-wa-wb)/2
    d.text((x,110),a,font=t1,fill=(255,255,255)); d.text((x+wa,110),b,font=t2,fill=(255,255,255))
    sub=ImageFont.truetype(FD+'Ubuntu-L.ttf',40)
    d.text((W/2,300),'Yaru, in squircles',font=sub,fill=(255,255,255,220),anchor='mm')
    S=170; G=(W-8*S)/9; y0=400
    for i,k in enumerate(ICONS):
        ic=hicon.haru(k,S+24)   # the plate is 87.5 % of the canvas
        x=int(G+(i%8)*(S+G)-12); y=int(y0+(i//8)*(S+G*0.55)-12)
        sh,p=shadow(ic,blur=9,dy=8,alpha=0.45); bg.alpha_composite(sh,(x-p,y-p)); bg.alpha_composite(ic,(x,y))
    bg.convert('RGB').save(out,quality=92,optimize=True)

BAR=['org.gnome.Nautilus','org.gnome.Ptyxis','org.gnome.TextEditor','org.libreoffice.LibreOffice.writer','org.libreoffice.LibreOffice.calc','org.gnome.Maps','org.gnome.Loupe','org.gnome.Calculator','org.gnome.Settings','haru-snap-store_snap-store']
def bar(out,W=1600):
    S=104; n=len(BAR); H=520
    bg=background(W,H,seed=3)
    d=ImageDraw.Draw(bg)
    lab=ImageFont.truetype(FD+'Ubuntu-M.ttf',44)
    for r,(title,fn) in enumerate([('Yaru',lambda k:hicon.yaru(YARU_SRC.get(k,k),S)),('Haru',lambda k:hicon.haru(k,int(S/0.875)))]):
        y=40+r*240
        d.text((40,y),title,font=lab,fill=(255,255,255))
        dock_w=n*(S+28)+28; dx=(W-dock_w)//2; dy=y+70
        dock=Image.new('RGBA',(W,H)); dd=ImageDraw.Draw(dock)
        dd.rounded_rectangle((dx,dy,dx+dock_w,dy+S+36),radius=30,fill=(30,30,34,150))
        bg.alpha_composite(dock)
        for i,k in enumerate(BAR):
            ic=fn(k)
            cx=dx+28+i*(S+28)+S/2; cy=dy+18+S/2
            bg.alpha_composite(ic,(int(cx-ic.width/2),int(cy-ic.height/2)))
    bg.convert('RGB').save(out,quality=92,optimize=True)

if __name__=='__main__':
    import sys
    from pathlib import Path; docs = Path(__file__).resolve().parents[2] / 'docs'
    showcase(docs / 'showcase.jpg'); bar(docs / 'yaru-vs-haru.jpg')
