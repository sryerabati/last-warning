"""Editable original pixel artwork for Last Warning. No third-party assets.

Run with Python + Pillow. Integer drawing coordinates, no antialiasing.
"""
from pathlib import Path
from PIL import Image, ImageDraw
import json
import random

ROOT = Path(__file__).parent
RUNTIME = ROOT.parents[1] / 'public' / 'assets' / 'art' / 'last-warning'
RUNTIME.mkdir(parents=True, exist_ok=True)
P = dict(ink='#273d40', shade='#3f5651', grass='#809862', light='#96ab73', deep='#637f53',
         sand='#b9b18a', stone='#bdc4ae', white='#e8dfbb', cream='#d7ca9b', wall='#c6b185',
         brick='#ad7154', red='#a05b49', tile='#c67f57', blue='#507b85', slate='#42616e',
         water='#4c8f9e', aqua='#71adb1', foam='#b1cec0', road='#636f6c', pavement='#929b87',
         gold='#dcbd70', darkgreen='#3c624d', green='#577b51', bright='#779c58', trunk='#705b40')
frames = {}
atlas = Image.new('RGBA', (1024, 1024))
cursor = [2, 2, 0]

def publish(name, image):
    w, h = image.size
    if cursor[0] + w + 2 > 1024:
        cursor[0] = 2
        cursor[1] += cursor[2] + 4
        cursor[2] = 0
    x, y = cursor[:2]
    atlas.alpha_composite(image, (x, y))
    frames[name] = dict(x=x, y=y, w=w, h=h)
    cursor[0] += w + 4
    cursor[2] = max(cursor[2], h)

def canvas(w, h):
    im = Image.new('RGBA', (w, h)); return im, ImageDraw.Draw(im)

