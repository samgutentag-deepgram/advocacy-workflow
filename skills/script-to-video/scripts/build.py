#!/usr/bin/env python3
"""Render a beat script into a karaoke base-layer video.

  build.py script.json                 # every take in the file
  build.py script.json 4-technical     # just one
  build.py script.json --outdir ./out --keep-wav
  build.py script.json --estimate      # predicted durations, no API calls

Frame layout: bracketed shot direction top left, the current sentence in the middle
with the spoken word lit, full-clip waveform along the bottom with a playhead.

Needs Pillow and ffmpeg. See SKILL.md.
"""
import sys, os, json, wave, re, difflib, subprocess, pathlib, array
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from dg import speak, write_wav, words as stt_words, SR
from PIL import Image, ImageDraw, ImageFont

FPS = 24
BG=(14,17,22); DIM=(88,99,115); MID=(140,152,168); HOT=(233,239,246)
ACC=(255,176,46); WAVE=(52,62,78); WAVE_ON=(255,176,46)
HEL=os.environ.get("S2V_FONT_SANS","/System/Library/Fonts/HelveticaNeue.ttc")
MEN=os.environ.get("S2V_FONT_MONO","/System/Library/Fonts/Menlo.ttc")

def layout(orientation):
    """Geometry and fonts per orientation. Vertical is 9:16 for social."""
    if orientation == "vertical":
        return dict(W=1080, H=1920, pad=64, wave_y=1560, wave_h=150, text_y=760, line_h=104,
                    f_dir=ImageFont.truetype(MEN,26), f_txt=ImageFont.truetype(HEL,74,index=0),
                    f_lbl=ImageFont.truetype(MEN,22), f_big=ImageFont.truetype(HEL,96,index=1),
                    f_sub=ImageFont.truetype(MEN,30))
    return dict(W=1920, H=1080, pad=80, wave_y=890, wave_h=110, text_y=380, line_h=88,
                f_dir=ImageFont.truetype(MEN,34), f_txt=ImageFont.truetype(HEL,62,index=0),
                f_lbl=ImageFont.truetype(MEN,24), f_big=ImageFont.truetype(HEL,84,index=1),
                f_sub=ImageFont.truetype(MEN,28))

# Flux pauses at every sentence boundary and lengthens the final word, so duration tracks
# words AND sentence count. Punchy fragment copy runs ~half the words-per-minute of flowing
# prose. Measured across four samples; good to about 10 percent.
SEC_PER_WORD = 0.30
SEC_PER_SENTENCE = 0.70

def estimate(text):
    return len(text.split())*SEC_PER_WORD + len(sentences(text))*SEC_PER_SENTENCE

def estimate_chunk(ch, beat_gap=0.45):
    beats=ch["beats"]
    return (sum(estimate(b[1]) for b in beats)
            + sum(b[2] for b in beats if len(b)>2)
            + len(beats)*beat_gap)

def sentences(t):
    return [p for p in re.split(r'(?<=[.!?])\s+', t.strip()) if p.strip()]

def norm(w): return re.sub(r"[^a-z0-9]", "", w.lower())

def align(src, dg):
    """Source words keep their own spelling; timings come from the STT of the real audio."""
    a=[norm(w) for w in src]; b=[norm(x["word"]) for x in dg]
    t=[None]*len(src)
    for i,j,n in difflib.SequenceMatcher(a=a,b=b,autojunk=False).get_matching_blocks():
        for k in range(n): t[i+k]=(dg[j+k]["start"], dg[j+k]["end"])
    known=[i for i,v in enumerate(t) if v]
    if not known: return [(0,0)]*len(src)
    for i in range(len(t)):
        if t[i]: continue
        prev=[k for k in known if k<i]; nxt=[k for k in known if k>i]
        if prev and nxt:
            p,n_=prev[-1],nxt[0]; s=t[p][1]; span=t[n_][0]-s; f=(i-p)/(n_-p)
            t[i]=(s+span*f, s+span*(f+1/(n_-p)))
        elif prev: t[i]=(t[prev[-1]][1], t[prev[-1]][1]+0.25)
        else:      t[i]=(max(0,t[nxt[0]][0]-0.25), t[nxt[0]][0])
    return t

def envelope(pcm, n):
    s=array.array("h"); s.frombytes(pcm[:len(pcm)-(len(pcm)%2)])
    L=len(s); out=[]
    for i in range(n):
        lo=L*i//n; hi=max(lo+1, L*(i+1)//n); c=s[lo:hi]
        out.append(max(abs(min(c)),abs(max(c)))/32768.0 if c else 0.0)
    return out

def wrap(d, text, font, maxw):
    out=[]; line=""
    for w in text.split():
        t=(line+" "+w).strip()
        if d.textlength(t,font=font)<=maxw: line=t
        else: out.append(line); line=w
    if line: out.append(line)
    return out

