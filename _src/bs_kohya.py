# -*- coding: utf-8 -*-
"""kohya sd-scripts 설치 / TOML 생성 / 학습 / 배치.
   T4(bf16 미지원) 자동 감지, bitsandbytes 실패 시 Adafactor 폴백,
   중단 시 --resume 로 이어서 학습."""
import os, sys, glob, shutil, subprocess, time, requests
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_config as C, bs_common as K, bs_state as ST, bs_log as L, bs_forge as FG

KOHYA = "/kaggle/temp/sd-scripts"
CFG = os.path.join(ST.BASE, "lora", "_config")
MARKER = "/kaggle/temp/.kohya_ready"
os.makedirs(CFG, exist_ok=True)
os.makedirs(ST.LORA_OUT, exist_ok=True)


def caps():
    """(precision, optimizer, gpu_count) 를 환경에 맞춰 결정."""
    prec, gpus = "fp16", 0
    try:
        import torch
        gpus = torch.cuda.device_count()
        if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
            prec = "bf16"
    except Exception:
        pass
    opt = "AdamW8bit"
    rc, out = L.shell('python -c "import bitsandbytes;print(\'BNBOK\')"', quiet=True)
    if "BNBOK" not in out:
        opt = "Adafactor"
    return prec, opt, gpus


def install():
    if os.path.exists(MARKER):
        L.log("kohya 준비 완료 표식 발견")
        return True
    L.banner("kohya sd-scripts 설치")
    if not os.path.isdir(os.path.join(KOHYA, ".git")):
        L.shell("git clone --depth 1 https://github.com/kohya-ss/sd-scripts %s" % KOHYA,
                title="sd-scripts clone")
    L.shell('pip install -q "accelerate>=0.30,<1.2" "transformers>=4.44,<4.57" '
            '"diffusers>=0.25,<0.36" "safetensors>=0.4" toml voluptuous ftfy '
            '"huggingface_hub>=0.25" opencv-python-headless einops', title="학습 의존성")
    L.shell('pip install -q bitsandbytes || true', quiet=True, title="bitsandbytes(선택)")
    cfgdir = os.path.expanduser("~/.cache/huggingface/accelerate")
    os.makedirs(cfgdir, exist_ok=True)
    prec, opt, gpus = caps()
    with open(os.path.join(cfgdir, "default_config.yaml"), "w") as f:
        f.write("compute_environment: LOCAL_MACHINE\ndistributed_type: 'NO'\n"
                "downcast_bf16: 'no'\ngpu_ids: '0'\nmachine_rank: 0\n"
                "main_training_function: main\nmixed_precision: %s\nnum_machines: 1\n"
                "num_processes: 1\nrdzv_backend: static\nsame_network: true\n"
                "use_cpu: false\n" % prec)
    open(MARKER, "w").write(time.strftime("%Y-%m-%d %H:%M:%S"))
    L.ok("kohya 준비 완료 (precision=%s / optimizer=%s / GPU=%d)" % (prec, opt, gpus))
    return True


DATASET_TPL = """[general]
shuffle_caption = true
keep_tokens = 1
caption_extension = ".txt"
enable_bucket = true
bucket_no_upscale = false
min_bucket_reso = 640
max_bucket_reso = 1536

[[datasets]]
resolution = {res}
batch_size = {batch}

  [[datasets.subsets]]
  image_dir = "{img_dir}"
  num_repeats = {repeats}
"""

TRAIN_TPL = """[model_arguments]
pretrained_model_name_or_path = "{ckpt}"
vae = "{vae}"

[additional_network_arguments]
network_module = "networks.lora"
network_dim = {dim}
network_alpha = {alpha}
network_train_unet_only = {unet_only}

[optimizer_arguments]
optimizer_type = "{opt}"
learning_rate = 1e-4
unet_lr = 1e-4
text_encoder_lr = 2e-5
lr_scheduler = "cosine_with_restarts"
lr_scheduler_num_cycles = 3
lr_warmup_steps = 50
max_grad_norm = 1.0

[training_arguments]
output_dir = "{out_dir}"
output_name = "bs_{code}_{ver}"
save_precision = "{prec}"
save_every_n_epochs = 2
save_state = true
max_train_epochs = {epochs}
train_batch_size = {batch}
mixed_precision = "{prec}"
gradient_checkpointing = true
gradient_accumulation_steps = 1
seed = 1234
clip_skip = 2
min_snr_gamma = 5
noise_offset = 0.03
sdpa = true
no_half_vae = true
cache_latents = true
cache_latents_to_disk = true
persistent_data_loader_workers = true
max_data_loader_n_workers = 2
logging_dir = "{log_dir}"
log_prefix = "bs_{code}_"
# IL v19.0 은 NoobAI EPS 기반 -> v_parameterization / zero_terminal_snr 사용 금지
"""


