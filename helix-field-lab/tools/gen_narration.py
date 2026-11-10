"""Generate Kokoro TTS narration clips for each workflow step.

Usage (inside a venv with kokoro + misaki[zh] + soundfile, and ffmpeg on PATH):
    python tools/gen_narration.py [--lang zh|en] [--only outbreak-0] [--voice ...]
Writes audio/<workflow>-<step>.mp3 (zh) or audio/en-<workflow>-<step>.mp3 (en) and audio/manifest.json (durations in seconds).
"""
import argparse, json, subprocess, sys, tempfile
from pathlib import Path

NARRATION = {
    "outbreak": [
        "这是疫情病毒全基因组测序流程。九十四份鼻咽拭子送达后，先扫码登记，放进四度冷藏柜保存。",
        "在生物安全柜里开管，每份取两百微升加入裂解液，病毒在这一步被灭活。",
        "磁珠法核酸提取仪纯化病毒 RNA，大约三十分钟，洗脱到九十六孔板里。",
        "用实时荧光定量 PCR 做初筛，Ct 值低于三十三的样本才进入测序。",
        "移液工作站根据 Ct 值做归一化，配好反转录和两组扩增引物。",
        "回到 PCR 仪，跑三十五个循环，用约四百个碱基长的扩增子覆盖整个病毒基因组。",
        "移液工作站自动完成文库构建：片段化，加索引，磁珠纯化，然后等体积混合。",
        "荧光定量仪测出文库浓度，换算成上机需要的摩尔浓度。",
        "片段分析仪检查文库长度，主峰应该在四百五十个碱基左右，并且没有接头二聚体。",
        "短读长测序仪开始双端一百五十碱基测序，大约八小时，每个基因组覆盖一百倍以上。",
        "边缘计算机柜拆分样本，组装一致性序列，判定病毒谱系，并放进系统发育树。",
        "最后通过卫星链路，把基因组和聚集性分析报告上传到公共卫生平台。全程大约十四小时。",
    ],
    "meta": [
        "这是未知病原宏基因组流程。样本在生物安全柜里一分为二，一半存档，一半放进珠磨裂解管。",
        "离心机把机械裂解后的碎片沉下去，得到干净的裂解液。",
        "提取仪同时纯化 DNA 和 RNA，并去除环境样本里的抑制物。",
        "荧光定量仪确认每个样本至少有五十纳克，满足快速条形码建库。",
        "移液工作站给十二个样本加上条形码，混合后用磁珠纯化。",
        "文库加入纳米孔测序仪，数据实时产生。自适应采样会在测序过程中丢弃人源序列。",
        "GPU 一边做碱基识别，一边做物种分类和耐药基因搜索，读段一到就开始分析。",
        "初步鉴定结果和耐药谱通过卫星推送给临床团队。从样本到答案，大约五小时。",
    ],
    "pgx": [
        "这是药物基因组分型流程。二十四位患者的抗凝血样送达，登记后放入四度冷藏。",
        "在生物安全柜里，每位患者取两百微升全血，加入裂解板。",
        "提取仪纯化基因组 DNA，洗脱到一百微升。",
        "荧光定量仪测量浓度，把每个样本统一到每微升五纳克。",
        "移液工作站配制数字 PCR 反应，包括两个关键药物代谢基因的等位基因探针和拷贝数检测。",
        "数字 PCR 把每个反应分成两万六千个微孔，扩增后逐个计数阳性孔，直接得到绝对拷贝数。",
        "计算机柜判定基因型和代谢表型，为每位患者生成用药建议。全程大约三小时。",
    ],
    "water": [
        "这是饮用水污染物筛查流程。二十份水样装在聚丙烯瓶里，登记后四度保存。",
        "离心去除颗粒物，避免堵塞后面的固相萃取柱。",
        "移液工作站加入同位素内标，完成上样，清洗和洗脱。",
        "萃取好的样品板在板库里低温排队，等待质谱空闲。",
        "液相色谱串联质谱用多反应监测模式，定量四十种全氟化合物和农药，每针五分钟。",
        "计算机柜积分色谱峰，用八点校准曲线算出浓度。",
        "结果与监管限值对比后，上传给供水公司。全程大约四小时。",
    ],
    "amr": [
        "这是耐药菌分离株测序流程。在生物安全柜里挑取单菌落，接种到深孔板培养基中。",
        "板子进入培养箱，三十七度振荡培养过夜，大约十六小时。",
        "离心机以四千倍重力沉淀菌体，去掉上清液。",
        "酶解加磁珠裂解，让革兰氏阳性菌也能充分破壁，然后提取基因组 DNA。",
        "荧光定量仪测量浓度，归一化到适合片段化的投入量。",
        "移液工作站完成片段化和索引 PCR 的反应配制。",
        "PCR 仪跑十二个循环，给每个样本加上独立的索引序列。",
        "片段分析仪检查文库长度分布，合格后再混合上机。",
        "短读长测序仪测序大约十小时，每个菌株覆盖五十倍以上。",
        "计算机柜做从头组装和分型，找出耐药和毒力基因，并做核心基因组聚类。全程约三十小时，包括过夜培养。",
    ],
}

