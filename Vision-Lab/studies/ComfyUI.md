# 🏗️ ملخص معماري: ComfyUI (Portable)

> دراسة جرد معماري — تثبيت Portable على `G:\ai\ComfyUI_windows_portable`
> تاريخ آخر تحديث: 2026-10-18 | وضع الفحص: قراءة أسماء وملفات نصية صغيرة فقط (لا فتح موديلات)

---

## 1) الهوية والإصدار

| البند | القيمة |
|---|---|
| المنتج | ComfyUI — تثبيت Windows Portable مستقل (كله داخل مجلد واحد) |
| إصدار ComfyUI | **0.38.0** (`ComfyUI\comfyui_version.py` = قيمة `pyproject.toml`) |
| مصدر الكود | مستودع git رسمي — `ComfyUI\.git` موجود (متجرّ `comfyanonymous/ComfyUI` / comfy.org) |
| بيئة Python المضمّنة | `python_embeded\` — **Python 3.12** (`python312.dll` / `python312._pth` / `python312.zip`) |
| إطار التوليد | **PyTorch 2.14.0+cu126** → مبني على **CUDA 12.6** (من `torch\version.py`) |
| حزم الواجهة المرتبطة | `comfyui-frontend-package 1.53.6` • `comfyui-workflow-templates 0.11.70` • `comfyui-embedded-docs 0.5.12` (من requirements.txt) |
| متطلبات بايثون العامة | `requires-python = ">=3.10"` |
| نمط التشغيل | `--windows-standalone-build` يُمرَّر تلقائيًا في كل سكربتات التشغيل |

## 2) الغرض

- **ComfyUI** محرك واجهة عقدية (Node/Graph) لتوليد الصور بـ Stable Diffusion ونحوهما: خادم بايثون محلي + واجهة متصفح برسم بياني من عقد.
- دوره في مخطط «Vision-Lab» الخاص بورشة «النجار برنت»: **محرك توليد الصور/الماكيتات المحلي** بين الدراسات المعمارية الأخرى في `Vision-Lab\studies`.
- ميزة هذا التثبيت: **محمول بالكامل** — بايثون 3.12 + مكتبات مضمنة في `python_embeded\`، لا يعتمد على بايثون النظام، و4 سكربتات تشغيل جاهزة حسب العتاد.
- التثبيت **فانيلا نظيف**: بلا عُقد مخصّصة ولا موديلات إضافية — قاعدة نظيفة قابلة للتوسعة بأمان.

## 3) التشغيل

- **البوابة الرسمية**: `run_nvidia_gpu.bat` — سطره التنفيذي:
  `.\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build`
  يفتح خادمًا على `http://127.0.0.1:8188` افتراضيًا (المنفذ مؤكَّد في `ComfyUI\main.py`) وتُدار الواجهة من المتصفح.
- سكربتات الجذر (4):
  | السكربت | الاستخدام |
  |---|---|
  | `run_nvidia_gpu.bat` | القياسي لكروت NVIDIA |
  | `run_nvidia_gpu_fast_fp16_accumulation.bat` | يضيف `--fast fp16_accumulation` — أسرع لموديلات fp16 بجودة أقل يسيرًا |
  | `run_nvidia_gpu_lowvram.bat` | وضع الذاكرة المنخفضة (`--lowvram`) |
  | `run_cpu.bat` | CPU بطيء بدون GPU |
- سكربت إضافي في `advanced\`: `run_nvidia_gpu_disable_api_nodes.bat` — تشغيل بتعطيل عقد API الجديدة (توافق مع مهام سير عمل قديمة).
- **التحديث** (`update\`): `update_comfyui.bat` (كود فقط) • `update_comfyui_stable.bat` (قناة مستقرة) • `update_comfyui_and_python_dependencies.bat` (كود + اعتماديات — فقط عند مشاكل) • `update.py`.
- تنبيهات التشغيل: خطأ `c10.dll` → تثبيت VC++ Redist؛ والخطأ الأحمر في الواجهة غالبًا غياب checkpoint في `models\checkpoints`.

## 4) الهيكل

```
G:\ai\ComfyUI_windows_portable\
├─ run_nvidia_gpu.bat                     ← نقطة التشغيل الرئيسية (NVIDIA)
├─ run_nvidia_gpu_fast_fp16_accumulation.bat / _lowvram.bat / run_cpu.bat
├─ README_VERY_IMPORTANT.txt              ← إرشادات التشغيل/التحديث/المشاركة (1 KB)
├─ advanced\run_nvidia_gpu_disable_api_nodes.bat
├─ update\  update_comfyui.bat · update_comfyui_stable.bat
│           update_comfyui_and_python_dependencies.bat · update.py
├─ python_embeded\                        ← Python 3.12 كامل + PyTorch cu126 (مضمّن ومحصور)
│   └─ Lib\site-packages\                 ← حزم البيئة (torch 2.14.0+cu126 وغيره)
└─ ComfyUI\                               ← التطبيق نفسه (نسخة git قابلة للتحديث)
    ├── main.py · server.py · execution.py · nodes.py · folder_paths.py
    ├── comfy\ comfy_execution\ comfy_api\ comfy_api_nodes\ comfy_extras\
    ├── api_server\ middleware\ blueprints\      ← طبقة API الحديثة (v0.38)
    ├── alembic_db\ alembic.ini  +  user\comfyui.db ← قاعدة SQLite محلية (اختيارية)
    ├── custom_nodes\ input\ output\ temp\ models\
    ├── requirements.txt / manager_requirements.txt / openapi.yaml
    ├── comfyui_version.py · pyproject.toml
    └── extra_model_paths.yaml.example            ← غير مُفعَّل (مشاركة موديلات مع واجهات أخرى)