def build(key, spec, outdir, keep_wav=False):
    OUT=pathlib.Path(outdir); OUT.mkdir(parents=True, exist_ok=True)
    # A spec has either flat "beats" or "chunks", each chunk a self-contained clip
    # separated by a silent gap so the reel can be cut apart on the gaps.
    chunks = spec.get("chunks")
    if chunks is None:
        chunks = [{"label": None, "beats": spec["beats"]}]
    chunk_gap = spec.get("chunk_gap", 5)
    n_chunks = len(chunks)
    target = spec.get("target_seconds")
    if target:
        for i,ch in enumerate(chunks):
            est=estimate_chunk(ch)/spec.get("tempo",1.0)
            if est > target*1.15:
                print(f"[{key}] chunk {i+1} estimates {est:.0f}s against a {target}s target "
                      f"({ch.get('label')}). Cut it before rendering.", flush=True)

    print(f"[{key}] rendering audio ({n_chunks} chunk(s))...", flush=True)
    pcm=b""; beats=[]; gap=b"\x00\x00"*int(SR*0.45)
    for ci, ch in enumerate(chunks):
        if ci and chunk_gap:
            t0=len(pcm)/2/SR
            pcm += b"\x00\x00"*int(SR*chunk_gap)
            beats.append({"dir":"","text":"","t0":t0,"t1":t0+chunk_gap,"gap":True,
                          "chunk":ci,"n":n_chunks,"label":ch.get("label")})
        for beat in ch["beats"]:
            direction, text = beat[0], beat[1]
            hold = beat[2] if len(beat)>2 else 0
            t0=len(pcm)/2/SR
            seg=speak(text, spec.get("voice","flux-alexis-en"))
            pcm+=seg+gap; t1=t0+len(seg)/2/SR
            beats.append({"dir":direction,"text":text,"t0":t0,"t1":t1,
                          "chunk":ci,"n":n_chunks,"label":ch.get("label")})
            if hold:
                pcm += b"\x00\x00"*int(SR*hold)
                beats.append({"dir":direction+"  //  HOLD","text":"","t0":t1,"t1":t1+hold,
                              "chunk":ci,"n":n_chunks,"label":ch.get("label")})

    tempo=spec.get("tempo",1.0)
    if tempo!=1.0:
        raw=OUT/f"{key}.raw.wav"; slow=OUT/f"{key}.slow.wav"; write_wav(pcm,raw)
        subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-i",str(raw),
                        "-filter:a",f"atempo={tempo}","-ar",str(SR),"-ac","1",str(slow)],check=True)
        with wave.open(str(slow),"rb") as w: pcm=w.readframes(w.getnframes())
        raw.unlink(); slow.unlink()
        for b in beats: b["t0"]/=tempo; b["t1"]/=tempo
        print(f"[{key}] atempo={tempo}", flush=True)

    wav=OUT/f"{key}.wav"; write_wav(pcm, wav); dur=len(pcm)/2/SR
    print(f"[{key}] {dur:.1f}s audio, getting word timings...", flush=True)
    dg=stt_words(wav)

    final=[]
    for b in beats:
        sents=sentences(b["text"])
        if not sents:
            final.append({**b,"words":[],"times":[]}); continue
        dgb=[x for x in dg if b["t0"]-0.15 <= x["start"] < b["t1"]+0.15]
        allw=[w for s in sents for w in s.split()]
        times=align(allw,dgb) if dgb else [(b["t0"],b["t1"])]*len(allw)
        i=0
        for s in sents:
            sw=s.split(); tt=times[i:i+len(sw)]; i+=len(sw)
            if tt: final.append({**b,"words":sw,"times":tt,"t0":tt[0][0],"t1":tt[-1][1]})
    for a,b2 in zip(final, final[1:]): a["t1"]=max(a["t1"], b2["t0"]-0.05)
    if final: final[-1]["t1"]=dur

    L = layout(spec.get("orientation","horizontal"))
    W,H,pad = L["W"],L["H"],L["pad"]
    wy,wh = L["wave_y"],L["wave_h"]
    print(f"[{key}] {len(final)} sentences, rendering {int(dur*FPS)} frames at {W}x{H}...", flush=True)
    env=envelope(pcm, W-2*pad)
    base=Image.new("RGB",(W,H),BG); d0=ImageDraw.Draw(base)
    d0.text((pad,pad-16),"[ ON SCREEN ]",font=L["f_lbl"],fill=DIM)
    for i,v in enumerate(env):
        h=max(2,int(v*wh)); d0.line([(pad+i,wy-h),(pad+i,wy+h)],fill=WAVE)
    d0.text((pad,H-pad+8), spec.get("title",key).upper(), font=L["f_lbl"], fill=DIM)

    mp4=OUT/f"{key}.mp4"
    ff=subprocess.Popen(["ffmpeg","-y","-hide_banner","-loglevel","error",
        "-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}","-r",str(FPS),"-i","-",
        "-i",str(wav),"-c:v","libx264","-preset","veryfast","-crf","20",
        "-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-shortest",str(mp4)],
        stdin=subprocess.PIPE)
    cur=0
    for fi in range(int(dur*FPS)):
        t=fi/FPS
        while cur+1<len(final) and t>=final[cur+1]["t0"]: cur+=1
        u=final[cur] if final else None
        im=base.copy(); d=ImageDraw.Draw(im)
        if u and u.get("gap"):
            # Cut marker. Deliberately loud so the boundary is findable when scrubbing.
            d.rectangle([0,0,W,H],fill=(20,14,4))
            nxt=f"CLIP {u['chunk']+1} / {u['n']}"
            tw=d.textlength(nxt,font=L["f_big"])
            d.text(((W-tw)/2, H/2-120), nxt, font=L["f_big"], fill=ACC)
            if u.get("label"):
                for k,ln in enumerate(wrap(d,u["label"],L["f_sub"],W-2*pad)):
                    lw=d.textlength(ln,font=L["f_sub"])
                    d.text(((W-lw)/2, H/2+20+k*44), ln, font=L["f_sub"], fill=MID)
            cw=d.textlength("— CUT HERE —",font=L["f_sub"])
            d.text(((W-cw)/2, H/2+200), "— CUT HERE —", font=L["f_sub"], fill=DIM)
            ff.stdin.write(im.tobytes()); continue
        if u:
            d.text((pad,pad+24), f"[ {u['dir']} ]", font=L["f_dir"], fill=ACC)
            if u.get("n",1) > 1:
                tag=f"CLIP {u['chunk']+1}/{u['n']}"
                d.text((W-pad-d.textlength(tag,font=L["f_lbl"]), pad-16), tag,
                       font=L["f_lbl"], fill=DIM)
            lines=wrap(d,' '.join(u["words"]),L["f_txt"],W-2*pad) if u["words"] else []
            wi=0; y=L["text_y"]-(len(lines)-1)*(L["line_h"]//2); active=-1
            for k,(s_,e_) in enumerate(u["times"]):
                if s_<=t<=e_: active=k; break
                if t>e_: active=k
            for ln in lines:
                x=pad
                for w in ln.split():
                    d.text((x,y),w,font=L["f_txt"],fill=HOT if wi==active else (MID if wi<active else DIM))
                    x+=d.textlength(w+" ",font=L["f_txt"]); wi+=1
                y+=L["line_h"]
        px=int(pad+(W-2*pad)*min(1.0,t/dur))
        for i in range(pad,px):
            h=max(2,int(env[i-pad]*wh)); d.line([(i,wy-h),(i,wy+h)],fill=WAVE_ON)
        d.line([(px,wy-wh-14),(px,wy+wh+14)],fill=HOT,width=3)
        ff.stdin.write(im.tobytes())
    ff.stdin.close(); ff.wait()
    if ff.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for {key} (exit {ff.returncode}); wav kept at {wav}")
    if not keep_wav:
        wav.unlink()          # the mp4 carries the audio; the wav is an intermediate
    print(f"[{key}] done -> {mp4}  ({int(dur//60)}:{int(dur%60):02d})", flush=True)
    return mp4

if __name__=="__main__":
    args=[a for a in sys.argv[1:]]
    keep = "--keep-wav" in args; args=[a for a in args if a!="--keep-wav"]
    estimate_only = "--estimate" in args; args=[a for a in args if a!="--estimate"]
    outdir="./out"
    if "--outdir" in args:
        i=args.index("--outdir"); outdir=args[i+1]; del args[i:i+2]
    if not args:
        sys.exit(__doc__)
    specs=json.load(open(args[0]))
    if estimate_only:
        for k in (args[1:] or list(specs)):
            sp=specs[k]; t=sp.get("tempo",1.0); tgt=sp.get("target_seconds")
            chunks=sp.get("chunks") or [{"label":None,"beats":sp["beats"]}]
            total=0
            print(f"\n{k}  (tempo {t}" + (f", target {tgt}s/chunk" if tgt else "") + ")")
            for i,ch in enumerate(chunks):
                e=estimate_chunk(ch)/t; total+=e
                flag=""
                if tgt and e>tgt*1.15: flag="  << OVER"
                elif tgt and e<tgt*0.7: flag="  << short"
                print(f"  chunk {i+1:2d}  {e:5.1f}s  {ch.get('label') or ''}{flag}")
            total += (len(chunks)-1)*sp.get("chunk_gap",5)
            print(f"  total   {int(total//60)}:{int(total%60):02d}")
        sys.exit(0)
    # One take failing (a dropped TTS call, a network blip) must not cost the rest of the batch.
    todo=(args[1:] or list(specs)); done=[]; failed=[]
    for k in todo:
        try:
            build(k, specs[k], outdir, keep); done.append(k)
        except Exception as e:
            failed.append((k, f"{type(e).__name__}: {e}"))
            print(f"[{k}] FAILED -> {type(e).__name__}: {e}", file=sys.stderr, flush=True)
    if len(todo) > 1 or failed:
        print(f"\n{len(done)}/{len(todo)} rendered.")
        for k, err in failed:
            print(f"  FAILED  {k}  {err}")
        print(f"  retry:  build.py {args[0]} {' '.join(k for k,_ in failed)}" if failed else "")
    sys.exit(1 if failed else 0)
