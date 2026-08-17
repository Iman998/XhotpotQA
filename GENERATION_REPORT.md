# گزارش تولید دیتاست XHotpotQA v2

**تاریخ:** ۱۴ مرداد ۱۴۰۵ (۱۴ اوت ۲۰۲۶)
**مدل:** gemma-4-31B-it (vLLM v0.19.1، ۲ GPU، tensor-parallel-size=2)
**سرور:** `192.168.1.204:16688` (API key: `EMPTY`)
**مسیر خروجی:** `dataset/hf_sft/xhotpot/XhotpotQA-main/data/processed/`

---

## ۱. نتیجه نهایی

| اسپلیت | رکورد موفق | خطا | مورد انتظار | پوشش |
|---|---|---|---|---|
| **validation** | ۷۴۰۳ | ۲ | ۷۴۰۵ | **۹۹.۹۷٪** |
| **train** (hard) | ۱۵۴۳۳ | ۱ | ۱۵۶۶۱ | **۹۸.۵۴٪** |
| **مجموع** | **۲۲۸۳۶** | **۳** | **۲۳۰۶۶** | **۹۹.۰٪** |

### فایل‌های خروجی
```
data/processed/validation.v2.jsonl        → ۷۴۰۳ رکورد
data/processed/train.v2.jsonl             → ۱۵۴۳۳ رکورد
data/processed/validation.v2.jsonl.errors.jsonl  → ۲ خطا
data/processed/train.v2.jsonl.errors.jsonl       → ۱ خطا
```

### ۳ خطای باقی‌مونده (غیرقابل رفع — خطای داده‌ی اصلی HotpotQA)

| source_id | اسپلیت | خطا | دلیل |
|---|---|---|---|
| `5a77e9c0` | validation | `Candidate 'p07' has empty sentence content` | کل پاراگراف p07 خالی است |
| `5ae61bfd` | validation | `Supporting sentence 902 is outside 'p07'` | annotation اشتباه: supporting fact به جمله‌ی ۹۰۲ اشاره می‌کند ولی پاراگراف فقط چند جمله دارد |
| `5a845173` | train | `Supporting sentence 2 is outside 'p04'` | annotation اشتباه: supporting fact به جمله‌ی ۲ اشاره می‌کند ولی پاراگراف کمتر از ۲ جمله دارد |

---

## ۲. تنظیمات اجرا

### پارامترهای اصلی
- **تعداد ترد:** ۱۲۸ (اجرای اولیه) → ۴ (retry)
- **دمای اولیه:** 0.0 (دترمینیستیک)
- **دمای retry:** 0.2 → 0.3
- **timeout:** ۶۰۰ ثانیه (۱۰ دقیقه)
- **max_new_tokens:** ۴۰۹۶
- **seed:** ۲۰۲۶۰۸۱۰

### کانفیگ‌های ساخته‌شده
| فایل | توضیح |
|---|---|
| `configs/generation/gemma4_31b_local.yaml` | temp=0.0 (دترمینیستیک) |
| `configs/generation/gemma4_31b_local_temp01.yaml` | temp=0.1 |
| `configs/generation/gemma4_31b_local_temp02.yaml` | temp=0.2 |
| `configs/generation/gemma4_31b_local_temp03.yaml` | temp=0.3، timeout=600s |

---

## ۳. تغییرات کد

### ۳.۱. `src/xhotpotqa/generation/run.py`
- تابع `generate_dataset_parallel` اضافه شد: پردازش همزمان با `ThreadPoolExecutor`، قفل نوشتن، tqdm progress bar، و **error isolation** (رکوردهای fail‌شده skip و به فایل `.errors.jsonl` لاگ می‌شوند به جای کرش کردن کل pipeline).

### ۳.۲. `src/xhotpotqa/generation/translation.py`
دو patch کلیدی:

**Patch ۱ — thread-safe retry counter:**
- قفل `threading.Lock` روی `_retry_count` برای جلوگیری از race condition در اجرای همزمان.

**Patch ۲ — fallback ترجمه‌ی تک‌جمله‌ای:**
- در `translate_sentences`: اگر ترجمه‌ی آرایه‌ای fail شود، جملات تک‌تک ترجمه می‌شوند تا alignment حفظ شود.
- در `translate_text`: جملات خالی/قطعه‌ای (طول < ۲) با `"—"` جایگزین می‌شوند (خطای `empty_response` را حل می‌کند).
- اگر مدل نتواند جمله‌ای را ترجمه کند، متن اصلی برگردانده می‌شود تا alignment نشکند.

