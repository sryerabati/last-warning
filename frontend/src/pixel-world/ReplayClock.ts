/** One visual clock per canvas, shared by both comparison roots. No wall-clock simulation. */
export class ReplayClock {
  private sampledAt=performance.now()
  private tick=-1
  private progress=1
  private duration=220
  private animationSeconds=0
  playing=false
  private quiet=matchMedia('(prefers-reduced-motion: reduce)').matches
  get reduced() {return this.quiet}
  set reduced(value:boolean) {this.sample();this.quiet=value;this.sampledAt=performance.now()}
  private sample() {
    const now=performance.now()
    if(this.playing&&!this.quiet){this.progress=Math.min(1,this.progress+(now-this.sampledAt)/this.duration);this.animationSeconds+=(now-this.sampledAt)/1000}
    this.sampledAt=now
  }
  set(tick:number,playing:boolean,duration:number) {
    this.sample()
    if(tick!==this.tick) {
      this.progress=playing&&!this.quiet&&tick===this.tick+1?0:1
      this.tick=tick
    }
    this.duration=Math.max(16,duration)
    this.playing=playing
  }
  get fraction() {this.sample();return this.progress}
  get time() {this.sample();return Math.max(0,this.tick-1+this.progress)}
  /** Visible gestures use real playback seconds, not accelerated world minutes. */
  get animationTime() {this.sample();return this.animationSeconds}
}
