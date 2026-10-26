# Nayro-Levant-AI-Studio

AI Content Creation Studio — يولّد فيديو MP4 جاهزاً للنشر من وصف نصي عربي أو إنجليزي.
Turns a short text prompt (Arabic or English) into a branded, animated MP4 video.

## المميزات / Features

- توليد تلقائي للمشاهد من النص: كل جملة تتحول إلى مشهد مع عنوان وعنوان فرعي.
- دعم كامل للعربية (تشكيل الحروف واتجاه RTL) بخط Noto Kufi Arabic مضمّن.
- ٤ سمات ألوان: `aurora`، `midnight`، `sunrise`، `desert`.
- خلفيات متدرجة متحركة، ظهور ناعم للنص، وانتقالات Crossfade بين المشاهد.
- شريط تقدّم، رقم المشهد، وهوية الاستوديو في كل إطار.
- تصدير H.264 MP4 (yuv420p + faststart) عبر ffmpeg المضمّن — بدون تثبيت نظامي.
- ملف Storyboard بصيغة JSON للتحكم الكامل في النصوص والمدة والسمات.

## التثبيت / Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

## الاستخدام السريع / Quick start

```bash
# من وصف نصي مباشرةً
.venv/bin/nayro-video --prompt "استوديو نيرو ليفانت للذكاء الاصطناعي. حوّل أفكارك إلى فيديو متكامل. جاهز للنشر على كل المنصات." \
  --out output/demo.mp4

# من ملف Storyboard جاهز
.venv/bin/nayro-video --storyboard examples/studio-intro.json \
  --out output/nayro-studio-intro.mp4
```

الفيديو التجريبي المرفق: [`output/nayro-studio-intro.mp4`](output/nayro-studio-intro.mp4)
(1280×720، 24 إطار/ثانية، 11 ثانية، H.264).

### خيارات / Options

| Option | Default | Description |
| --- | --- | --- |
| `--prompt`, `-p` | – | وصف نصي (عربي أو إنجليزي) |
| `--storyboard`, `-s` | – | مسار ملف JSON |
| `--out`, `-o` | `output/nayro-video.mp4` | مسار الفيديو الناتج |
| `--duration` | `3.0` | مدة كل مشهد بالثواني (وضع الوصف) |
| `--theme` | `aurora` | `aurora` / `midnight` / `sunrise` / `desert` |
| `--width`, `--height` | `1280`, `720` | أبعاد الإطار |
| `--fps` | `24` | عدد الإطارات في الثانية |
| `--brand` | `NAYRO LEVANT · AI STUDIO` | النص العلوي في كل مشهد |
| `--max-scenes` | `8` | أقصى عدد مشاهد في وضع الوصف |
| `--save-storyboard` | – | حفظ الـ Storyboard المولّد لملف JSON |
| `--dry-run` | – | بناء الـ Storyboard بدون تصدير فيديو |
| `--list-themes` | – | عرض السمات المتاحة |

### صيغة الـ Storyboard

```json
{
  "brand": "NAYRO LEVANT · AI STUDIO",
  "width": 1280,
  "height": 720,
  "fps": 24,
  "theme": "aurora",
  "transition": 0.6,
  "scenes": [
    { "title": "استوديو نيرو ليفانت", "subtitle": "نصنع المحتوى بالذكاء الاصطناعي", "duration": 3.2 },
    { "title": "جاهز للنشر", "duration": 3.0, "theme": "desert" }
  ]
}
```

## التطوير والاختبارات / Tests

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
```

## البنية / Layout

```
nayro_studio/
  cli.py          # واجهة الأوامر
  storyboard.py   # نموذج المشاهد وتحويل الوصف إلى Storyboard
  renderer.py     # رسم الإطارات: تدرجات، نصوص، انتقالات
  text.py         # تشكيل العربية وتقسيم الأسطر
  fonts.py        # تحميل الخطوط المضمّنة
  theme.py        # سمات الألوان
  video.py        # ترميز H.264 عبر ffmpeg
  probe.py        # قراءة بيانات الفيديو الناتج
  assets/fonts/   # Noto Kufi Arabic + Noto Sans
examples/         # Storyboard جاهز للتجربة
output/           # الفيديو التجريبي
tests/            # اختبارات pytest
```