def tile(kind, variant=0):
    im, d = canvas(16, 16)
    rng = random.Random(variant + 810)
    if kind == 'grass':
        d.rectangle((0, 0, 15, 15), fill=P['grass'])
        for _ in range(7):
            x, y = rng.randrange(16), rng.randrange(16)
            d.line((x, y, min(15,x+1), y), fill=P['light' if rng.random()>.5 else 'deep'])
    elif kind == 'stone':
        d.rectangle((0, 0, 15, 15), fill=P['stone'])
        for y in (0, 8):
            d.line((0,y,15,y), fill=P['pavement'])
            for x in range((y//8)*4,16,8):d.line((x,y,x,min(15,y+7)),fill=P['pavement'])
        d.point((3,4), fill=P['white']);d.point((12,12),fill=P['white'])
    elif kind == 'water':
        d.rectangle((0,0,15,15),fill=P['water'])
        d.line((2,4+variant%3,7,4+variant%3),fill=P['aqua'])
        d.line((10,11,15,11),fill=P['blue'])
        d.point((8,5+variant%3),fill=P['foam'])
    elif kind == 'soil':
        d.rectangle((0,0,15,15),fill=P['sand'])
        for _ in range(14):d.point((rng.randrange(16),rng.randrange(16)),fill=P['cream'])
    publish(f'{kind}{variant}',im)

for k in ('grass','water','stone','soil'):
    for v in range(4):tile(k,v)

def windows(d,x,y,w=8,h=9):
    d.rectangle((x-1,y-1,x+w,y+h),fill=P['shade'])
    d.rectangle((x,y,x+w-1,y+h-1),fill=P['blue'])
    d.line((x,y,x+w-1,y),fill=P['aqua'])
    d.line((x+w//2,y,x+w//2,y+h-1),fill=P['cream'])
    d.line((x,y+h,x+w,y+h),fill=P['white'])

def building(name, roof, kind='home', variant=0):
    im,d=canvas(112,112);r=random.Random(variant+92)
    # Stepped silhouette, dark foundation and projected southeast shadow.
    x,y,w,h=(15,30,76,61) if kind=='home' else (7,22,94,74)
    if kind=='cottage':x,y,w,h=22,42,64,48
    d.rectangle((x+8,y+11,x+w+8,y+h+8),fill='#354d3e66')
    d.rectangle((x-2,y+7,x+w+2,y+h+2),fill=P['ink'])
    d.rectangle((x,y+8,x+w-1,y+h),fill=P['wall'])
    d.rectangle((x+w-10,y+8,x+w-1,y+h),fill=P['brick'])
    d.line((x,y+h,x+w,y+h),fill=P['shade'],width=3)
    for yy in range(y+15,y+h-3,6):
        d.line((x+1,yy,x+w-11,yy),fill='#b4a078')
    # Roof perspective remains orthographic; raised top edge creates depth.
    ry=y-15;rh=45 if kind!='cottage' else 34
    d.polygon([(x-4,ry+12),(x+7,ry),(x+w-7,ry),(x+w+4,ry+12),(x+w+4,ry+rh),(x-4,ry+rh)],fill=P['ink'])
    d.polygon([(x-2,ry+12),(x+8,ry+2),(x+w-8,ry+2),(x+w+2,ry+12),(x+w+2,ry+rh-2),(x-2,ry+rh-2)],fill=roof)
    for yy in range(ry+6,ry+rh-3,5):
        d.line((x+1,yy,x+w,yy),fill=P['tile'] if roof==P['red'] else P['blue'] if roof==P['slate'] else P['light'])
        for xx in range(x+5+(yy%2)*5,x+w,12):d.line((xx,yy,xx,yy+2),fill='#273d4038')
    d.line((x+8,ry+2,x+w-8,ry+2),fill=P['cream'],width=2)
    d.line((x-2,ry+rh-2,x+w+2,ry+rh-2),fill=P['shade'],width=3)
    # Chimney, dormer, shaded eaves.
    d.rectangle((x+w-23,ry-4,x+w-13,ry+13),fill=P['brick'])
    d.rectangle((x+w-25,ry-5,x+w-11,ry-2),fill=P['ink'])
    d.rectangle((x+w-22,ry-3,x+w-15,ry+2),fill=P['cream'])
    wy=ry+rh+5
    for wx in range(x+7,x+w-13,19):windows(d,wx,wy,8,9)
    doorx=x+w//2-5
    d.rectangle((doorx-2,y+h-19,doorx+12,y+h),fill=P['cream'])
    d.rectangle((doorx,y+h-18,doorx+9,y+h),fill=P['slate'])
    d.rectangle((doorx+2,y+h-16,doorx+7,y+h-10),fill=P['aqua'])
    d.point((doorx+8,y+h-7),fill=P['gold'])
    d.rectangle((doorx-4,y+h+1,doorx+14,y+h+5),fill=P['stone'])
    if kind=='shop':
        d.rectangle((x+4,y+h-32,x+w-14,y+h-21),fill=P['ink'])
        for xx in range(x+4,x+w-14,8):d.rectangle((xx,y+h-32,xx+5,y+h-21),fill=P['white'] if (xx//8)%2 else P['red'])
        windows(d,x+7,y+h-19,19,14);windows(d,x+w-35,y+h-19,19,14)
    if kind=='civic':
        d.rectangle((x+33,ry-8,x+57,ry+14),fill=P['wall'])
        d.rectangle((x+31,ry-12,x+59,ry-7),fill=P['ink'])
        d.rectangle((x+34,ry-11,x+56,ry-8),fill=P['slate'])
        d.rectangle((x+40,ry-4,x+50,ry+6),fill=P['cream'])
        d.line((x+45,ry-2,x+45,ry+2),fill=P['ink']);d.line((x+45,ry+2,x+48,ry+2),fill=P['ink'])
        d.rectangle((x+9,y+h-9,x+25,y+h+4),fill=P['stone']);d.rectangle((x+w-37,y+h-9,x+w-21,y+h+4),fill=P['stone'])
    if kind=='warehouse':
        d.rectangle((x+9,y+h-23,x+41,y+h),fill=P['shade'])
        for yy in range(y+h-21,y+h,4):d.line((x+11,yy,x+39,yy),fill=P['pavement'])
        for xx in (x+52,x+68):windows(d,xx,y+h-21,9,11)
    # Flowerboxes and side gardens provide a ground anchor.
    for xx in (x+1,x+w-13):
        d.rectangle((xx,y+h-3,xx+10,y+h+2),fill=P['trunk'])
        for a in range(5):d.rectangle((xx+a*2,y+h-6-r.randrange(3),xx+a*2+1,y+h-3),fill=P['bright'])
        d.point((xx+3,y+h-7),fill=P['gold']);d.point((xx+7,y+h-6),fill=P['tile'])
    publish(name,im)

for v,roof in enumerate((P['red'],P['slate'],P['green'],P['tile'])):
    building(f'house{v}',roof,'home',v)
    building(f'cottage{v}',roof,'cottage',v)
building('shop0',P['slate'],'shop');building('shop1',P['red'],'shop',1)
building('civic',P['slate'],'civic');building('warehouse',P['slate'],'warehouse')

def tree(name,kind):
    im,d=canvas(40,56)
    for box in ((14,40,33,42),(10,43,37,46),(14,47,33,49)):
        d.rectangle(box,fill='#273d404f')
    d.rectangle((18,27,22,48),fill=P['trunk']);d.line((18,30,18,45),fill=P['cream'])
    if kind=='pine':
        for x0,y0,x1,y1 in ((9,29,32,40),(6,20,34,34),(10,12,30,26),(14,3,26,18)):
            d.polygon([(20,y0),(x1,y1),(x0,y1)],fill=P['darkgreen'])
            d.polygon([(20,y0+2),(x0+3,y1-2),(20,y1-2)],fill=P['green'])
            d.line((x0+4,y1-2,19,y1-2),fill=P['bright'])
    else:
        # Designed, interlocking leaf masses: asymmetric stepped silhouettes,
        # broad shade planes, and a few highlights rather than stacked circles.
        d.polygon([(12,4),(25,4),(25,7),(31,7),(31,12),(35,12),(35,24),(37,24),(37,31),(33,31),(33,37),(26,37),(26,40),(13,40),(13,37),(7,37),(7,32),(3,32),(3,20),(1,20),(1,13),(6,13),(6,8),(12,8)],fill=P['darkgreen'])
        d.polygon([(12,4),(25,4),(25,7),(31,7),(31,13),(33,13),(33,22),(29,22),(29,28),(22,28),(22,32),(10,32),(10,28),(5,28),(5,21),(3,21),(3,14),(7,14),(7,9),(12,9)],fill=P['green'])
        d.polygon([(12,7),(22,7),(22,10),(25,10),(25,15),(20,15),(20,20),(10,20),(10,23),(6,23),(6,14),(9,14),(9,10),(12,10)],fill=P['bright'])
        d.rectangle((12,8,19,10),fill=P['light']);d.rectangle((8,13,11,15),fill=P['light'])
        d.rectangle((25,25,31,28),fill=P['green']);d.rectangle((23,29,28,31),fill=P['bright'])
        if name=='oak1':
            d.rectangle((1,13,5,17),fill=(0,0,0,0));d.rectangle((10,2,19,6),fill=P['green'])
            d.rectangle((22,7,27,11),fill=P['bright']);d.rectangle((5,24,8,29),fill=P['darkgreen'])
        elif name=='oak2':
            d.rectangle((31,8,35,15),fill=P['green']);d.rectangle((8,4,13,9),fill=P['bright'])
            d.rectangle((8,29,16,34),fill=P['green']);d.rectangle((16,30,19,32),fill=P['bright'])
    publish(name,im)
tree('oak','oak');tree('pine','pine')
tree('oak1','oak');tree('oak2','oak')

for name in ('bench','lamp','flowers','bush','car0','car1','fountain','shelter','barrier','boat'):
    im,d=canvas(48,48)
    if name=='bench':
        d.rectangle((8,22,38,27),fill=P['trunk']);d.line((8,21,38,21),fill=P['gold'],width=2)
        d.rectangle((10,29,36,32),fill=P['wall']);d.line((12,25,12,37),fill=P['ink'],width=2);d.line((34,25,34,37),fill=P['ink'],width=2)
    elif name=='lamp':
        d.rectangle((22,13,24,43),fill=P['ink']);d.rectangle((18,42,28,45),fill=P['shade'])
        d.rectangle((18,5,28,15),fill=P['ink']);d.rectangle((20,7,26,13),fill=P['gold']);d.rectangle((17,4,29,6),fill=P['slate'])
    elif name=='flowers':
        d.rectangle((7,25,40,35),fill=P['trunk']);d.rectangle((8,24,39,29),fill=P['green'])
        for x,y in ((12,20),(18,23),(25,19),(32,23),(36,20)):
            d.line((x,y,x,28),fill=P['deep']);d.rectangle((x-1,y-1,x+1,y+1),fill=P['gold'] if x%2 else P['tile'])
    elif name=='bush':
        d.polygon([(12,20),(24,20),(24,18),(34,18),(34,22),(40,22),(40,26),(43,26),(43,35),(37,35),(37,39),(12,39),(12,36),(5,36),(5,27),(9,27),(9,23),(12,23)],fill=P['darkgreen'])
        d.polygon([(12,21),(24,21),(24,19),(33,19),(33,23),(38,23),(38,29),(34,29),(34,33),(10,33),(10,28),(8,28),(8,25),(12,25)],fill=P['green'])
        d.rectangle((13,23,20,25),fill=P['bright']);d.rectangle((23,21,30,23),fill=P['bright'])
    elif name.startswith('car'):
        c=P['red'] if name=='car0' else P['cream']
        d.rectangle((12,14,36,41),fill='#273d404f');d.rectangle((11,8,33,39),fill=P['ink']);d.rectangle((13,7,31,39),fill=c)
        d.rectangle((15,16,29,30),fill=P['slate']);d.rectangle((16,17,28,20),fill=P['aqua']);d.rectangle((15,33,29,36),fill=P['white'])
        d.rectangle((12,11,15,14),fill=P['gold']);d.rectangle((29,11,32,14),fill=P['gold'])
    elif name=='fountain':
        d.ellipse((3,14,45,42),fill=P['shade']);d.ellipse((3,10,45,38),fill=P['stone']);d.ellipse((8,14,40,32),fill=P['water']);d.ellipse((13,18,35,29),outline=P['foam'],width=2)
        d.rectangle((21,9,27,25),fill=P['white']);d.ellipse((16,6,32,15),fill=P['stone']);d.line((24,4,24,11),fill=P['aqua'],width=2)
    elif name=='shelter':
        d.rectangle((3,3,44,44),fill=P['ink']);d.rectangle((5,5,42,42),fill=P['cream']);d.rectangle((8,8,39,39),fill=P['darkgreen'])
        d.rectangle((20,13,27,34),fill=P['white']);d.rectangle((13,20,34,27),fill=P['white'])
    elif name=='barrier':
        d.rectangle((5,20,43,30),fill=P['ink']);d.rectangle((6,21,42,28),fill=P['gold'])
        for x in range(8,40,10):d.polygon([(x,21),(x+5,21),(x+1,28),(x-4,28)],fill=P['red'])
        d.rectangle((9,30,12,39),fill=P['ink']);d.rectangle((36,30,39,39),fill=P['ink'])
    elif name=='boat':
        d.polygon([(11,7),(26,3),(37,12),(36,38),(24,44),(11,37)],fill=P['ink']);d.polygon([(14,9),(25,6),(33,14),(32,35),(24,40),(14,34)],fill=P['wall'])
        d.rectangle((17,15,30,31),fill=P['cream']);d.line((24,11,24,32),fill=P['trunk']);d.line((17,31,30,31),fill=P['trunk'],width=2)
    publish(name,im)

# Residents: 12 persistent appearances, four facings and four poses, 12×20 pixels.
clothes=[P['slate'],P['red'],P['cream'],P['gold'],P['green'],P['blue']]
skins=['#d5a67c','#aa7859','#e1bd91','#805a46']
for variant in range(12):
    for direction in range(4):
        for pose in range(4):
            im,d=canvas(12,20);skin=skins[variant%4];shirt=clothes[variant%6]
            step=1 if pose==1 else -1 if pose==3 else 0
            d.ellipse((2,17,10,19),fill='#273d405f')
            d.rectangle((4,13,5,17+step),fill=P['ink']);d.rectangle((7,13,8,17-step),fill=P['shade'])
            d.rectangle((3,8,8,13),fill=shirt);d.line((3,8,7,8),fill=P['white'])
            d.rectangle((2,9,2,12+step),fill=skin);d.rectangle((9,9,9,12-step),fill=skin)
            d.rectangle((4,3,8,7),fill=skin);d.rectangle((3,2,8,4),fill=P['trunk'] if variant%3 else P['ink'])
            if direction==0:d.rectangle((4,5,8,6),fill=P['trunk'])
            elif direction==1:d.point((8,5),fill=P['ink']);d.point((9,6),fill=skin)
            elif direction==2:d.point((5,5),fill=P['ink']);d.point((8,5),fill=P['ink'])
            else:d.point((4,5),fill=P['ink']);d.point((3,6),fill=skin)
            if variant>7:d.rectangle((3,1,8,3),fill=P['gold']);d.line((2,3,9,3),fill=P['gold'])
            publish(f'person-{variant}-{direction}-{pose}',im)

for phase in range(4):
    im,d=canvas(32,48)
    d.polygon([(4,44),(1,31),(8,33),(6,17),(13,23),(16,2+phase*2),(21,21),(26,13),(27,29),(31,36),(26,45)],fill=P['red'])
    d.polygon([(8,44),(6,33),(14,34),(15,17+phase),(21,27),(24,24),(26,38),(22,45)],fill=P['tile'])
    d.polygon([(12,44),(11,36),(16,29+phase),(23,39),(20,45)],fill=P['gold'])
    d.rectangle((15,39,19,45),fill=P['white']);publish(f'fire{phase}',im)

def landmark(name,kind):
    im,d=canvas(192,160)
    # A distinct multi-wing silhouette with tiled roofing, raised central volume,
    # masonry, recessed doors and projected shadows, all at the same pixel scale.
    d.rectangle((17,45,182,146),fill='#273d4055')
    d.rectangle((9,49,173,133),fill=P['ink'])
    d.rectangle((11,51,170,129),fill=P['wall'])
    d.rectangle((161,51,170,129),fill=P['brick'])
    for yy in range(55,128,7):d.line((12,yy,160,yy),fill='#b3a17c')
    roof=P['slate'] if kind!='market' else P['red']
    d.polygon([(5,49),(20,24),(156,24),(178,49),(178,74),(5,74)],fill=P['ink'])
    d.polygon([(8,48),(22,27),(155,27),(174,48),(174,70),(8,70)],fill=roof)
    for yy in range(31,69,5):
        d.line((13 if yy>43 else 22,yy,166 if yy>43 else 156,yy),fill=P['blue'] if kind!='market' else P['tile'])
        for xx in range(22+(yy%2)*5,164,13):d.line((xx,yy,xx,yy+2),fill='#273d4044')
    d.line((22,26,155,26),fill=P['cream'],width=2)
    for xx in (20,43,66,111,134):windows(d,xx,82,12,16)
    d.rectangle((79,101,105,131),fill=P['cream']);d.rectangle((83,104,101,131),fill=P['slate'])
    d.line((92,104,92,130),fill=P['ink']);d.rectangle((84,106,90,115),fill=P['aqua']);d.rectangle((94,106,100,115),fill=P['aqua'])
    for yy,w in ((133,34),(137,42),(141,50)):d.rectangle((92-w//2,yy,92+w//2,yy+3),fill=P['stone'])
    if kind=='hall':
        d.rectangle((71,12,111,76),fill=P['ink']);d.rectangle((74,15,108,74),fill=P['wall'])
        d.polygon([(67,16),(91,2),(115,16)],fill=P['slate']);d.line((68,17,113,17),fill=P['cream'],width=2)
        d.rectangle((81,26,101,46),fill=P['shade']);d.rectangle((83,28,99,44),fill=P['cream'])
        d.line((91,30,91,37,96,37),fill=P['ink'],width=2)
        for xx in (77,91,104):d.rectangle((xx,55,xx+2,66),fill=P['shade'])
        for xx in (16,53,124,159):d.rectangle((xx,104,xx+9,132),fill=P['cream'])
    elif kind=='school':
        d.rectangle((73,14,111,75),fill=P['ink']);d.rectangle((76,16,108,72),fill=P['wall'])
        d.rectangle((73,11,111,17),fill=P['slate']);windows(d,83,27,17,22)
        d.rectangle((78,59,106,66),fill=P['cream'])
        for xx in (81,87,93,99):d.rectangle((xx,61,xx+2,63),fill=P['slate'])
        d.line((173,46,173,138),fill=P['ink'],width=2);d.rectangle((175,47,189,56),fill=P['tile']);d.rectangle((175,47,178,56),fill=P['gold'])
    else:
        # Repeating striped awning and real storefront glass in the market hall.
        d.rectangle((13,99,164,111),fill=P['ink'])
        for xx in range(15,163,10):d.rectangle((xx,99,xx+7,110),fill=P['cream'] if (xx//10)%2 else P['tile'])
        for xx in (20,46,118,144):windows(d,xx,113,15,13)
        d.rectangle((74,81,110,91),fill=P['cream']);d.rectangle((79,84,105,87),fill=P['red'])
    for xx in (18,147):
        d.rectangle((xx,133,xx+19,140),fill=P['trunk'])
        d.rectangle((xx+1,130,xx+18,135),fill=P['green'])
        for xx2 in range(xx+3,xx+18,5):d.rectangle((xx2,128,xx2+1,130),fill=P['gold'])
    publish(name,im)

landmark('school','school');landmark('townhall','hall');landmark('market','market')

im,d=canvas(48,48)
d.rectangle((4,19,44,43),fill=P['trunk']);d.rectangle((5,29,42,40),fill=P['wall'])
for x in range(3,45,7):d.rectangle((x,13,x+5,24),fill=P['cream'] if x%2 else P['tile'])
d.line((3,12,45,12),fill=P['ink']);d.rectangle((5,25,42,29),fill=P['green'])
for x in range(7,41,6):d.rectangle((x,25,x+3,27),fill=P['gold'] if x%2 else P['tile'])
publish('stall',im)

# Organic-town additions. Existing frames and resident palettes remain unchanged.
im,d=canvas(112,112)
d.rectangle((16,37,106,103),fill='#273d4055')
d.rectangle((9,40,97,96),fill=P['ink']);d.rectangle((12,41,94,93),fill=P['red'])
for x in range(16,94,7):d.line((x,42,x,92),fill=P['tile'])
d.polygon([(4,43),(25,13),(80,13),(104,43),(104,50),(4,50)],fill=P['ink'])
d.polygon([(8,42),(27,16),(79,16),(100,42),(100,46),(8,46)],fill=P['slate'])
for y in range(22,44,5):d.line((22,y,87,y),fill=P['blue'])
d.line((27,15,79,15),fill=P['cream'],width=2)
d.rectangle((33,59,74,95),fill=P['ink']);d.rectangle((36,61,71,94),fill=P['trunk'])
d.line((37,62,69,92),fill=P['cream'],width=3);d.line((69,62,37,92),fill=P['cream'],width=3)
d.line((53,61,53,93),fill=P['ink'],width=2);windows(d,17,58,9,12);windows(d,80,58,9,12)
for x in (8,84):
    d.rectangle((x,91,x+20,102),fill=P['gold']);d.line((x+3,92,x+3,101),fill=P['trunk']);d.line((x+16,92,x+16,101),fill=P['trunk'])
publish('barn',im)

im,d=canvas(128,112)
d.rectangle((14,35,122,105),fill='#273d4055')
d.rectangle((6,40,114,96),fill=P['ink']);d.rectangle((9,42,111,93),fill=P['brick'])
for y in range(46,92,6):d.line((10,y,110,y),fill=P['wall'])
d.polygon([(2,41),(18,17),(96,17),(120,41),(120,56),(2,56)],fill=P['ink'])
d.polygon([(6,40),(20,20),(95,20),(116,40),(116,52),(6,52)],fill=P['green'])
for y in range(25,51,5):d.line((13,y,108,y),fill=P['bright'])
d.rectangle((95,10,103,34),fill=P['brick']);d.rectangle((93,9,105,12),fill=P['shade'])
d.rectangle((14,64,54,94),fill=P['shade'])
for y in range(66,94,4):d.line((16,y,52,y),fill=P['pavement'])
for x in (65,86):windows(d,x,64,12,16)
d.rectangle((63,85,101,91),fill=P['trunk']);d.rectangle((66,83,77,85),fill=P['wall']);d.rectangle((83,81,96,85),fill=P['cream'])
d.rectangle((8,96,116,100),fill=P['stone']);publish('workshop',im)

im,d=canvas(56,80)
d.ellipse((11,58,53,75),fill='#273d4055')
d.rectangle((25,31,30,69),fill=P['trunk']);d.line((25,35,25,65),fill=P['cream'],width=2)
d.line((27,43,14,30),fill=P['trunk'],width=3);d.line((28,39,41,25),fill=P['trunk'],width=3)
for box,c in [((4,17,49,54),'darkgreen'),((2,10,44,44),'green'),((12,4,49,36),'green'),((10,10,34,29),'bright')]:d.ellipse(box,fill=P[c])
for x,y,h in ((5,25,34),(11,31,32),(18,34,26),(37,28,35),(44,22,36),(49,30,26)):
    d.rectangle((x,y,x+3,y+h),fill=P['green']);d.rectangle((x,y+2,x+1,y+h-4),fill=P['bright'])
d.line((15,13,23,10,32,10),fill=P['light'],width=2);publish('willow',im)

atlas.save(RUNTIME/'town-atlas.png',optimize=True)
(RUNTIME/'town-atlas.json').write_text(json.dumps(dict(revision=3,image='town-atlas.png',frames=frames,palette=P),indent=2)+'\n')
(ROOT/'README.md').write_text('''# Last Warning original art · revision 3\n\nAll 245 sprites and tiles were authored specifically for Last Warning. No external asset packs, copied game sprites, paid assets, or generated model images are included. `generate_atlas.py` is the editable source; it draws at integer coordinates without antialiasing. Runtime atlas, palette and frame metadata are emitted to `frontend/public/assets/art/last-warning/town-atlas.{png,json}` so the existing production `/assets` mount serves them. Revision 3 adds stepped oak crown variants and refines foliage silhouettes and contact shadows. Resident palettes and fixed sprite foot anchors stay unchanged.\n\nTerrain tiles are 16×16 pixels. The city maps four art tiles to each logic-cell edge (64 source pixels per logic unit). Buildings and props use fixed foot anchors in the renderer. Resident appearances are stable per ID and recorded art seed; direction and gait do not change their appearance. Art is presentation only and adds no simulation mechanics.\n\nRegenerate with Python 3 and Pillow: `python generate_atlas.py`. The runtime needs only the PNG and JSON.\n''')
print(f'{len(frames)} frames, occupied height {cursor[1]+cursor[2]}, atlas {atlas.size}')