def make_cfg(code, batch=None):
    code = code.upper()
    batch = batch or C.LORA_BATCH
    prec, opt, gpus = caps()
    img_root = os.path.join(ST.BASE, "lora", code, "img")
    subs = sorted(glob.glob(os.path.join(img_root, "*_*")))
    if not subs:
        L.warn("[%s] 데이터셋 없음 - bs_dataset 먼저" % code)
        return None
    img_dir = subs[0]
    repeats = int(os.path.basename(img_dir).split("_", 1)[0])
    out_dir = os.path.join(ST.BASE, "lora", code, "model")
    log_dir = os.path.join(ST.BASE, "lora", code, "log")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)
    d = os.path.join(CFG, code + "_dataset.toml")
    t = os.path.join(CFG, code + "_train.toml")
    with open(d, "w", encoding="utf-8") as f:
        f.write(DATASET_TPL.format(res=C.DATASET_RES, batch=batch,
                                   img_dir=img_dir, repeats=repeats))
    with open(t, "w", encoding="utf-8") as f:
        f.write(TRAIN_TPL.format(ckpt=C.CKPT_PATH, vae=C.VAE_PATH, out_dir=out_dir,
                                 log_dir=log_dir, code=code, ver=C.LORA_VER,
                                 batch=batch, prec=prec, opt=opt,
                                 epochs=C.LORA_EPOCHS, dim=C.LORA_DIM,
                                 alpha=C.LORA_ALPHA,
                                 unet_only=str(not C.LORA_TRAIN_TE).lower()))
    trig = K.CHARS[code]["trigger"]
    with open(os.path.join(CFG, code + "_sample.txt"), "w", encoding="utf-8") as f:
        f.write("%s, %s, %s, 1girl, solo, %s, upper body, looking at viewer, "
                "simple background, BREAK, %s --n %s --w 832 --h 1216 --d 1234 "
                "--l 4.5 --s 26\n" % (C.QUALITY_HEAD, C.STYLE_BA, trig,
                                      K.CHARS[code]["anchor"], C.TAIL, C.NEG_DATASET))
    L.ok("[%s] TOML 생성 (precision=%s optimizer=%s)" % (code, prec, opt))
    return t, d


def _resume_arg(code):
    st_dirs = sorted(glob.glob(os.path.join(ST.BASE, "lora", code.upper(),
                                            "model", "*-state*")))
    if st_dirs:
        L.log("[%s] 이전 학습 상태 발견 -> 이어서 학습" % code)
        return ' --resume "%s"' % st_dirs[-1]
    return ""


def train(code, batch=None, gpu_id=None):
    code = code.upper()
    install()
    r = make_cfg(code, batch)
    if not r:
        return False
    t, d = r
    script = os.path.join(KOHYA, "sdxl_train_network.py")
    if not os.path.exists(script):
        L.err("sdxl_train_network.py 없음")
        return False
    prec, opt, gpus = caps()
    env_prefix = ""
    if gpu_id is not None:
        env_prefix = "CUDA_VISIBLE_DEVICES=%d " % gpu_id
    cmd = ('cd %s && %saccelerate launch --num_cpu_threads_per_process 2 '
           '--mixed_precision %s "%s" --config_file "%s" --dataset_config "%s" '
           '--sample_prompts "%s" --sample_every_n_epochs 2 --sample_sampler euler_a%s'
           % (KOHYA, env_prefix, prec, script, t, d,
              os.path.join(CFG, code + "_sample.txt"), _resume_arg(code)))
    L.banner("LoRA 학습 시작 : %s" % code)
    t0 = time.time()
    rc, out = L.shell(cmd, timeout=60 * 240, tail=25, title="accelerate launch")
    mins = (time.time() - t0) / 60
    made = glob.glob(os.path.join(ST.BASE, "lora", code, "model",
                                  "bs_%s_%s*.safetensors" % (code, C.LORA_VER)))
    ok = rc == 0 and bool(made)
    ST.mark("lora_%s" % code, "done" if ok else "failed", "%.1f분 rc=%s" % (mins, rc))
    if ok:
        L.ok("[%s] 학습 완료 %.1f분 / 산출 %d개" % (code, mins, len(made)))
    else:
        L.err("[%s] 학습 실패 rc=%s (%.1f분)" % (code, rc, mins))
    return ok


def deploy():
    dst = "/kaggle/temp/models/Lora"
    os.makedirs(dst, exist_ok=True)
    n = 0
    for code in K.CHARS:
        cands = sorted(glob.glob(os.path.join(
            ST.BASE, "lora", code, "model",
            "bs_%s_%s*.safetensors" % (code, C.LORA_VER))))
        if not cands:
            continue
        final = [c for c in cands
                 if c.endswith("bs_%s_%s.safetensors" % (code, C.LORA_VER))]
        src = final[0] if final else cands[-1]
        name = "bs_%s_%s.safetensors" % (code, C.LORA_VER)
        shutil.copy2(src, os.path.join(dst, name))
        shutil.copy2(src, os.path.join(ST.LORA_OUT, name))
        n += 1
    L.ok("LoRA %d개 배치 -> %s" % (n, dst))
    try:
        requests.post(FG.API + "/sdapi/v1/refresh-loras", timeout=120)
        L.ok("Forge LoRA 목록 갱신")
    except Exception as e:
        L.log("refresh 생략(Forge 미기동): %s" % e)
    ST.rescan()
    return n
