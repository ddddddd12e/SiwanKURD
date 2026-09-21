# پنل اشتراک (ادمین + صفحه‌ی کاربر + ربات تلگرام)

یه پروژه‌ی سبک با Flask و SQLite:
- **پنل ادمین** (`/admin`): ساخت کاربر، حجم و انقضا، مدیریت کانفیگ‌ها
- **صفحه‌ی اشتراک** (`/sub/<توکن>`): صفحه‌ای با اسم برند تو که مصرف و کانفیگ‌ها رو نشون می‌ده؛ کلاینت‌هایی مثل v2rayNG و Hiddify همین آدرس رو به‌عنوان ساب‌لینک می‌گیرن
- **ربات تلگرام** (اختیاری): دریافت کانفیگ، مشاهده‌ی مصرف، لینک اشتراک

نکته: این پروژه خودش ترافیک عبور نمی‌ده؛ فقط لینک کانفیگ‌هایی که تو وارد می‌کنی رو مدیریت و نمایش می‌ده. مصرف رو هم فعلاً دستی توی «ویرایش» کاربر وارد می‌کنی.

## دیپلوی روی Railway
1. پوشه رو توی یه ریپوی GitHub بذار.
2. Railway → New Project → Deploy from GitHub repo.
3. توی Variables اینا رو بذار: `BRAND_NAME`, `ADMIN_USER`, `ADMIN_PASS`, `SECRET_KEY` (و اگه ربات می‌خوای `TELEGRAM_BOT_TOKEN`).
4. برای اینکه دیتا با ری‌استارت پاک نشه: یه Volume بساز، Mount path رو `/data` بذار و `DB_PATH=/data/data.db` رو اضافه کن.
5. Settings → Networking → Generate Domain. بعد آدرس `/admin` رو باز کن.

## اجرای محلی
```
pip install -r requirements.txt
ADMIN_PASS=1234 BRAND_NAME=SiwanKURD python app.py
```
بعد `http://localhost:5000/admin`.

## تنظیمات
همه‌ی متغیرها توی `.env.example` توضیح داده شدن.
