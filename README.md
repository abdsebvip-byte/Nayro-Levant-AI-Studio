# Nayro-Levant-AI-Studio

AI Content Creation Studio — يولّد فيديو MP4 جاهزاً للنشر من وصف نصي عربي أو إنجليزي.
Turns a short text prompt (Arabic or English) into a branded, animated MP4 video.

## المميزات / Features

- توليد تلقائي للمشاهد من النص: كل جملة تتحول إلى مشهد مع عنوان وعنوان فرعي.
- دعم كامل للعربية (تشكيل الحروف واتجاه RTL) بخط Noto Kufi Arabic مضمّن.
- ٤ سمات ألوان: `aurora`، `midnight`، `sunrise`، `desert`.
- خلفيات متدرجة متحركة، ظهور ناعم للنص، وانتقالات Crossfade بين المشاهد.
- تعليق صوتي كامل (سكربت لكل مشهد) بأصوات عصبية عربية، مع ضبط تلقائي لمدة المشهد على طول الصوت.
- موسيقى خلفية هادئة مولّدة محلياً، ومزج صوتي AAC داخل ملف MP4.
- شريط تقدّم، رقم المشهد، وهوية الاستوديو في كل إطار.
- تصدير H.264 MP4 (yuv420p + faststart) عبر ffmpeg المضمّن — بدون تثبيت نظامي.
- ملف Storyboard بصيغة JSON للتحكم الكامل في النصوص والمدة والسمات والتعليق الصوتي.

## التثبيت / Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[voice]"
```

`[voice]` يثبّت محرّكي الصوت `edge-tts` و`gTTS`. بدونهما يعمل توليد الفيديو الصامت فقط.
التعليق الصوتي يحتاج اتصالاً بالشبكة (أصوات Edge العصبية أولاً ثم Google TTS)،
بينما الموسيقى الخلفية تُولَّد محلياً بلا أي اعتماد خارجي.

## الاستخدام السريع / Quick start

```bash
# فيديو صامت من وصف نصي
.venv/bin/nayro-video --prompt "استوديو نيرو ليفانت للذكاء الاصطناعي. حوّل أفكارك إلى فيديو متكامل. جاهز للنشر على كل المنصات." \
  --out output/demo.mp4

# فيديو كامل: سكربت + تعليق صوتي + موسيقى
.venv/bin/nayro-video --storyboard examples/studio-intro.json \
  --voice --music --out output/nayro-studio-voiceover.mp4
```

فيديوهات جاهزة في المستودع:

| File | الوصف |
| --- | --- |
| [`output/nayro-studio-intro.mp4`](output/nayro-studio-intro.mp4) | نسخة صامتة 1280×720، 11 ثانية |
| [`output/nayro-studio-voiceover.mp4`](output/nayro-studio-voiceover.mp4) | نسخة كاملة بتعليق صوتي عربي وموسيقى (AAC) |

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
| `--voice` | off | تفعيل التعليق الصوتي لكل مشهد |
| `--tts` | `auto` | `auto` / `edge` (أصوات عصبية) / `gtts` |
| `--lang` | `ar` | لغة التعليق (`ar`, `en`, ...) |
| `--voice-name` | `ar-LB-LaylaNeural` | صوت محدّد من مزوّد الصوت |
| `--music` | off | إضافة موسيقى خلفية هادئة |
| `--music-volume` | `0.12` | مستوى الموسيقى بين 0 و1 |

عند تفعيل `--voice` تُضبط مدة كل مشهد تلقائياً لتستوعب التعليق، ويبدأ الصوت
بعد 0.35 ثانية من بداية المشهد وينتهي قبل المشهد التالي، ثم يُدمج المسار
الصوتي AAC داخل الـ MP4. النص المنطوق لكل مشهد هو `narration` إن وُجد،
وإلا العنوان + العنوان الفرعي.

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
    {
      "title": "استوديو نيرو ليفانت",
      "subtitle": "نصنع المحتوى بالذكاء الاصطناعي",
      "narration": "مرحباً بكم في استوديو نيرو ليفانت للذكاء الاصطناعي.",
      "duration": 3.2
    },
    { "title": "جاهز للنشر", "duration": 3.0, "theme": "desert" }
  ]
}
```

## التطوير والاختبارات / Tests

```bash
.venv/bin/pip install -e ".[dev,voice]"
.venv/bin/python -m pytest -q
# اختبار الصوت المباشر (يتطلب شبكة)
NAYRO_NETWORK_TESTS=1 .venv/bin/python -m pytest tests/test_tts.py -q
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
  tts.py          # محرّكات الصوت (Edge Neural / Google TTS)
  voice.py        # توليد التعليق وضبط توقيت المشاهد
  audio.py        # فك الصوت، الموسيقى، المزج
  video.py        # ترميز H.264 + مزج AAC عبر ffmpeg
  probe.py        # قراءة بيانات الفيديو الناتج
  assets/fonts/   # Noto Kufi Arabic + Noto Sans
examples/         # Storyboard جاهز للتجربة
output/           # الفيديوهات التجريبية
tests/            # اختبارات pytest
```