NARRATION_EN = {
    "outbreak": [
        "This is the outbreak viral genomics workflow. Ninety-four nasal swabs arrive. Each tube is scanned, logged, and held at four degrees.",
        "Inside the biosafety cabinet, tubes are opened and two hundred microliters go into lysis buffer, which inactivates the virus.",
        "The magnetic bead extractor purifies viral RNA in about thirty minutes, eluting into a ninety-six well plate.",
        "A real-time PCR screen comes next. Only samples with a C T value below thirty-three go on to sequencing.",
        "The liquid handler normalizes each sample by its C T value and sets up reverse transcription and two tiled primer pools.",
        "Back on the PCR machine, thirty-five cycles of amplification produce overlapping fragments that cover the whole genome.",
        "The liquid handler builds the libraries automatically: fragmenting, tagging, indexing, bead clean-up, and pooling.",
        "The fluorometer measures the pool concentration and converts it to the molarity needed for loading.",
        "The fragment analyzer checks library size. We expect a peak near four hundred fifty base pairs and no adapter dimer.",
        "The short-read sequencer runs paired one-fifty reads for about eight hours, giving every genome over one hundred times coverage.",
        "The edge compute rack sorts the reads by sample, builds consensus genomes, assigns lineages, and places them on a phylogenetic tree.",
        "Finally, genomes and the cluster report are uploaded over satellite to the public health portal. Total turnaround is about fourteen hours.",
    ],
    "meta": [
        "This is the unknown pathogen meta genomics workflow. Each sample is split in the biosafety cabinet: half archived, half into bead-beating tubes.",
        "The centrifuge spins down debris after mechanical lysis, leaving a clear lysate.",
        "The extractor co-purifies DNA and RNA and removes inhibitors common in environmental samples.",
        "The fluorometer confirms at least fifty nanograms per sample for rapid barcoding.",
        "The liquid handler adds a barcode to each of the twelve samples, then pools and cleans them.",
        "The library is loaded onto the nanopore sequencer and data streams in real time. Adaptive sampling rejects human reads during the run.",
        "GPUs turn the raw signal into bases, classify species, and search for resistance genes as each read arrives.",
        "A preliminary identification and resistance profile is sent to the clinical team by satellite. Sample to answer takes about five hours.",
    ],
    "pgx": [
        "This is the pharmacogenomic genotyping workflow. Blood tubes from twenty-four patients are logged and kept at four degrees.",
        "In the biosafety cabinet, two hundred microliters of whole blood per patient go into the lysis plate.",
        "The extractor purifies genomic DNA into one hundred microliters.",
        "The fluorometer measures each sample so it can be normalized to five nanograms per microliter.",
        "The liquid handler assembles digital PCR reactions with allele-specific probes and a copy-number assay for two key drug-metabolism genes.",
        "Digital PCR splits each reaction into twenty-six thousand partitions and counts the positive ones, giving absolute copy numbers.",
        "The compute rack calls each genotype and drug metabolism type and writes a dosing note for every patient. Total time is about three hours.",
    ],
    "water": [
        "This is the drinking water contaminant screen. Twenty water samples arrive in polypropylene bottles and are kept at four degrees.",
        "A quick spin removes particulates that would clog the extraction plate.",
        "The liquid handler spikes isotope-labeled standards, then loads, washes, and elutes the solid-phase extraction plate.",
        "The finished plate waits, chilled, in the plate hotel until the mass spectrometer is free.",
        "The LC mass spectrometer runs a targeted method for forty PFAS and pesticide compounds, five minutes per injection.",
        "The compute rack integrates every peak and quantifies it against an eight-point calibration curve.",
        "Results are compared with regulatory limits and sent to the water utility. Total time is about four hours.",
    ],
    "amr": [
        "This is the antimicrobial resistance isolate workflow. Single colonies are picked in the biosafety cabinet into a deep-well plate.",
        "The plate goes into the incubator overnight at thirty-seven degrees, shaking, for about sixteen hours.",
        "The centrifuge pellets the cells at four thousand g, and the supernatant is removed.",
        "Enzymatic and bead lysis open even tough Gram-positive cells before genomic DNA is extracted.",
        "The fluorometer measures each extract so the input can be normalized for library prep.",
        "The liquid handler sets up fragmenting, tagging, and index PCR.",
        "The PCR machine runs twelve cycles, giving every isolate its own index.",
        "The fragment analyzer checks the size distribution before pooling.",
        "The short-read sequencer runs for about ten hours, covering each isolate at fifty times or more.",
        "The compute rack assembles each genome, assigns a sequence type, finds resistance and virulence genes, and clusters related isolates. About thirty hours in total, including the overnight culture.",
    ],
}