```

- ملاحظة هيكلية: `ComfyUI\input\` يحوي مجلد `3d\` و`example.png` — مدخل ملفات مرجعية (يشمل مجلد `3d` الخاص بحزم العقد ثلاثية الأبعاد في الإصدارات الحديثة).

## 5) الموديلات (جرد أسماء)

> 26 مجلدًا فرعيًا تحت `ComfyUI\models\`، معظمها هيكل فارغ بملف إرشادي `put_…_here`.
> **ملفات موديل فعلية:**

| الفئة | الملف (اسم فقط) | الحجم |
|---|---|---|
| checkpoints | `v1-5-pruned-emaonly-fp16.safetensors` | ~2.0 GB — الموديل الفعلي الوحيد (SD 1.5) |
| vae_approx | `taesd_encoder.safetensors` · `taesd_decoder.safetensors` | ~2.3 MB لكلٍّ (معاينات SD 1.5) |
| vae_approx | `taesdxl_encoder.safetensors` · `taesdxl_decoder.safetensors` | ~2.3 MB لكلٍّ (معاينات SDXL) |
| vae_approx | `taef1_encoder.safetensors` · `taef1_decoder.safetensors` | ~2.4 MB لكلٍّ (معاينات FLUX) |
| configs | `anything_v3.yaml` + `v1-inference*.yaml` + `v2-inference*.yaml` + `v1/v2-inpainting-inference.yaml` | ملفات إعداد صغيرة |

- باقي الفئات **فارغة** (loras, vae, controlnet, upscale_models, clip, clip_vision, text_encoders, unet, diffusion_models, diffusers, embeddings, style_models, hypernetworks, gligen, photomaker, upscale… وغيرها — ملفات `put_…_here` فقط).
- لا يوجد `extra_model_paths.yaml` مُفعَّل → قراءة الموديلات من هذا المجلد محليًا فقط.

## 6) custom_nodes

المجلد **شبه فارغ — بلا أي عقدة طرفية خارجية** (تثبيت فانيلا):

| العنصر | الوصف |
|---|---|
| `websocket_image_save.py` | عقدة مدمجة من الحزمة نفسها: `SaveImageWebsocket` — ترسل الصور كاملة الحجم عبر WebSocket لعملاء الـ API (بدون ميتاداتا داخل الصورة) |
| `example_node.py.example` | قالب مثال عقدة مخصصة، غير مفعّل (امتداد `.example`) |
| `__pycache__` | كاش بايثون فقط |

- لا يوجد **ComfyUI-Manager** ولا أي عقدة مجتمعية مثبتة → التثبيت نظيف وقابل للتحديث بلا تعارضات.

## 7) التكاملات

- **خادم محلي HTTP + WebSocket** على `127.0.0.1:8188` (من `main.py`) — نقطة التكامل الأساسية لأي أتمتة (REST: `openapi.yaml` / `api_server\`).
- **أثر استخدام آلي موجود**: `output\` يحتوي `dsh-comfyui_00001_.png` و`dsh-comfyui_00002_.png` — بادئة `dsh-comfyui` تثبت أن أدوات Vision-Lab/DSH سبق أن ولّدت صورًا عبر هذا الخادم (تكامل فعلي قائم، لا افتراضي).
- **قاعدة بيانات محلية**: `user\comfyui.db` (+wal/shm) عبر SQLite + ترحيلات `alembic` — تخزين إعدادات المستخدم/الجلسات.
- **عقدة SaveImageWebsocket** → مسار تسليم صور مخصص لعملاء WebSocket دون واجهة المتصفح.
- **حزم الواجهة كتبعيات pip**: الواجهة (frontend 1.53.6) وقوالب الـ workflows والوثائق تأتي كحزم منفصلة تُحدَّث مع `update_comfyui_and_python_dependencies.bat`.
- **مشاركة الموديلات مع واجهات أخرى**: متاحة لكن **غير مفعّلة** (`extra_model_paths.yaml.example` لم يُعد تسميته).
- **مخرَج الإدخال ثلاثي الأبعاد**: `input\3d\` لمدخلات حزم العقد 3D الحديثة.

## 8) تقييم الصحة

| المحور | التقييم |
|---|---|
| ✅ إصدار حديث | ComfyUI 0.38.0 + PyTorch 2.14/cu126 — طبقة API حديثة (api_server, blueprints, middleware) |
| ✅ جرّب سابقًا | `comfyui.db` موجود + صورتان في `output\` → التثبيت اشتغل فعلًا وليس مجرد فك ضغط |
| ✅ جاهز من أول تشغيل | checkpoint افتراضي حاضر (`v1-5-pruned-emaonly-fp16.safetensors` ~2GB) — لا خطأ «لا يوجد موديل» |
| ✅ نظيف ومستقر | صفر عقد مخصصة طرفية → لا تعارضات تحديث؛ مستودع git سليم يسمح بتحديث مباشر |
| ⚠️ محدودية إنتاجية | الموديل الوحيد SD 1.5 (2022) — للعمل الإنتاجي الحديث يلزم تنزيل SDXL/FLUX لاحقًا إلى `checkpoints\` |
| ⚠️ استخدام خفيف | مخرجان فقط في `output\` → ما زال في مرحلة الإعداد/التجريب |
| ⚠️ متطلبات تشغيل | كرت NVIDIA بدرايفر حديث؛ `c10.dll` يعني نقص VC++ Redist (`aka.ms/vc14/vc_redist.x64.exe`) |

**الحكم**: تثبيت سليم وجاهز للتشغيل الفوري، في مرحلة مبكرة من الاستخدام، قاعدة ممتازة للتوسعة بإضافة موديلات وعُقد لاحقًا.

## 9) خريطة دخول

1. **تشغيل الواجهة**: `run_nvidia_gpu.bat` → افتح `http://127.0.0.1:8188` في المتصفح.
2. **إضافة موديل**: ضع `.safetensors` في `ComfyUI\models\checkpoints\` (أو الفئة المناسبة) ثم حدّث الواجهة.
3. **تسريع fp16**: `run_nvidia_gpu_fast_fp16_accumulation.bat` — ضعف الأدوات ذاتها لكن أسرع.
4. **كارت ضعيف الذاكرة**: `run_nvidia_gpu_lowvram.bat`.
5. **تحديث الكود**: `update\update_comfyui.bat` — ولا تشغّل سكربت الاعتماديات إلا عند مشاكل.
6. **أتمتة برمجية**: اقرأ `ComfyUI\openapi.yaml` واتصل بـ `127.0.0.1:8188` (بادئة `api_server\`)، أو استخدم عقدة `SaveImageWebsocket` لالتقاط الصور مباشرة من الـ WebSocket.
7. **إرشادات المالك**: `README_VERY_IMPORTANT.txt` في الجذر.

## 10) فهرس مختصر

| المسار | المحتوى |
|---|---|
| `run_nvidia_gpu.bat` | نقطة الدخول — بايثون مضمّن + `main.py --windows-standalone-build` |
| `python_embeded\` | Python 3.12 + PyTorch 2.14.0+cu126 (مكتفٍ ذاتيًا) |
| `ComfyUI\` | كود الإصدار 0.38.0 (git) + النواة وطبقة API |
| `ComfyUI\models\` | 26 فئة — فعليًا: SD1.5 fp16 + معاينات taesd/taesdxl/taef1 |
| `ComfyUI\custom_nodes\` | فارغ تقريبًا (عقدة websocket مدمجة فقط) |
| `ComfyUI\output\` | `_output_images_will_be_put_here` + `dsh-comfyui_00001/00002_.png` |
| `ComfyUI\user\comfyui.db` | قاعدة SQLite للتخزين المحلي |
| `update\` | 3 سكربتات تحديث + `update.py` |
| `README_VERY_IMPORTANT.txt` | دليل التشغيل والتحديث والمشاركة |

---
_ملف الدراسة مبني على قراءة أسماء الملفات والمجلدات + ملفات نصية صغيرة (bat / py / yaml / toml). لم يُفتح أي ملف موديل._
