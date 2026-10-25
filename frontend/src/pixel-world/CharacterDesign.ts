/** Original modular 32×48 pixel artwork. Parts are composed from a saved recipe,
 * not a small roster of complete sprites. The drawing never controls behavior. */
export interface CharacterAppearance {
  body:number;skin:number;hair:number;hair_style:number;outfit:number;top:number;bottom:number;
  accessory:number;headwear:number;mobility:'walk'|'wheelchair';age:'adult'|'child'|'older'
}
export const CHARACTER_WIDTH=32,CHARACTER_HEIGHT=48,CHARACTER_FOOT=44
export type CharacterMotionStyle='walk'|'run'|'careful'|'brace'
export const SKIN=['#f0c6a2','#dfb18a','#cd956e','#b47c56','#986449','#81503d','#623f34','#49332c']
export const HAIR=['#282a29','#3d2d28','#654432','#906345','#bd9862','#d7c6a0','#8c8983','#5c455f']
export const TOP=['#b74e4b','#5c788b','#e0d4b5','#698377','#b89755','#796783','#3e6570','#b3785a','#6b7258','#d0b6a0','#4c5163','#9c6978']
export const BOTTOM=['#334858','#536375','#746552','#4d5148','#383b43','#8d7c64','#645367','#a99c7b']
const INK='#283334'

function seedHash(id:number,seed:number,salt:number) {
  let n=Math.imul(id+9317+salt*173,374761393)^Math.imul(seed+1777+salt*71,668265263)
  n=Math.imul(n^(n>>>13),1274126177);return(n^(n>>>16))>>>0
}
export function characterAppearance(id:number,seed=42,source?:Partial<CharacterAppearance>):CharacterAppearance {
  const count=(key:keyof CharacterAppearance,n:number,salt:number)=>{
    const value=source?.[key];return typeof value==='number'&&Number.isFinite(value)?Math.abs(Math.trunc(value))%n:seedHash(id,seed,salt)%n
  }
  return {body:count('body',4,1),skin:count('skin',8,2),hair:count('hair',8,3),hair_style:count('hair_style',8,4),
    outfit:count('outfit',6,5),top:count('top',12,6),bottom:count('bottom',8,7),accessory:count('accessory',7,8),
    headwear:count('headwear',5,9),mobility:source?.mobility==='wheelchair'?'wheelchair':'walk',
    age:source?.age==='child'?'child':source?.age==='older'?'older':'adult'}
}
export function appearanceKey(a:CharacterAppearance){return Object.values(a).join(':')}
function tint(hex:string,amount:number){const value=parseInt(hex.slice(1),16);return '#'+[16,8,0].map(s=>Math.max(0,Math.min(255,((value>>s)&255)+amount)).toString(16).padStart(2,'0')).join('')}

/** Integer scanline fills preserve hard pixel clusters, including diagonal edges. */
function polygon(ctx:CanvasRenderingContext2D,points:number[][],color:string) {
  ctx.fillStyle=color
  const top=Math.min(...points.map(p=>p[1])),bottom=Math.max(...points.map(p=>p[1]))
  for(let y=Math.floor(top);y<Math.ceil(bottom);y++) {
    const crossings:number[]=[]
    for(let i=0;i<points.length;i++) {const a=points[i],b=points[(i+1)%points.length],sy=y+.5
      if((a[1]<=sy&&b[1]>sy)||(b[1]<=sy&&a[1]>sy))crossings.push(a[0]+(sy-a[1])*(b[0]-a[0])/(b[1]-a[1]))}
    crossings.sort((a,b)=>a-b)
    for(let i=0;i+1<crossings.length;i+=2){const l=Math.ceil(crossings[i]-.5),r=Math.ceil(crossings[i+1]-.5);ctx.fillRect(l,y,r-l,1)}
  }
}

/** Direction order matches recordings: north, east, south, west. Every part uses
 * the same integer pose landmarks. West is a complete mirrored east profile,
 * not a front-facing head pasted onto independently shifted limbs. */