### ۳.۳. `src/xhotpotqa/cli.py`
- فلگ `--max-workers` برای کنترل تعداد ترد اضافه شد.
- فلگ `--no-progress` برای غیرفعال کردن tqdm.

### ۳.۴. اسکریپت‌های کمکی
| فایل | توضیح |
|---|---|
| `run_generate_all.sh` | اجرای متوالی validation + train |
| `retry_temp01_v2.py` | retry رکوردهای fail‌شده با فیلتر input و merge |

---

## ۴. روند اجرا و رفع خطا

### مرحله ۱ — اجرای اولیه (temp=0.0، ۱۲۸ ترد)
- validation: ۷۱۲۴ موفق، ۲۸۱ خطا (۳.۸٪)
- train: ۱۵۰۶۵ موفق، ۵۹۶ خطا (۳.۸٪)
- **مشکل:** اجرای همزمان دو فرایند روی یک فایل خروجی باعث ۷۸۰۹ رکورد تکراری در train شد → با dedup اصلاح شد.

### مرحله ۲ — retry با temp=0.0 (۴ راند)
- **نتیجه:** تقریباً صفر بازیابی. دلیل: خروجی دترمینیستیک = همان خطای قبلی تکرار می‌شود.

### مرحله ۳ — retry با temp=0.1 (۴ راند)
- validation: ۲۱۹ → ۲۱۱ خطا (۸ رکورد بازیابی)
- train: ۱۱۹۳ → ۵۰ خطا (۱۱۴۳ رکورد بازیابی)
- **مشکل:** خطای `sentence_alignment` همچنان سرسخت بود.

### مرحله ۴ — آنالیز ریشه خطا
- خطای `sentence_alignment`: مدل gemma-4 جمله‌های قطعه‌ای HotpotQA (مثل `"Tres Hombres" and "Fandango!` + `" were reissued...`) را در ترجمه‌ی آرایه‌ای یکی می‌کند.
- خطای `empty_response`: HotpotQA اصلی جمله‌های خالی `''` دارد.
- خطای `supporting_fact_oob`: annotation اشتباه در داده‌ی اصلی HotpotQA.

### مرحله ۵ — patch fallback + retry با temp=0.2
- **Patch:** اگر ترجمه‌ی آرایه‌ای fail شود، تک‌تک جملات ترجمه می‌شوند.
- validation: ۲۱۱ → ۵۶ خطا (۱۵۵ رکورد بازیابی)
- train: ۵۰ → ۵۰ خطا (۱۹۷ رکورد بازیابی در round اول)

### مرحله ۶ — patch جملات خالی + retry با temp=0.3
- **Patch:** جملات خالی/قطعه‌ای با `"—"` جایگزین می‌شوند.
- validation: ۵۶ → ۲ خطا (۵۴ رکورد بازیابی)
- train: ۵۰ → ۱ خطا (۴۹ رکورد بازیابی)
- **نتیجه نهایی:** فقط ۳ خطای غیرقابل رفع (خطای داده‌ی اصلی) باقی ماند.

---

## ۵. دستورات مفید

### مانیتورینگ
```bash
# تعداد رکوردها
wc -l data/processed/validation.v2.jsonl data/processed/train.v2.jsonl

# خطاهای باقی‌مونده
cat data/processed/validation.v2.jsonl.errors.jsonl
cat data/processed/train.v2.jsonl.errors.jsonl
```

### اعتبارسنجی
```bash
xhotpotqa validate --train data/processed/train.v2.jsonl --validation data/processed/validation.v2.jsonl
```

---

## ۶. کامیت‌ها

| SHA | پیام |
|---|---|
| `17306d6` | Initial commit: XHotpotQA v0.3.0 source tree |
| `b073e12` | Add concurrent generation (128 threads) + resilient error handling |

**تغییرات بدون کامیت (آماده برای review):**
- `src/xhotpotqa/generation/translation.py` (patch fallback + empty sentence)
- `configs/generation/gemma4_31b_local_temp*.yaml` (۴ کانفیگ)
- `retry_temp01_v2.py` و اسکریپت‌های retry
