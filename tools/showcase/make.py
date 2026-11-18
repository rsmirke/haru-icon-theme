"""README showcase images: python3 tools/showcase/make.py (writes docs/showcase.jpg, docs/yaru-vs-haru.jpg).
Only Yaru, GNOME and LibreOffice icons: brand logos are never shipped here."""
import random, hicon
from PIL import Image, ImageDraw, ImageFont, ImageFilter
FD='/usr/share/fonts/truetype/ubuntu/'
def background(w,h,seed=7):
    """A neutral graphite backdrop, like an out-of-focus macOS wallpaper: soft grey
    light from the top left, a few blurred lighter and darker shapes, a gentle vignette."""
    random.seed(seed)
    bg=Image.new('RGB',(w,h),(44,44,48))
    d=ImageDraw.Draw(bg)
    cols=[(92,92,98),(70,70,76),(30,30,33),(120,120,126),(56,56,61),(22,22,25)]
    for _ in range(22):
        r=random.randint(w//7,w//3); x=random.randint(-r//2,w); y=random.randint(-r//2,h)
        d.ellipse((x-r,y-r,x+r,y+r),fill=random.choice(cols))
    bg=bg.filter(ImageFilter.GaussianBlur(w/12))
    light=Image.new('L',(w,h),0); ld=ImageDraw.Draw(light)
    ld.ellipse((-w*0.4,-h*0.6,w*0.7,h*0.6),fill=70)
    light=light.filter(ImageFilter.GaussianBlur(w/6))
    bg.paste((210,210,215),(0,0),light)                 # soft light from the top left
    vig=Image.new('L',(w,h),0); vd=ImageDraw.Draw(vig)
    vd.rectangle((0,0,w,h),fill=110); vd.ellipse((-w*0.15,-h*0.2,w*1.15,h*1.2),fill=0)
    bg.paste((8,8,10),(0,0),vig.filter(ImageFilter.GaussianBlur(w/8)))   # darker edges
    noise=Image.effect_noise((w,h),6).convert('L')                     # a touch of grain against banding
    bg=Image.blend(bg,Image.merge('RGB',(noise,noise,noise)),0.03)
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
        dd.rounded_rectangle((dx,dy,dx+dock_w,dy+S+36),radius=30,fill=(255,255,255,26),outline=(255,255,255,40),width=2)   # frosted glass
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
