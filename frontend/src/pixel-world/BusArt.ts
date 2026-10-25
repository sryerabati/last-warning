/** Original pixel shuttle plates. No logo or borrowed game artwork. */
export function paintBusPlates(canvas:HTMLCanvasElement){
  canvas.width=512;canvas.height=128
  const ctx=canvas.getContext('2d')!;ctx.imageSmoothingEnabled=false
  const r=(x:number,y:number,w:number,h:number,c:string)=>{ctx.fillStyle=c;ctx.fillRect(x,y,w,h)}
  const ink='#293b3c',scarlet='#9f5148',cream='#d9d3b9',glass='#557b81',light='#97b1ad'
  for(let facing=0;facing<4;facing++){
    ctx.save();ctx.translate(facing*128,0)
    if(facing===1||facing===3){
      if(facing===3){ctx.translate(128,0);ctx.scale(-1,1)}
      r(11,80,110,8,'#263f3248');r(24,74,13,15,ink);r(91,74,13,15,ink)
      r(27,78,7,6,'#8c9890');r(94,78,7,6,'#8c9890');r(9,42,110,37,ink);r(14,36,99,7,ink)
      r(12,45,104,30,cream);r(16,39,93,12,cream);r(13,69,102,6,scarlet);r(13,66,102,2,'#adac93')
      r(16,49,80,16,ink)
      for(let x=19;x<93;x+=15){r(x,51,12,12,glass);r(x+1,52,10,3,light);r(x+4,61,6,2,'#314b51')}
      r(100,48,13,18,glass);r(101,49,11,5,light);r(98,65,14,9,ink);r(101,65,4,8,'#77918a');r(107,65,3,8,'#77918a')
      r(17,42,78,2,'#eee7ca');r(39,39,26,4,'#969d8c');r(43,36,18,3,'#c9cbb1')
      r(99,43,14,4,ink);r(102,44,8,2,'#e1c078');r(114,64,3,5,'#eee3b3');r(10,65,3,5,'#c86c50')
      r(12,76,105,2,'#7c8e82')
    }else{
      if(facing===0){ctx.translate(128,128);ctx.rotate(Math.PI)}
      r(47,13,38,107,'#263f3248');r(43,27,5,15,ink);r(80,27,5,15,ink);r(43,86,5,15,ink);r(80,86,5,15,ink)
      r(47,10,33,106,ink);r(50,7,27,112,ink);r(49,13,29,100,cream);r(51,10,25,106,cream)
      r(49,25,29,74,scarlet);r(52,25,23,74,cream);r(53,28,21,15,'#b1b7a0');r(56,31,15,9,'#8e9c8e')
      r(52,48,23,33,'#c7ccb2');r(55,55,17,18,'#a1ad9e');r(56,57,15,3,'#d5d6b9')
      r(50,88,27,16,ink);r(52,90,23,11,glass);r(53,91,21,3,light)
      r(52,15,23,9,glass);r(54,16,19,3,light);r(53,105,21,4,ink);r(57,106,13,2,'#e0c282')
      r(50,111,6,4,'#f0e4b8');r(71,111,6,4,'#f0e4b8');r(50,12,5,3,'#b96852');r(72,12,5,3,'#b96852');r(54,117,19,2,'#819489')
    }
    ctx.restore()
  }
}