export function drawCharacter(ctx:CanvasRenderingContext2D,a:CharacterAppearance,direction=2,pose=0,motion:CharacterMotionStyle='walk') {
  ctx.save();ctx.imageSmoothingEnabled=false
  // Atlas isolation also prevents a future accessory from bleeding into its neighbour.
  ctx.beginPath();ctx.rect(0,0,CHARACTER_WIDTH,CHARACTER_HEIGHT);ctx.clip()
  if(direction===3){ctx.translate(CHARACTER_WIDTH,0);ctx.scale(-1,1)}
  const r=(x:number,y:number,w:number,h:number,c:string)=>{if(w<=0||h<=0)return;ctx.fillStyle=c;ctx.fillRect(Math.round(x),Math.round(y),Math.round(w),Math.round(h))}
  const p=(points:number[][],color:string)=>polygon(ctx,points,color)
  const side=direction===1||direction===3,back=direction===0,child=a.age==='child',wheel=a.mobility==='wheelchair'
  const running=motion==='run'&&!wheel,careful=motion==='careful',bracing=motion==='brace'
  const walking=pose>0&&pose<7,step=walking?(running?[0,2,4,0,-2,-4]:careful?[0,1,1,0,-1,-1]:[0,1,2,0,-1,-2])[pose-1]:0,bob=walking&&(pose===2||pose===5)?running?-2:careful?0:-1:0
  const gesture=pose===7&&!back,wide=a.body===1?1:a.body===2?-1:0,tall=a.body===3&&!child?1:0
  const skin=SKIN[a.skin],skinShade=tint(skin,-24),hair=HAIR[a.hair],hairShade=tint(hair,-17),hairLight=tint(hair,17)
  const shirt=TOP[a.top],shirtShade=tint(shirt,-24),shirtLight=tint(shirt,16),pants=BOTTOM[a.bottom],pantsShade=tint(pants,-18)
  const shoe='#37403e',sole='#b9bca7',bag='#847458',bagShade='#625e49'
  const crouch=bracing?3:careful?1:0
  const headY=(child?16:7)-tall+bob+crouch,cx=side?(running?18:17):16,headW=child?5:6
  const shoulder=(child?29:22)-tall+bob+crouch,hip=child?37:34,torsoLeft=side?12:child?11:10-wide,torsoRight=side?22:child?21:22+wide
  const coat=a.outfit===3,hem=hip+(coat&&!child?3:0),shortSleeve=a.outfit===4
  // One quiet contact shadow; no highlight noise around the feet.
  p([[8,43],[12,42],[23,42],[27,44],[23,46],[10,46],[6,44]],'#22382f30')

  const leg=(x:number,shift:number,lift:number,near:boolean)=>{
    const width=child?4:5,foot=44-lift*(running?4:1),toe=side?2:0
    p([[x,hip-2],[x+width,hip-2],[x+width+shift,foot-3],[x+width+shift+toe,foot-2],[x+width+shift+toe,foot],[x+shift-1,foot],[x+shift-1,foot-3]],INK)
    p([[x+1,hip],[x+width-1,hip],[x+width+shift-1,foot-3],[x+shift,foot-3]],near?pants:pantsShade)
    r(x+shift,foot-3,width+toe-1,2,shoe);r(x+shift,foot-1,width+toe-1,1,sole)
  }
  if(!wheel){
    if(side){leg(14,-step,step>0?1:0,false);leg(13,step,step<0?1:0,true)}
    else{leg(child?11:10-wide,step>1?-1:0,step>0?1:0,true);leg(child?17:18+wide,step< -1?1:0,step<0?1:0,false)}
  } else {
    r(10,hip-2,13,5,INK);r(12,hip-1,10,3,pants);r(18,hip+1,5,7,pantsShade);r(18,41,8,3,shoe)
  }

  // Rear hair and bags are deliberately behind the body/face, with no stray pixels.
  if(a.hair_style===4){r(cx-headW-1,headY+5,headW*2+2,shoulder-headY+3,hairShade)}
  if(a.hair_style===3){p([[cx-6,headY+4],[cx-3,headY+5],[cx-4,headY+15],[cx-7,headY+18],[cx-8,headY+13]],hairShade)}
  if(a.accessory===1&&side){r(8,shoulder+2,6,11,INK);r(9,shoulder+3,4,9,bag);r(9,shoulder+7,4,3,bagShade)}
  if(a.accessory===4){r(side?9:23,shoulder+9,5,8,bagShade);r(side?10:24,shoulder+10,3,6,'#b5a27c')}

  const arm=(left:boolean,near:boolean)=>{
    const x=left?torsoLeft-2:torsoRight-1,sy=shoulder+1
    const swing=walking?(left?step:-step):0,handY=shoulder+(child?8:11)+(swing>0?1:swing<0?-1:0)
    if(bracing){
      const handX=left?cx-headW-1:cx+headW-1,handTop=headY+6
      p([[x,sy],[x+3,sy],[handX+3,handTop+2],[handX+3,handTop-1],[handX,handTop-1],[handX-1,handTop+3],[x-1,sy+5]],INK)
      p([[x+1,sy],[x+2,sy],[handX+2,handTop+2],[handX,handTop+2],[x,sy+4]],near?shirt:shirtShade)
      r(handX,handTop,2,3,skin);return
    }
    if(running||careful){
      const elbow=x+(side?Math.round(swing/2):left?-2:2),ey=sy+(child?5:7),hx=elbow+(left?1:2),hy=sy+(careful?5:3)+(swing<0?2:0)
      p([[x,sy],[x+3,sy],[elbow+4,ey],[elbow+2,ey+2],[hx-2,hy+2],[hx-2,hy],[hx+1,hy],[elbow+1,ey-1],[x,sy+3]],INK)
      p([[x+1,sy+1],[x+2,sy+1],[elbow+3,ey],[elbow+1,ey],[x+1,sy+3]],near?shirt:shirtShade)
      p([[elbow+1,ey],[hx-1,hy+1],[hx+1,hy+1],[elbow+2,ey+1]],shortSleeve?skin:shirt)
      r(hx-1,hy,3,3,near?skin:skinShade);return
    }
    if(gesture&&!left){
      p([[x,sy],[x+3,sy],[x+4,sy+4],[x+7,sy+1],[x+9,sy+2],[x+7,sy+6],[x+3,sy+8],[x,sy+6]],INK)
      p([[x+1,sy+1],[x+2,sy+1],[x+4,sy+5],[x+6,sy+4],[x+5,sy+6],[x+2,sy+7],[x+1,sy+5]],shirt)
      r(x+6,sy+2,2,3,skin);return
    }
    const dx=side?Math.round(swing/2):0,sleeveEnd=shortSleeve?sy+4:handY-1
    p([[x,sy],[x+3,sy],[x+4+dx,handY],[x+3+dx,handY+3],[x+dx,handY+3],[x-1+dx,handY]],INK)
    p([[x+1,sy+1],[x+2,sy+1],[x+3+dx,sleeveEnd],[x+dx,sleeveEnd]],near?shirt:shirtShade)
    p([[x+dx,sleeveEnd],[x+3+dx,sleeveEnd],[x+3+dx,handY+2],[x+dx,handY+2]],near?skin:skinShade)
  }
  // The far profile arm is occluded by the torso, rather than drawn through it.
  if(side)arm(true,false)
  p([[torsoLeft+2,shoulder-1],[torsoRight-2,shoulder-1],[torsoRight,shoulder+2],[torsoRight,hem-1],[torsoRight-2,hem],[torsoLeft+1,hem],[torsoLeft,shoulder+2]],INK)
  p([[torsoLeft+2,shoulder],[torsoRight-2,shoulder],[torsoRight-1,shoulder+3],[torsoRight-1,hem-1],[torsoLeft+1,hem-1],[torsoLeft+1,shoulder+3]],shirt)
  r(torsoRight-3,shoulder+4,2,hem-shoulder-5,shirtShade)
  r(torsoLeft+2,shoulder+2,side?3:5,2,shirtLight)
  r(cx-2,shoulder-2,4,3,skinShade)
  if(!back){
    if(a.outfit===0){ // Hoodie: broad collar, one simple pocket.
      r(cx-4,shoulder,side?6:8,2,shirtShade)
      if(!side&&!child){r(cx-3,shoulder+3,1,3,'#ccc5aa');r(cx+2,shoulder+3,1,3,'#ccc5aa');r(cx-3,hip-4,6,2,shirtShade)}
    }else if(a.outfit===1||coat){
      if(!side){r(cx-2,shoulder+1,4,hem-shoulder-3,'#d9d1b5');p([[cx-4,shoulder],[cx-1,shoulder+3],[cx-3,shoulder+5]],shirtShade);p([[cx+4,shoulder],[cx+1,shoulder+3],[cx+3,shoulder+5]],shirtShade)}
      else r(torsoRight-3,shoulder+2,1,hem-shoulder-4,'#d9d1b5')
    }else if(a.outfit===2){r(cx-3,shoulder,6,1,'#d6cdb3');r(torsoLeft+2,hem-2,torsoRight-torsoLeft-3,1,shirtShade)}
    else if(a.outfit===5&&!side){r(cx-4,shoulder+5,3,3,shirtShade);r(cx+2,shoulder+5,3,3,shirtShade)}
  }else if(a.outfit===0){r(cx-4,shoulder,8,4,shirtShade);r(cx-3,shoulder,6,2,shirt)}
  if(!side)arm(true,false)
  arm(false,true)

  // A single stepped head silhouette and two large skin clusters read at map scale.
  // No checkerboard cheek highlights, mouth outline or floating nose fragments.
  const faceBottom=headY+(child?11:13)
  p([[cx-headW+2,headY],[cx+headW-2,headY],[cx+headW,headY+2],[cx+headW,faceBottom-3],[cx+headW-2,faceBottom],[cx-headW+2,faceBottom],[cx-headW,faceBottom-3],[cx-headW,headY+2]],INK)
  p([[cx-headW+2,headY+2],[cx+headW-2,headY+2],[cx+headW-1,headY+4],[cx+headW-1,faceBottom-3],[cx+headW-2,faceBottom-1],[cx-headW+2,faceBottom-1],[cx-headW+1,faceBottom-3],[cx-headW+1,headY+4]],skin)
  r(cx+headW-3,headY+5,2,faceBottom-headY-7,skinShade)
  r(cx-2,faceBottom-2,4,1,skinShade)
  if(side&&!back){r(cx+headW-1,headY+7,2,3,skin);r(cx+3,headY+6,1,2,INK);r(cx-headW,headY+7,2,3,skinShade)}
  else if(!back){r(cx-3,headY+6,1,2,INK);r(cx+3,headY+6,1,2,INK)}

  // Eight cuts use a small number of contiguous clusters. The back is covered
  // fully; profile fringe/ear placement follows the same anatomy as the face.
  const top=headY-2,outerLeft=cx-headW-1,outerRight=cx+headW+1
  p([[outerLeft+2,top],[outerRight-2,top],[outerRight,top+2],[outerRight,headY+4],[cx+1,headY+3],[cx-2,headY+5],[outerLeft,headY+4],[outerLeft,top+2]],hair)
  r(cx-4,top,6,2,hairLight)
  if(back){p([[outerLeft,headY+2],[outerRight,headY+2],[outerRight-1,faceBottom-2],[cx+3,faceBottom],[cx-3,faceBottom],[outerLeft+1,faceBottom-2]],hair);r(outerLeft+1,headY+3,2,5,hairLight)}
  else if(side){r(outerLeft,headY+3,4,6,hair);r(outerLeft+1,headY+4,2,3,hairLight)}
  if(a.hair_style===0){r(cx-4,top-1,5,2,hair);r(cx-2,headY+3,3,2,hair)}
  else if(a.hair_style===1){r(outerLeft,headY+2,3,10,hair);if(!side)r(outerRight-3,headY+2,3,10,hair);r(outerLeft+1,headY+4,1,5,hairLight)}
  else if(a.hair_style===2||a.hair_style===6){
    p([[cx-4,top-2],[cx+3,top-2],[cx+3,top-1],[outerRight,top-1],[outerRight,top+2],[outerRight+1,top+2],[outerRight+1,headY+5],[outerRight-2,headY+5],[outerRight-3,headY+3],[cx-2,headY+4],[outerLeft-1,headY+4],[outerLeft-1,top+1],[outerLeft+2,top+1],[outerLeft+2,top-1],[cx-4,top-1]],hair)
    r(cx-4,top,5,2,hairLight)
    if(a.hair_style===6){r(outerLeft-1,headY+3,3,7,hair);if(back||!side)r(outerRight-2,headY+3,3,7,hair)}
  }else if(a.hair_style===3){r(cx-7,headY+4,3,2,'#b78364')}
  else if(a.hair_style===4){r(outerLeft,headY+2,3,15,hair);if(!side)r(outerRight-3,headY+2,3,15,hair);r(outerLeft+1,headY+4,1,9,hairLight)}
  else if(a.hair_style===5){r(cx-headW+1,headY,headW*2-2,3,hairLight);if(!back)r(cx-headW+2,headY+3,headW*2-4,2,skin)}
  else if(a.hair_style===7){p([[outerLeft,headY],[cx+4,headY],[cx+4,headY+2],[cx-3,headY+5],[outerLeft,headY+4]],hair);r(cx-4,headY,6,1,hairLight)}

  if(a.headwear===1){
    p([[outerLeft,headY+3],[outerLeft,headY],[cx-4,headY-2],[cx+4,headY-2],[outerRight,headY],[outerRight,headY+3]],shirtShade)
    r(cx-4,headY-1,8,3,shirt)
    if(!back)r(side?cx+2:outerLeft,headY+3,side?7:headW*2+2,2,shirtShade)
  }else if(a.headwear===2){
    p([[outerLeft,headY+3],[outerLeft,headY],[cx-4,headY-3],[cx+3,headY-3],[outerRight,headY],[outerRight,headY+3]],shirt)
    r(outerLeft,headY+2,headW*2+2,3,shirtShade);r(cx-4,headY-2,5,2,shirtLight)
  }else if(a.headwear===3){
    p([[outerLeft,headY],[cx-4,headY-3],[cx+4,headY-3],[outerRight,headY],[outerRight,faceBottom],[cx+3,faceBottom+2],[cx-4,faceBottom+2],[outerLeft,faceBottom]],shirtShade)
    r(outerLeft+1,headY+2,2,faceBottom-headY-2,shirt)
    if(!back){p([[cx-3,headY+3],[cx+3,headY+3],[cx+4,headY+5],[cx+4,faceBottom-4],[cx+2,faceBottom-1],[cx-2,faceBottom-1],[cx-4,faceBottom-4],[cx-4,headY+5]],skin);r(side?cx+2:cx-2,headY+6,1,2,INK);if(!side)r(cx+2,headY+6,1,2,INK)}
  }else if(a.headwear===4){
    r(outerLeft,headY-1,headW*2+2,2,'#4a5352');r(outerLeft-1,headY+4,3,5,'#aeb7aa');if(!side)r(outerRight-2,headY+4,3,5,'#aeb7aa')
  }
  if(a.accessory===6&&!back){
    if(side){r(cx+1,headY+5,4,3,'#45514e');r(cx+2,headY+6,2,1,skin)}
    else{r(cx-4,headY+5,3,3,'#45514e');r(cx+2,headY+5,3,3,'#45514e');r(cx-1,headY+6,3,1,'#45514e');r(cx-3,headY+6,1,1,skin);r(cx+3,headY+6,1,1,skin)}
  }
  // The protective hands sit in front of the head, never behind the hair.
  if(bracing){r(cx-headW-1,headY+6,3,4,skinShade);r(cx+headW-2,headY+6,3,4,skin)}
  if(a.accessory===1){
    if(back){r(cx-5,shoulder+2,10,12,INK);r(cx-4,shoulder+3,8,10,bag);r(cx-3,shoulder+8,6,4,bagShade);r(cx-3,shoulder+8,6,1,'#a89972')}
    else if(!side){r(torsoLeft+2,shoulder+2,2,7,bagShade);r(torsoRight-3,shoulder+2,2,7,bagShade)}
  }else if(a.accessory===2){
    for(let i=0;i<8;i++)r(back?11+i:20-i,shoulder+1+i,2,2,bagShade)
    r(9,hip-4,7,7,INK);r(10,hip-3,5,5,bag);r(10,hip-3,5,1,'#a89972')
  }else if(a.accessory===3&&!back){
    const bookX=side?20:13;r(bookX,shoulder+6,side?5:10,7,INK);r(bookX+1,shoulder+7,side?3:8,5,'#a75f4d');r(bookX+1,shoulder+10,side?3:8,1,'#d9cfb0');r(bookX-1,shoulder+9,2,3,skin)
  }else if(a.accessory===5){r(cx-4,shoulder,8,3,'#c1a161');if(!back)r(cx+2,shoulder+3,3,5,'#ad874e')}
  if(wheel){
    // Seated limbs, chair frame and continuous wheel rings share registered anchors.
    r(9,31,16,3,'#697b7b');r(10,31,2,10,'#384b4b');r(23,31,2,10,'#384b4b');r(11,38,14,2,'#a6b2a7')
    const wheelAt=(x:number)=>{p([[x-3,32],[x+2,32],[x+5,35],[x+5,41],[x+2,44],[x-3,44],[x-5,41],[x-5,35]],INK);p([[x-2,34],[x+1,34],[x+3,36],[x+3,40],[x+1,42],[x-2,42],[x-3,40],[x-3,36]],'#9faaa1');r(x-1,35,2,7,'#4c615c');r(x-3,37,6,2,'#4c615c')}
    if(side){wheelAt(17);r(24,42,4,2,INK)}else{wheelAt(7);wheelAt(25)}
  }
  ctx.restore()
}