# The zh G2P passes Latin letters through unchanged, so spell acronyms the way
# Mandarin speakers read them aloud.
LETTERS = {"A": "诶", "C": "西", "D": "迪", "G": "吉", "N": "恩", "P": "皮", "R": "阿尔", "T": "梯", "U": "优"}
ACRONYMS = ["PCR", "RNA", "DNA", "GPU", "Ct"]


def speakable(text):
    for ac in ACRONYMS:
        text = text.replace(ac, "".join(LETTERS[ch.upper()] for ch in ac))
    return text.replace(" ", "")


def _disable_broken_espeak():
    """espeakng-loader's bundled data path is broken on macOS, and misaki's
    English G2P only needs espeak as an out-of-vocabulary fallback. The English
    script is written to avoid OOV words, so stub the fallback out."""
    import types, misaki
    stub = types.ModuleType("misaki.espeak")
    class EspeakFallback:
        def __init__(self, *a, **k): pass
        def __call__(self, tok): return (None, None)
    stub.EspeakFallback = EspeakFallback
    sys.modules["misaki.espeak"] = stub
    misaki.espeak = stub


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=["zh", "en"], default="zh")
    ap.add_argument("--only", help="generate a single clip, e.g. outbreak-3")
    ap.add_argument("--voice", help="default: zf_xiaoxiao (zh) / af_heart (en)")
    ap.add_argument("--speed", type=float, default=0.92)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "audio"))
    args = ap.parse_args()

    zh = args.lang == "zh"
    if not zh:
        _disable_broken_espeak()
    import numpy as np, soundfile as sf
    from kokoro import KPipeline

    voice = args.voice or ("zf_xiaoxiao" if zh else "af_heart")
    script = NARRATION if zh else NARRATION_EN
    prefix = "" if zh else "en-"   # zh clips: audio/<wf>-<i>.mp3, en clips: audio/en-<wf>-<i>.mp3
    prep = speakable if zh else (lambda t: t)

    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    man_path = out / "manifest.json"
    manifest = json.loads(man_path.read_text()) if man_path.exists() else {}
    pipe = KPipeline(lang_code="z" if zh else "a", repo_id="hexgrad/Kokoro-82M")

    for wf, lines in script.items():
        for i, text in enumerate(lines):
            key = f"{prefix}{wf}-{i}"
            if args.only and key not in (args.only, prefix + args.only):
                continue
            chunks = [r.audio.numpy() if hasattr(r.audio, "numpy") else r.audio
                      for r in pipe(prep(text), voice=voice, speed=args.speed) if r.audio is not None]
            audio = np.concatenate(chunks)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                sf.write(tmp.name, audio, 24000)
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp.name,
                                "-ac", "1", "-b:a", "56k", str(out / f"{key}.mp3")], check=True)
            manifest[key] = round(len(audio) / 24000, 2)
            print(key, manifest[key], "s", file=sys.stderr)

    man_path.write_text(json.dumps(manifest, indent=0, sort_keys=True))


if __name__ == "__main__":
    main()
